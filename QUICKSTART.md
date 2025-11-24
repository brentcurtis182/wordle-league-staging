# 🚀 Wordle League Cloud - Quick Start

## What You Just Got

A complete cloud-native Wordle League system that replaces Google Voice scraping with Twilio webhooks.

## Files Created

### `cloud_deployment/` (9 files)
1. ✅ `twilio_webhook_app.py` - Flask webhook receiver
2. ✅ `schema.sql` - PostgreSQL database schema
3. ✅ `requirements.txt` - Python dependencies
4. ✅ `Procfile` - Railway process config
5. ✅ `railway.json` - Railway deployment config
6. ✅ `.env.railway` - Environment variables template
7. ✅ `DEPLOYMENT_GUIDE.md` - Full deployment instructions
8. ✅ `README.md` - Overview and architecture
9. ✅ `QUICKSTART.md` - This file!

### `Temp_Python_scripts/` (2 files)
1. ✅ `test_twilio_locally.py` - Local webhook testing
2. ✅ `migrate_sqlite_to_postgres.py` - Data migration tool

## Next Steps (5 Minutes to Deploy!)

### 1. Push to GitHub (if needed)
```bash
cd f:\Wordle-League
git add cloud_deployment/
git commit -m "Add cloud deployment for Twilio webhook"
git push
```

### 2. Deploy to Railway
1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Select `wordle-league` repository
4. Railway auto-detects the setup ✨

### 3. Add PostgreSQL
1. In Railway project, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Done! (Railway auto-configures everything)

### 4. Set Environment Variables
**⚠️ SECURITY**: Use your NEW rotated tokens (not the ones shown here - they were exposed!)

In Railway → Variables tab, paste:
```
TWILIO_ACCOUNT_SID=<YOUR_TWILIO_ACCOUNT_SID>
TWILIO_AUTH_TOKEN=<YOUR_TWILIO_AUTH_TOKEN>
TWILIO_PHONE_NUMBER=+18586666827
GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
GITHUB_USERNAME=brentcurtis182
GITHUB_REPO_NAME=wordle-league
GITHUB_PAGES_BRANCH=gh-pages
```

**Rotate tokens at**:
- Twilio: https://console.twilio.com → Account → API Keys
- GitHub: https://github.com/settings/tokens

### 5. Initialize Database
1. Railway → PostgreSQL → Query tab
2. Copy entire `schema.sql` file
3. Paste and click "Run Query"
4. Verify: `SELECT * FROM players WHERE league_id = 6;`

### 6. Configure Twilio Conversations Webhook
**IMPORTANT**: You're using Conversations (group MMS), NOT phone number webhooks!

1. Twilio Console → **Conversations** → **Services**
2. Click on: **"Wordle League Group Text Threads"** (your Messaging Service)
3. Go to **Webhooks** tab
4. Under **Post-Event URL**, set to: `https://your-app.railway.app/webhook`
5. Under **Post-webhooks**, check: **onMessageAdded**
6. Leave **Pre-Event URL** blank
7. Save

**DO NOT** configure "A MESSAGE COMES IN" on the phone number itself - that's for simple SMS, not group threads!

### 7. Test!
Text to **(858) 666-6827**:
```
Wordle 1,618 4/6 ⬛🟩⬛⬛⬛ ⬛⬛🟨⬛⬛ 🟨🟩🟨⬛🟩 🟩🟩🟩🟩🟩
```

**Note**: The webhook runs in SILENT MODE - no SMS replies are sent back.  
Check Railway logs to confirm score was saved: `✅ Score recorded! Brent: Wordle #1618 - 4/6`

## Troubleshooting

### Can't find Railway app URL?
Railway Dashboard → Your App → Settings → Domains

### Webhook not working?
Check Railway logs: Dashboard → Your App → Logs

### Database error?
Verify `schema.sql` ran successfully in PostgreSQL Query tab

### Need help?
See `DEPLOYMENT_GUIDE.md` for detailed troubleshooting

## What's Different from Server PC?

| Feature | Server PC | Cloud (Railway) |
|---------|-----------|-----------------|
| Extraction | Selenium + Google Voice | Twilio webhook |
| Database | SQLite file | PostgreSQL |
| Scheduling | Windows Task Scheduler | (Coming soon) |
| Auth Issues | Constant | None! |
| Uptime | Depends on PC | 99.9% |
| Cost | Free (your PC) | ~$5/month |

## League 6 Beta Players

- **Brent** - 858-735-9353
- **Matt** - 760-908-2000  
- **Rob** - 760-815-6131
- **Jason** - 650-346-8822

## Testing Checklist

- [ ] Railway deployed successfully
- [ ] PostgreSQL database created
- [ ] Environment variables set
- [ ] Database schema initialized
- [ ] Twilio webhook configured
- [ ] Health check works: `/health`
- [ ] Test SMS sent
- [ ] Confirmation SMS received
- [ ] Score visible in database
- [ ] Logs show successful processing

## After Beta Testing

Once League 6 works for 1-2 weeks:

1. **Migrate historical data** - Run `migrate_sqlite_to_postgres.py`
2. **Add table updates** - Port your scoring scripts
3. **Add GitHub publishing** - Automated deployment
4. **Migrate other leagues** - Add Twilio bot to threads
5. **Shut down server PC** - You're done! 🎉

## Cost Breakdown

**Railway Hobby Plan**: $5/month
- PostgreSQL database included
- 500 hours/month (more than enough)
- $5 credit/month included
- Free tier covers League 6 testing

## Support

- **Deployment**: See `DEPLOYMENT_GUIDE.md`
- **Architecture**: See `README.md`
- **Testing**: Use `test_twilio_locally.py`
- **Migration**: Use `migrate_sqlite_to_postgres.py`

## Success! 🎉

Your cloud deployment is ready. The system will:
- ✅ Receive SMS instantly via Twilio
- ✅ Parse Wordle scores (single-line or multi-line format)
- ✅ Store in PostgreSQL with same schema
- ✅ Run 24/7 with no maintenance
- ✅ Never have Google auth issues again!

**Enjoy your maintenance-free Wordle League!** 🚀
