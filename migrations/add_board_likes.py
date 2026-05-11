#!/usr/bin/env python3
"""Add likes table for message board posts and replies.

Creates:
    board_likes table -- one like per user per post/reply

Idempotent -- safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_board_likes.py
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_likes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            post_id INTEGER REFERENCES board_posts(id) ON DELETE CASCADE,
            reply_id INTEGER REFERENCES board_replies(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT one_like_per_user_post UNIQUE (user_id, post_id),
            CONSTRAINT one_like_per_user_reply UNIQUE (user_id, reply_id),
            CONSTRAINT like_target_check CHECK (
                (post_id IS NOT NULL AND reply_id IS NULL) OR
                (post_id IS NULL AND reply_id IS NOT NULL)
            )
        )
    """)
    print("Created table board_likes (if not exists)")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_board_likes_post ON board_likes(post_id) WHERE post_id IS NOT NULL")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_board_likes_reply ON board_likes(reply_id) WHERE reply_id IS NOT NULL")
    print("Created indexes (if not exists)")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    main()
