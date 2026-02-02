-- Migration: Add Slack and Discord integration columns to leagues table
-- Run this on the Railway Postgres database

-- Channel type: 'sms' (default/existing), 'slack', or 'discord'
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS channel_type VARCHAR(20) DEFAULT 'sms';

-- Slack-specific columns
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS slack_team_id VARCHAR(50);
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS slack_channel_id VARCHAR(50);
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS slack_bot_token TEXT;

-- Discord-specific columns
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS discord_guild_id VARCHAR(50);
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS discord_channel_id VARCHAR(50);

-- Player columns for Slack/Discord user IDs
ALTER TABLE players ADD COLUMN IF NOT EXISTS slack_user_id VARCHAR(50);
ALTER TABLE players ADD COLUMN IF NOT EXISTS discord_user_id VARCHAR(50);

-- Index for quick lookups by channel
CREATE INDEX IF NOT EXISTS idx_leagues_slack_channel ON leagues(slack_team_id, slack_channel_id) WHERE channel_type = 'slack';
CREATE INDEX IF NOT EXISTS idx_leagues_discord_channel ON leagues(discord_guild_id, discord_channel_id) WHERE channel_type = 'discord';

-- Add comment for documentation
COMMENT ON COLUMN leagues.channel_type IS 'Message channel: sms, slack, or discord';
COMMENT ON COLUMN leagues.slack_team_id IS 'Slack workspace ID (T...)';
COMMENT ON COLUMN leagues.slack_channel_id IS 'Slack channel ID (C...)';
COMMENT ON COLUMN leagues.slack_bot_token IS 'Encrypted Slack bot OAuth token for this workspace';
COMMENT ON COLUMN leagues.discord_guild_id IS 'Discord server/guild ID';
COMMENT ON COLUMN leagues.discord_channel_id IS 'Discord channel ID';
