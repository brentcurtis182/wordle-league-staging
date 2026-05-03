"""
Stripe subscription billing for Wordle League.

Handles: checkout sessions, customer portal, webhook processing,
subscription status checks, and slot/credit management.
"""

import os
import logging
import stripe
from datetime import datetime

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Legacy leagues — free forever, bypass all payment checks
LEGACY_LEAGUE_IDS = {1, 3, 4, 7, 8, 19}

# SMS pricing: player_count -> cents/month
SMS_PRICE_MAP = {4: 800, 5: 1000, 6: 1200, 7: 1400, 8: 1600, 9: 1800}

# SMS bundle tiers (player_count + AI included)
SMS_BUNDLES = {
    'sms_9_ai': {'price_cents': 2000, 'player_count': 9, 'ai_included': True},
}

# Slack tiers
SLACK_TIERS = {
    'slack_1': {'price_cents': 500, 'league_slots': 1, 'ai_included': False},
    'slack_1_ai': {'price_cents': 700, 'league_slots': 1, 'ai_included': True},
    'slack_2': {'price_cents': 1000, 'league_slots': 2, 'ai_included': True},
    'slack_5': {'price_cents': 2000, 'league_slots': 5, 'ai_included': True},
}


def is_legacy_league(league_id):
    """Check if a league is a legacy free league."""
    return league_id in LEGACY_LEAGUE_IDS


def is_league_grandfathered(league):
    """
    Check if a league was activated before payment_required was turned on.
    A league is grandfathered if it already has an active connection.
    """
    if is_legacy_league(league['id']):
        return True
    # Already connected = grandfathered
    if league.get('twilio_conversation_sid') or league.get('slack_channel_id') or league.get('discord_channel_id'):
        return True
    return False


def league_requires_payment(league, payment_required_flag):
    """
    Determine if a league needs a subscription to activate.
    Returns False if: legacy, grandfathered, or payment_required flag is off.
    """
    if not payment_required_flag:
        return False
    if is_legacy_league(league['id']):
        return False
    if is_league_grandfathered(league):
        return False
    return True


# ---------------------------------------------------------------------------
# Database table creation (idempotent)
# ---------------------------------------------------------------------------

def create_billing_tables():
    """Create all billing-related tables. Safe to call multiple times."""
    from auth import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # subscriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
                stripe_price_id VARCHAR(255) NOT NULL,
                plan_type VARCHAR(50) NOT NULL,
                plan_tier VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                current_period_end TIMESTAMP,
                cancel_at_period_end BOOLEAN DEFAULT FALSE,
                ai_messaging_addon BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # subscription_leagues mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_leagues (
                id SERIAL PRIMARY KEY,
                subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
                league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subscription_id, league_id)
            )
        """)

        # Webhook event idempotency table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stripe_webhook_events (
                stripe_event_id VARCHAR(255) PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe ON subscriptions(stripe_subscription_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_leagues_sub ON subscription_leagues(subscription_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_leagues_league ON subscription_leagues(league_id)
        """)

        # Add stripe_customer_id to users table
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)")
        except Exception:
            pass

        # Add max_players and lapsed_notified to leagues table
        try:
            cursor.execute("ALTER TABLE leagues ADD COLUMN IF NOT EXISTS max_players INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE leagues ADD COLUMN IF NOT EXISTS lapsed_notified BOOLEAN DEFAULT FALSE")
        except Exception:
            pass

        conn.commit()
        logging.info("Billing tables created/verified successfully")
        return True

    except Exception as e:
        conn.rollback()
        logging.error(f"Error creating billing tables: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Stripe Customer Management
# ---------------------------------------------------------------------------

def get_or_create_stripe_customer(user_id, email, name=None):
    """Get existing or create new Stripe customer for a user."""
    from auth import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT stripe_customer_id FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()

        if row and row[0]:
            return row[0]

        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=email,
            name=name or email,
            metadata={'user_id': str(user_id)}
        )

        cursor.execute(
            "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
            (customer.id, user_id)
        )
        conn.commit()
        logging.info(f"Created Stripe customer {customer.id} for user {user_id}")
        return customer.id

    except Exception as e:
        conn.rollback()
        logging.error(f"Error getting/creating Stripe customer for user {user_id}: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Checkout & Portal Sessions
# ---------------------------------------------------------------------------

def create_checkout_session(user_id, email, plan_type, plan_tier, league_id=None,
                            success_url=None, cancel_url=None):
    """
    Create a Stripe Checkout session for a subscription purchase.
    Returns the checkout session URL.
    """
    from auth import get_db_connection, get_config

    customer_id = get_or_create_stripe_customer(user_id, email)

    # Look up the price ID from admin_config
    price_key = f'stripe_price_{plan_tier}'
    price_id = get_config(price_key)
    if not price_id:
        raise ValueError(f"No Stripe price configured for tier: {plan_tier} (key: {price_key})")

    line_items = [{'price': price_id, 'quantity': 1}]

    # For SMS plans, check if AI messaging addon is requested
    # (handled separately via plan_tier naming or explicit addon)

    base_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:5000')
    scheme = 'https' if 'railway' in base_url or 'wordplay' in base_url else 'http'
    if not success_url:
        success_url = f"{scheme}://{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    if not cancel_url:
        cancel_url = f"{scheme}://{base_url}/billing/cancel"

    metadata = {
        'user_id': str(user_id),
        'plan_type': plan_type,
        'plan_tier': plan_tier,
    }
    if league_id:
        metadata['league_id'] = str(league_id)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode='subscription',
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        subscription_data={'metadata': metadata},
    )

    logging.info(f"Created checkout session {session.id} for user {user_id}, plan {plan_tier}")
    return session.url


