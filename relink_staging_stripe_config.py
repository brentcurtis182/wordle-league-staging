"""
Relink staging admin_config to EXISTING Stripe sandbox prices.

Use after a full prod->staging DB resync wipes the staging-only Stripe config.
Read-only on Stripe (lists prices/products); only WRITES to staging admin_config.
Does NOT create or modify any Stripe products/prices.

Run:
    STRIPE_SECRET_KEY="sk_test_..." python relink_staging_stripe_config.py
"""
import os, sys, stripe, psycopg2

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe.api_key or not stripe.api_key.startswith('sk_test_'):
    print("ERROR: set STRIPE_SECRET_KEY to a sandbox sk_test_ key"); sys.exit(1)

STAGING_DB = "postgresql://postgres:XaTEjaiVqLfnGGVbWnYxAejCSuuKtGJE@metro.proxy.rlwy.net:29344/railway"

EXPECTED = [
    'stripe_price_sms_4', 'stripe_price_sms_5', 'stripe_price_sms_6',
    'stripe_price_sms_7', 'stripe_price_sms_8', 'stripe_price_sms_9',
    'stripe_price_sms_9_ai', 'stripe_price_sms_ai',
    'stripe_price_slack_1', 'stripe_price_slack_1_ai',
    'stripe_price_slack_2', 'stripe_price_slack_5',
]


def md_field(obj, field):
    """Safe metadata read for stripe objects (no .get / dict() support here)."""
    try:
        m = obj['metadata']
        return m[field] if field in m else None
    except Exception:
        return None


def set_config(cur, key, value):
    cur.execute("""
        INSERT INTO admin_config (key, value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
    """, (key, value))


# --- Gather newest active price per config key (Stripe read-only) ---
best = {}       # key -> (created, price_id, amount)
unmapped = []   # (price_id, amount)
for price in stripe.Price.list(active=True, limit=100).auto_paging_iter():
    plan_tier = md_field(price, 'plan_tier')
    addon = md_field(price, 'addon')
    if plan_tier:
        k = f"stripe_price_{plan_tier}"
    elif addon == 'ai_messaging':
        k = 'stripe_price_sms_ai'
    else:
        unmapped.append((price['id'], price['unit_amount']))
        continue
    if k not in best or price['created'] > best[k][0]:
        best[k] = (price['created'], price['id'], price['unit_amount'])

print(f"Sandbox: matched {len(best)} config keys from active prices "
      f"({len(unmapped)} active prices had no plan_tier/addon metadata)\n")

# --- Write to staging admin_config ---
conn = psycopg2.connect(STAGING_DB); cur = conn.cursor()
written = 0
for k in EXPECTED:
    if k in best:
        _, pid, amt = best[k]
        set_config(cur, k, pid)
        amt_s = f"${amt/100:.0f}/mo" if amt is not None else "?"
        print(f"  SET  {k:26} = {pid}  ({amt_s})")
        written += 1
    else:
        print(f"  MISS {k:26} -> no active price found in sandbox!")

# Best-effort product reference keys
prod_map = {'sms_league': 'stripe_product_sms', 'sms_ai_addon': 'stripe_product_sms_ai',
            'slack_league': 'stripe_product_slack'}
prod_best = {}
for prod in stripe.Product.list(active=True, limit=100).auto_paging_iter():
    ck = prod_map.get(md_field(prod, 'product_type'))
    if ck and (ck not in prod_best or prod['created'] > prod_best[ck][0]):
        prod_best[ck] = (prod['created'], prod['id'])
for ck, (_, pid) in prod_best.items():
    set_config(cur, ck, pid)
    print(f"  SET  {ck:26} = {pid}")

# Restore payment_required default if missing (do NOT overwrite if present)
cur.execute("SELECT value FROM admin_config WHERE key = 'payment_required'")
if not cur.fetchone():
    set_config(cur, 'payment_required', 'false')
    print("  SET  payment_required          = false (default)")
else:
    print("  keep payment_required (already set)")

conn.commit()
print(f"\nDone. Wrote {written}/{len(EXPECTED)} price keys to staging admin_config.")

if unmapped:
    print(f"\nNote: {len(unmapped)} active price(s) had no plan_tier/addon metadata (ignored).")

cur.close(); conn.close()
