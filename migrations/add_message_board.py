#!/usr/bin/env python3
"""Add community message board tables and nickname column.

Creates:
    board_posts table    -- community Q&A posts
    board_replies table  -- threaded replies on posts
    users.nickname       -- optional display name for the board

Idempotent -- safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_message_board.py
"""
import os
import psycopg2


def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit("DATABASE_URL not set")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Create board_posts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subject VARCHAR(200) NOT NULL,
            body TEXT NOT NULL,
            is_pinned BOOLEAN DEFAULT FALSE,
            is_faq BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("Created table board_posts (if not exists)")

    # 2. Create board_replies table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_replies (
            id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL REFERENCES board_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("Created table board_replies (if not exists)")

    # 3. Add nickname column to users
    cur.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(50) DEFAULT NULL
    """)
    print("Added column users.nickname (if not exists)")

    # 4. Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_board_posts_created ON board_posts(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_board_posts_pinned ON board_posts(is_pinned, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_board_replies_post ON board_replies(post_id, created_at)")
    print("Created indexes (if not exists)")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    main()