def create_customer_portal_session(user_id, email, return_url=None):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    customer_id = get_or_create_stripe_customer(user_id, email)

    base_url = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:5000')
    scheme = 'https' if 'railway' in base_url or 'wordplay' in base_url else 'http'
    if not return_url:
        return_url = f"{scheme}://{base_url}/dashboard/membership"

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )

    return session.url


# ---------------------------------------------------------------------------
# Subscription Queries
# ---------------------------------------------------------------------------

def get_user_subscriptions(user_id):
    """Get all subscriptions for a user with their assigned leagues."""
    from auth import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.id, s.stripe_subscription_id, s.plan_type, s.plan_tier,
                   s.status, s.current_period_end, s.cancel_at_period_end,
                   s.ai_messaging_addon, s.created_at
            FROM subscriptions s
            WHERE s.user_id = %s
            ORDER BY s.created_at DESC
        """, (user_id,))

        subscriptions = []
        for row in cursor.fetchall():
            sub = {
                'id': row[0],
                'stripe_subscription_id': row[1],
                'plan_type': row[2],
                'plan_tier': row[3],
                'status': row[4],
                'current_period_end': row[5],
                'cancel_at_period_end': row[6],
                'ai_messaging_addon': row[7],
                'created_at': row[8],
            }

            # Get assigned leagues
            cursor.execute("""
                SELECT sl.league_id, l.name, l.display_name
                FROM subscription_leagues sl
                JOIN leagues l ON l.id = sl.league_id
                WHERE sl.subscription_id = %s
            """, (sub['id'],))
            sub['leagues'] = [{'id': r[0], 'name': r[1], 'display_name': r[2]} for r in cursor.fetchall()]

            subscriptions.append(sub)

        return subscriptions

    finally:
        cursor.close()
        conn.close()


def get_league_subscription_status(league_id):
    """
    Get subscription status for a specific league.
    Returns: 'active', 'past_due', 'canceled', 'lapsed', or None (no subscription / legacy / grandfathered)
    """
    from auth import get_db_connection

    if is_legacy_league(league_id):
        return None  # Legacy leagues don't need subscriptions

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.status
            FROM subscription_leagues sl
            JOIN subscriptions s ON s.id = sl.subscription_id
            WHERE sl.league_id = %s
            ORDER BY s.created_at DESC
            LIMIT 1
        """, (league_id,))

        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        cursor.close()
        conn.close()


