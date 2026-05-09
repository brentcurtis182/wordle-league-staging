"""
One-time migration: Split single "SMS League" product into per-tier products
so Stripe displays distinct names like "SMS League -4 Players".

Also creates the sms_9_ai bundle product if it doesn't exist yet.

Run against staging with:
    DATABASE_URL="<staging_public_url>" STRIPE_SECRET_KEY="sk_test_..." python migrate_stripe_products.py

Safe to re-run — checks for existing config before creating.
Does NOT delete old products/prices (Stripe keeps them for historical invoices).
"""

import os
import sys
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

if not stripe.api_key:
    print("ERROR: Set STRIPE_SECRET_KEY environment variable")
    sys.exit(1)


def get_db_connection():
    import psycopg2
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url, connect_timeout=10)
    else:
        return psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432),
            connect_timeout=10
        )


def get_config(cursor, key):
    cursor.execute("SELECT value FROM admin_config WHERE key = %s", (key,))
    row = cursor.fetchone()
    return row[0] if row else None


def set_config(cursor, conn, key, value):
    cursor.execute("""
        INSERT INTO admin_config (key, value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
    """, (key, value))
    conn.commit()


def main():
    print("=" * 60)
    print("Stripe Migration: Per-Tier SMS Products")
    print("=" * 60)
    print(f"\nUsing Stripe key: {stripe.api_key[:12]}...")

    conn = get_db_connection()
    cursor = conn.cursor()

    # --- SMS tiers: one product per player count ---
    sms_tiers = {
        4: 800,
        5: 1000,
        6: 1200,
        7: 1400,
        8: 1600,
        9: 1800,
    }

    for player_count, cents in sms_tiers.items():
        config_key = f'stripe_price_sms_{player_count}'
        old_price_id = get_config(cursor, config_key)

        print(f"\n--- SMS {player_count} Players (${cents/100:.0f}/mo) ---")
        print(f"  Old price ID: {old_price_id}")

        # Create a new product for this tier
        product = stripe.Product.create(
            name=f"SMS League -{player_count} Players",
            description=f"Monthly SMS league subscription for {player_count} players",
            metadata={'product_type': 'sms_league', 'player_count': str(player_count)}
        )
        print(f"  New product: {product.id} ({product.name})")

        # Create a new price under the new product
        price = stripe.Price.create(
            product=product.id,
            unit_amount=cents,
            currency='usd',
            recurring={'interval': 'month'},
            nickname=f"SMS {player_count}-player league",
            metadata={'player_count': str(player_count), 'plan_type': 'sms', 'plan_tier': f'sms_{player_count}'}
        )
        print(f"  New price:   {price.id}")

        # Migrate any active subscription items from old price to new price
        if old_price_id:
            migrated = 0
            subs = stripe.Subscription.list(price=old_price_id, status='active', limit=100)
            for sub in subs.auto_paging_iter():
                for item in sub['items']['data']:
                    if item['price']['id'] == old_price_id:
                        stripe.SubscriptionItem.modify(
                            item['id'],
                            price=price.id,
                            proration_behavior='none',  # no charge for same-amount swap
                        )
                        migrated += 1
            if migrated:
                print(f"  Migrated {migrated} active subscription(s)")

            # Archive the old price (can't delete prices with history)
            stripe.Price.modify(old_price_id, active=False)
            print(f"  Archived old price: {old_price_id}")

        # Update config to point to new price
        set_config(cursor, conn, config_key, price.id)
        print(f"  Updated admin_config: {config_key} = {price.id}")

    # --- SMS 9 + AI bundle ---
    print(f"\n--- SMS 9 + AI Bundle ($20/mo) ---")
    old_bundle_price = get_config(cursor, 'stripe_price_sms_9_ai')
    print(f"  Old price ID: {old_bundle_price}")

    bundle_product = stripe.Product.create(
        name="SMS League -9 Players + AI",
        description="Monthly SMS league subscription for 9 players with AI messaging included",
        metadata={'product_type': 'sms_league', 'player_count': '9', 'ai_included': 'true'}
    )
    print(f"  New product: {bundle_product.id} ({bundle_product.name})")

    bundle_price = stripe.Price.create(
        product=bundle_product.id,
        unit_amount=2000,
        currency='usd',
        recurring={'interval': 'month'},
        nickname="SMS 9 Players + AI Messaging",
        metadata={'player_count': '9', 'plan_type': 'sms', 'plan_tier': 'sms_9_ai', 'ai_included': 'true'}
    )
    print(f"  New price:   {bundle_price.id}")

    if old_bundle_price:
        migrated = 0
        subs = stripe.Subscription.list(price=old_bundle_price, status='active', limit=100)
        for sub in subs.auto_paging_iter():
            for item in sub['items']['data']:
                if item['price']['id'] == old_bundle_price:
                    stripe.SubscriptionItem.modify(
                        item['id'],
                        price=bundle_price.id,
                        proration_behavior='none',
                    )
                    migrated += 1
        if migrated:
            print(f"  Migrated {migrated} active subscription(s)")

        stripe.Price.modify(old_bundle_price, active=False)
        print(f"  Archived old price: {old_bundle_price}")

    set_config(cursor, conn, 'stripe_price_sms_9_ai', bundle_price.id)
    print(f"  Updated admin_config: stripe_price_sms_9_ai = {bundle_price.id}")

    # --- Slack tiers: one product per tier ---
    slack_tiers = [
        ('slack_1', 500, 'Slack League - 1 League', '1 Slack league', {'plan_type': 'slack', 'plan_tier': 'slack_1'}),
        ('slack_1_ai', 700, 'Slack League - 1 League + AI', '1 Slack league + AI messaging', {'plan_type': 'slack', 'plan_tier': 'slack_1_ai', 'ai_included': 'true'}),
        ('slack_2', 1000, 'Slack League - 2 Leagues + AI', '2 Slack leagues + AI messaging', {'plan_type': 'slack', 'plan_tier': 'slack_2', 'ai_included': 'true'}),
        ('slack_5', 2000, 'Slack League - 5 Leagues + AI', '5 Slack leagues + AI messaging', {'plan_type': 'slack', 'plan_tier': 'slack_5', 'ai_included': 'true'}),
    ]

    for tier_name, cents, product_name, nickname, metadata in slack_tiers:
        config_key = f'stripe_price_{tier_name}'
        old_price_id = get_config(cursor, config_key)

        print(f"\n--- {product_name} (${cents/100:.0f}/mo) ---")
        print(f"  Old price ID: {old_price_id}")

        product = stripe.Product.create(
            name=product_name,
            description=f"Monthly Slack league subscription: {nickname}",
            metadata={'product_type': 'slack_league', **metadata}
        )
        print(f"  New product: {product.id} ({product.name})")

        price = stripe.Price.create(
            product=product.id,
            unit_amount=cents,
            currency='usd',
            recurring={'interval': 'month'},
            nickname=nickname,
            metadata=metadata
        )
        print(f"  New price:   {price.id}")

        if old_price_id:
            migrated = 0
            subs = stripe.Subscription.list(price=old_price_id, status='active', limit=100)
            for sub in subs.auto_paging_iter():
                for item in sub['items']['data']:
                    if item['price']['id'] == old_price_id:
                        stripe.SubscriptionItem.modify(
                            item['id'],
                            price=price.id,
                            proration_behavior='none',
                        )
                        migrated += 1
            if migrated:
                print(f"  Migrated {migrated} active subscription(s)")

            stripe.Price.modify(old_price_id, active=False)
            print(f"  Archived old price: {old_price_id}")

        set_config(cursor, conn, config_key, price.id)
        print(f"  Updated admin_config: {config_key} = {price.id}")

    # --- Done ---
    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("DONE! Each SMS and Slack tier now has its own product in Stripe.")
    print("Old prices archived (kept for invoice history).")
    print("Active subscriptions migrated to new prices.")
    print("=" * 60)
    print("\nVerify at: https://dashboard.stripe.com/test/products")


if __name__ == '__main__':
    main()
