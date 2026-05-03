"""
One-time setup script: Create Stripe products and prices for Wordle League.

Run against staging with:
    DATABASE_URL="<staging_public_url>" STRIPE_SECRET_KEY="sk_test_..." python setup_stripe_products.py

This creates all products/prices in Stripe and saves the price IDs to admin_config.
Safe to re-run — checks for existing products first.
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


def set_config(cursor, conn, key, value):
    cursor.execute("""
        INSERT INTO admin_config (key, value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
    """, (key, value))
    conn.commit()


def main():
    print("=" * 60)
    print("Wordle League - Stripe Products & Prices Setup")
    print("=" * 60)
    print(f"\nUsing Stripe key: {stripe.api_key[:12]}...")
    print()

    conn = get_db_connection()
    cursor = conn.cursor()

    # --- SMS League Product ---
    print("Creating SMS League product...")
    sms_product = stripe.Product.create(
        name="SMS League",
        description="Monthly SMS league subscription for Wordle League",
        metadata={'product_type': 'sms_league'}
    )
    print(f"  Product ID: {sms_product.id}")

    sms_prices = {
        4: 800,
        5: 1000,
        6: 1200,
        7: 1400,
        8: 1600,
        9: 1800,
    }

    print("\n  Creating SMS prices:")
    for player_count, cents in sms_prices.items():
        price = stripe.Price.create(
            product=sms_product.id,
            unit_amount=cents,
            currency='usd',
            recurring={'interval': 'month'},
            nickname=f"SMS {player_count}-player league",
            metadata={'player_count': str(player_count), 'plan_type': 'sms', 'plan_tier': f'sms_{player_count}'}
        )
        config_key = f'stripe_price_sms_{player_count}'
        set_config(cursor, conn, config_key, price.id)
        print(f"    {player_count} players (${cents/100:.0f}/mo): {price.id}")

    # --- SMS AI Messaging Addon ---
    print("\nCreating SMS AI Messaging addon product...")
    sms_ai_product = stripe.Product.create(
        name="SMS AI Messaging",
        description="AI messaging addon for SMS leagues (+$3/mo)",
        metadata={'product_type': 'sms_ai_addon'}
    )
    print(f"  Product ID: {sms_ai_product.id}")

    sms_ai_price = stripe.Price.create(
        product=sms_ai_product.id,
        unit_amount=300,
        currency='usd',
        recurring={'interval': 'month'},
        nickname="SMS AI Messaging Addon",
        metadata={'plan_type': 'sms', 'addon': 'ai_messaging'}
    )
    set_config(cursor, conn, 'stripe_price_sms_ai', sms_ai_price.id)
    print(f"  AI Addon ($3/mo): {sms_ai_price.id}")

    # --- Slack League Product ---
    print("\nCreating Slack League product...")
    slack_product = stripe.Product.create(
        name="Slack League",
        description="Monthly Slack league subscription for Wordle League",
        metadata={'product_type': 'slack_league'}
    )
    print(f"  Product ID: {slack_product.id}")

    slack_tiers = [
        ('slack_1', 500, "1 Slack league"),
        ('slack_1_ai', 700, "1 Slack league + AI messaging"),
        ('slack_2', 1000, "2 Slack leagues + AI messaging"),
        ('slack_5', 2000, "5 Slack leagues + AI messaging"),
    ]

    print("\n  Creating Slack prices:")
    for tier_name, cents, description in slack_tiers:
        price = stripe.Price.create(
            product=slack_product.id,
            unit_amount=cents,
            currency='usd',
            recurring={'interval': 'month'},
            nickname=description,
            metadata={'plan_type': 'slack', 'plan_tier': tier_name}
        )
        config_key = f'stripe_price_{tier_name}'
        set_config(cursor, conn, config_key, price.id)
        print(f"    {description} (${cents/100:.0f}/mo): {price.id}")

    # --- Store product IDs too (for reference) ---
    set_config(cursor, conn, 'stripe_product_sms', sms_product.id)
    set_config(cursor, conn, 'stripe_product_sms_ai', sms_ai_product.id)
    set_config(cursor, conn, 'stripe_product_slack', slack_product.id)

    # --- Set payment_required to false by default ---
    cursor.execute("SELECT value FROM admin_config WHERE key = 'payment_required'")
    if not cursor.fetchone():
        set_config(cursor, conn, 'payment_required', 'false')
        print("\n  Set payment_required = false (default)")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("DONE! All products, prices, and config keys saved.")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Verify in Stripe Dashboard: https://dashboard.stripe.com/test/products")
    print("  2. Set up webhook endpoint after deploying /billing/webhook route")
    print("  3. Toggle payment_required to 'true' when ready to test")


if __name__ == '__main__':
    main()