def get_available_slots(user_id, plan_type):
    """
    Get the number of available (unassigned) league slots for a user's subscriptions.
    Returns: (total_slots, used_slots, available_slots)
    """
    from auth import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.id, s.plan_tier, s.status
            FROM subscriptions s
            WHERE s.user_id = %s AND s.plan_type = %s AND s.status = 'active'
        """, (user_id, plan_type))

        total_slots = 0
        for sub_id, plan_tier, status in cursor.fetchall():
            if plan_type == 'sms':
                total_slots += 1  # Each SMS subscription = 1 league slot
            elif plan_type == 'slack':
                tier_info = SLACK_TIERS.get(plan_tier, {})
                total_slots += tier_info.get('league_slots', 1)

        # Count used slots
        cursor.execute("""
            SELECT COUNT(*)
            FROM subscription_leagues sl
            JOIN subscriptions s ON s.id = sl.subscription_id
            WHERE s.user_id = %s AND s.plan_type = %s AND s.status = 'active'
        """, (user_id, plan_type))

        used_slots = cursor.fetchone()[0]
        return total_slots, used_slots, total_slots - used_slots

    finally:
        cursor.close()
        conn.close()


def assign_league_to_slot(user_id, league_id, plan_type):
    """
    Assign a league to an available subscription slot.
    Returns True if successful, False if no slots available.
    """
    from auth import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Find an active subscription with available slots
        cursor.execute("""
            SELECT s.id, s.plan_tier
            FROM subscriptions s
            WHERE s.user_id = %s AND s.plan_type = %s AND s.status = 'active'
            ORDER BY s.created_at ASC
        """, (user_id, plan_type))

        for sub_id, plan_tier in cursor.fetchall():
            # Check how many leagues are assigned to this subscription
            cursor.execute(
                "SELECT COUNT(*) FROM subscription_leagues WHERE subscription_id = %s",
                (sub_id,)
            )
            assigned_count = cursor.fetchone()[0]

            # Determine max slots for this subscription
            if plan_type == 'sms':
                max_slots = 1
            else:
                tier_info = SLACK_TIERS.get(plan_tier, {})
                max_slots = tier_info.get('league_slots', 1)

            if assigned_count < max_slots:
                cursor.execute("""
                    INSERT INTO subscription_leagues (subscription_id, league_id)
                    VALUES (%s, %s)
                    ON CONFLICT (subscription_id, league_id) DO NOTHING
                """, (sub_id, league_id))
                conn.commit()
                logging.info(f"Assigned league {league_id} to subscription {sub_id}")
                return True

        return False

    except Exception as e:
        conn.rollback()
        logging.error(f"Error assigning league to slot: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def check_ai_messaging_enabled(league_id):
    """
    Check if AI messaging (the 3 optional messages) is enabled for a league.
    Returns True if: legacy league, or subscription includes AI, or has AI addon.
    """
    from auth import get_db_connection

    if is_legacy_league(league_id):
        return True

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.plan_tier, s.ai_messaging_addon
            FROM subscription_leagues sl
            JOIN subscriptions s ON s.id = sl.subscription_id
            WHERE sl.league_id = %s AND s.status = 'active'
            LIMIT 1
        """, (league_id,))

        row = cursor.fetchone()
        if not row:
            return True  # No subscription = grandfathered, allow AI messaging

        plan_tier, has_addon = row
        # Check if the plan tier includes AI messaging
        tier_info = SLACK_TIERS.get(plan_tier, {})
        if tier_info.get('ai_included'):
            return True
        # Check SMS bundles (e.g. sms_9_ai)
        bundle_info = SMS_BUNDLES.get(plan_tier, {})
        if bundle_info.get('ai_included'):
            return True
        if has_addon:
            return True

        return False

    finally:
        cursor.close()
        conn.close()


