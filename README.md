# Wordle League Cloud Deployment

## Overview

This folder contains the cloud-native version of Wordle League that uses Twilio webhooks instead of Google Voice scraping.

## What's Included

- **`twilio_webhook_app.py`** - Flask app that receives SMS from Twilio
- **`schema.sql`** - PostgreSQL database schema
- **`requirements.txt`** - Python dependencies
- **`Procfile`** - Railway/Heroku process configuration
- **`railway.json`** - Railway-specific configuration
- **`.env.railway`** - Environment variable template
- **`DEPLOYMENT_GUIDE.md`** - Complete deployment instructions

## Quick Start

1. **Deploy to Railway**: Follow `DEPLOYMENT_GUIDE.md`
2. **Add PostgreSQL**: Railway will auto-configure
3. **Run schema.sql**: Initialize database tables
4. **Configure Twilio**: Point webhook to your Railway URL
5. **Test**: Send a Wordle score via SMS

## Architecture

```
Twilio SMS → Flask Webhook → PostgreSQL → (Future: Table Updates → GitHub Pages)
```

## League 6: Beta Test

This deployment starts with League 6 only:
- **Brent** - 858-735-9353
- **Matt** - 760-908-2000
- **Rob** - 760-815-6131
- **Jason** - 650-346-8822

## Key Features

- ✅ Real-time SMS processing (no polling needed)
- ✅ Handles both single-line and multi-line emoji formats
- ✅ Same database schema as existing system
- ✅ Compatible with existing HTML generation
- ✅ No authentication issues
- ✅ Runs 24/7 in the cloud
- ✅ Silent mode - no SMS replies (prevents spam)

## Testing Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PGHOST=localhost
export PGDATABASE=wordle_league
export PGUSER=postgres
export PGPASSWORD=yourpassword

# Run the app
python twilio_webhook_app.py
```

Then use ngrok to expose locally:
```bash
ngrok http 5000
```

Point Twilio webhook to the ngrok URL.

## Environment Variables

Required in Railway:
- `TWILIO_ACCOUNT_SID` - Your Twilio account SID
- `TWILIO_AUTH_TOKEN` - Your Twilio auth token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number
- `GITHUB_TOKEN` - For publishing to GitHub Pages
- `GITHUB_USERNAME` - Your GitHub username
- `GITHUB_REPO_NAME` - Repository name
- `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT` - Auto-set by Railway

## Endpoints

- `POST /webhook` - Receives SMS from Twilio
- `GET /health` - Health check
- `GET /` - Root endpoint (status)

## Next Steps

After League 6 is stable:
1. Migrate historical data from SQLite
2. Add table update scheduler
3. Add GitHub publishing
4. Migrate other leagues to Twilio
5. Decommission server PC

## Support

See `DEPLOYMENT_GUIDE.md` for detailed instructions and troubleshooting.