def get_player_limit_for_league(league_id, channel_type):
    """
    Get the player limit for a league based on its subscription.
    Returns the max player count.
    """
    from auth import get_db_connection

    if is_legacy_league(league_id):
        return 9  # Legacy SMS leagues show 9/9

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if league has a max_players override from subscription
        cursor.execute("SELECT max_players FROM leagues WHERE id = %s", (league_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]

        # Default limits
        if channel_type == 'sms':
            return 9
        else:
            return 14

    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Webhook Handling
# ---------------------------------------------------------------------------

def handle_webhook_event(payload, sig_header):
    """
    Process a Stripe webhook event.
    Returns (success: bool, message: str)
    """
    from auth import get_db_connection

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return False, "Invalid signature"
    except Exception as e:
        return False, f"Webhook error: {str(e)}"

    # Idempotency check
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO stripe_webhook_events (stripe_event_id, event_type) VALUES (%s, %s)",
            (event['id'], event['type'])
        )
        conn.commit()
    except Exception:
        # Duplicate event — already processed
        conn.rollback()
        cursor.close()
        conn.close()
        return True, "Already processed"
    finally:
        cursor.close()
        conn.close()

    # Route to handler
    event_type = event['type']
    data = event['data']['object']

    if event_type == 'checkout.session.completed':
        _on_checkout_completed(data)
    elif event_type == 'customer.subscription.updated':
        _on_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        _on_subscription_deleted(data)
    elif event_type == 'invoice.payment_failed':
        _on_invoice_payment_failed(data)
    elif event_type == 'invoice.paid':
        _on_invoice_paid(data)
    else:
        logging.info(f"Unhandled Stripe event type: {event_type}")

    return True, "OK"


def _on_checkout_completed(session):
    """Handle successful checkout — create subscription record and assign league."""
    from auth import get_db_connection

    metadata = session.get('metadata', {})
    user_id = int(metadata.get('user_id', 0))
    plan_type = metadata.get('plan_type', '')
    plan_tier = metadata.get('plan_tier', '')
    league_id = metadata.get('league_id')

    stripe_sub_id = session.get('subscription')
    if not stripe_sub_id or not user_id:
        logging.error(f"Checkout completed but missing data: sub={stripe_sub_id}, user={user_id}")
        return

    # Fetch subscription details from Stripe
    sub = stripe.Subscription.retrieve(stripe_sub_id)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Determine AI addon status
        ai_addon = False
        if plan_type == 'slack':
            tier_info = SLACK_TIERS.get(plan_tier, {})
            ai_addon = tier_info.get('ai_included', False)
        elif plan_tier in SMS_BUNDLES:
            ai_addon = SMS_BUNDLES[plan_tier].get('ai_included', False)

        # Get price ID from the subscription
        price_id = sub['items']['data'][0]['price']['id'] if sub['items']['data'] else ''

        cursor.execute("""
            INSERT INTO subscriptions
                (user_id, stripe_subscription_id, stripe_price_id, plan_type, plan_tier,
                 status, current_period_end, ai_messaging_addon)
            VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s)
            ON CONFLICT (stripe_subscription_id) DO UPDATE SET
                status = EXCLUDED.status,
                current_period_end = EXCLUDED.current_period_end
        """, (user_id, stripe_sub_id, price_id, plan_type, plan_tier,
              sub['status'], sub['current_period_end'], ai_addon))

        conn.commit()

        # If a league_id was specified, assign it to this subscription
        if league_id:
            league_id = int(league_id)
            cursor.execute("SELECT id FROM subscriptions WHERE stripe_subscription_id = %s", (stripe_sub_id,))
            sub_row = cursor.fetchone()
            if sub_row:
                cursor.execute("""
                    INSERT INTO subscription_leagues (subscription_id, league_id)
                    VALUES (%s, %s)
                    ON CONFLICT (subscription_id, league_id) DO NOTHING
                """, (sub_row[0], league_id))

                # Set max_players for SMS leagues based on tier
                if plan_type == 'sms':
                    if plan_tier in SMS_BUNDLES:
                        player_count = SMS_BUNDLES[plan_tier]['player_count']
                    else:
                        player_count = int(plan_tier.replace('sms_', ''))
                    cursor.execute(
                        "UPDATE leagues SET max_players = %s WHERE id = %s",
                        (player_count, league_id)
                    )

                conn.commit()

        logging.info(f"Checkout completed: user {user_id}, plan {plan_tier}, sub {stripe_sub_id}")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing checkout.session.completed: {e}")
    finally:
        cursor.close()
        conn.close()


def _on_subscription_updated(subscription):
    """Handle subscription updates (plan changes, status changes)."""
    from auth import get_db_connection

    stripe_sub_id = subscription.get('id') or subscription.id
    new_status = subscription.get('status', 'active')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Update the price if it changed
        items_data = subscription.get('items', {}).get('data', [])
        price_id = items_data[0]['price']['id'] if items_data else None

        # Safely get current_period_end (can be int timestamp or None)
        period_end = subscription.get('current_period_end')
        cancel_at_end = subscription.get('cancel_at_period_end', False)

        if period_end:
            cursor.execute("""
                UPDATE subscriptions SET
                    status = %s,
                    current_period_end = to_timestamp(%s),
                    cancel_at_period_end = %s,
                    stripe_price_id = COALESCE(%s, stripe_price_id),
                    updated_at = CURRENT_TIMESTAMP
                WHERE stripe_subscription_id = %s
            """, (new_status, period_end, cancel_at_end, price_id, stripe_sub_id))
        else:
            cursor.execute("""
                UPDATE subscriptions SET
                    status = %s,
                    cancel_at_period_end = %s,
                    stripe_price_id = COALESCE(%s, stripe_price_id),
                    updated_at = CURRENT_TIMESTAMP
                WHERE stripe_subscription_id = %s
            """, (new_status, cancel_at_end, price_id, stripe_sub_id))

        conn.commit()
        logging.info(f"Subscription updated: {stripe_sub_id} -> status={new_status}")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing subscription.updated: {e}")
    finally:
        cursor.close()
        conn.close()


def _on_subscription_deleted(subscription):
    """Handle subscription cancellation — mark leagues as lapsed."""
    from auth import get_db_connection

    stripe_sub_id = subscription['id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE subscriptions SET status = 'canceled', updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = %s
        """, (stripe_sub_id,))

        # Mark all assigned leagues as needing lapsed notification
        cursor.execute("""
            UPDATE leagues SET lapsed_notified = FALSE
            WHERE id IN (
                SELECT sl.league_id FROM subscription_leagues sl
                JOIN subscriptions s ON s.id = sl.subscription_id
                WHERE s.stripe_subscription_id = %s
            )
        """, (stripe_sub_id,))

        conn.commit()
        logging.info(f"Subscription deleted: {stripe_sub_id} — leagues marked for lapsed notification")

    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing subscription.deleted: {e}")
    finally:
        cursor.close()
        conn.close()


def _on_invoice_payment_failed(invoice):
    """Handle failed payment — set subscription to past_due."""
    from auth import get_db_connection

    stripe_sub_id = invoice.get('subscription')
    if not stripe_sub_id:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE subscriptions SET status = 'past_due', updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = %s
        """, (stripe_sub_id,))
        conn.commit()
        logging.info(f"Invoice payment failed for subscription: {stripe_sub_id}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing invoice.payment_failed: {e}")
    finally:
        cursor.close()
        conn.close()


def _on_invoice_paid(invoice):
    """Handle successful payment — restore subscription if was past_due."""
    from auth import get_db_connection

    stripe_sub_id = invoice.get('subscription')
    if not stripe_sub_id:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE subscriptions SET status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = %s AND status = 'past_due'
        """, (stripe_sub_id,))

        if cursor.rowcount > 0:
            # Reset lapsed_notified for assigned leagues
            cursor.execute("""
                UPDATE leagues SET lapsed_notified = FALSE
                WHERE id IN (
                    SELECT sl.league_id FROM subscription_leagues sl
                    JOIN subscriptions s ON s.id = sl.subscription_id
                    WHERE s.stripe_subscription_id = %s
                )
            """, (stripe_sub_id,))
            logging.info(f"Subscription restored from past_due: {stripe_sub_id}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"Error processing invoice.paid: {e}")
    finally:
        cursor.close()
        conn.close()
