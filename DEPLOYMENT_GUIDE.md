# Wordle League Cloud Deployment Guide

## 🚀 Quick Start

This guide will help you deploy the Wordle League Twilio webhook to Railway.

## Prerequisites

- Railway account (https://railway.app) - Free tier available
- GitHub account
- Twilio account with phone number: (858) 666-6827

## Step 1: Create Railway Project

1. Go to https://railway.app and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account if not already connected
5. Select the `wordle-league` repository
6. Railway will detect the `cloud_deployment` folder

## Step 2: Add PostgreSQL Database

1. In your Railway project dashboard, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically create and configure the database
4. **Important**: Railway auto-populates these environment variables:
   - `PGHOST`
   - `PGDATABASE`
   - `PGUSER`
   - `PGPASSWORD`
   - `PGPORT`

## Step 3: Configure Environment Variables

In Railway project settings → Variables tab, add these:

```
TWILIO_ACCOUNT_SID=<YOUR_TWILIO_ACCOUNT_SID>
TWILIO_AUTH_TOKEN=<YOUR_TWILIO_AUTH_TOKEN>
TWILIO_PHONE_NUMBER=+18586666827
GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
GITHUB_USERNAME=brentcurtis182
GITHUB_REPO_NAME=wordle-league
GITHUB_PAGES_BRANCH=gh-pages
```

**Note**: Do NOT add the PG* variables - Railway handles those automatically.

## Step 4: Initialize Database Schema

1. In Railway, click on your PostgreSQL database
2. Click the "Query" tab
3. Copy the entire contents of `schema.sql` from this folder
4. Paste into the query editor
5. Click "Run Query"
6. Verify success message appears
7. Run this query to confirm players were added:
   ```sql
   SELECT * FROM players WHERE league_id = 6;
   ```
   You should see Brent, Matt, Rob, and Jason.

## Step 5: Deploy the Application

1. Railway will automatically deploy when you push to GitHub
2. Or click "Deploy" in the Railway dashboard
3. Wait for deployment to complete (usually 2-3 minutes)
4. Check the "Deployments" tab for status
5. Once deployed, click "View Logs" to monitor activity
6. Note your app URL (e.g., `wordle-league-production.up.railway.app`)

## Step 6: Configure Twilio Conversations Webhook

**CRITICAL**: You're using Twilio Conversations (group MMS threads), NOT simple phone number webhooks!

1. Go to Twilio Console: https://console.twilio.com
2. Navigate to: **Conversations** → **Services**
3. Click on your Messaging Service: **"Wordle League Group Text Threads"**
4. Click the **Webhooks** tab
5. Configure Post-Event Webhook:
   - **Post-Event URL**: `https://your-app-name.up.railway.app/webhook`
   - **Post-webhooks**: Check **onMessageAdded** ✅
   - Leave **Pre-Event URL** blank (or use for other features)
6. Click "Save"

**DO NOT configure the phone number's "A MESSAGE COMES IN" webhook** - that's for simple SMS only. Your setup uses Conversations for group thread functionality.

## Step 7: Test the System

### Test 1: Health Check
Visit in browser: `https://your-app-name.up.railway.app/health`

Should return:
```json
{"status": "healthy", "timestamp": "2025-11-23T..."}
```

### Test 2: Send Test SMS
From your phone (858-735-9353), text to **(858) 666-6827**:
```
Wordle 1,618 4/6 ⬛🟩⬛⬛⬛ ⬛⬛🟨⬛⬛ 🟨🟩🟨⬛🟩 🟩🟩🟩🟩🟩
```

**Note**: The webhook runs in SILENT MODE - you will NOT receive an SMS reply.  
This prevents spam in the text thread. Check Railway logs instead (see Test 4 below).

### Test 3: Verify Database
In Railway PostgreSQL Query tab:
```sql
SELECT p.name, s.wordle_number, s.score, s.timestamp
FROM scores s
JOIN players p ON s.player_id = p.id
WHERE p.league_id = 6
ORDER BY s.timestamp DESC
LIMIT 5;
```

### Test 4: Check Application Logs
In Railway dashboard → Your App → Logs

You should see:
```
Received SMS from +18587359353: Wordle 1,618 4/6...
Extracted single-line emoji pattern, converted to 4 rows
Inserted new score for Brent, Wordle #1618
```

## Troubleshooting

### Issue: Webhook Not Receiving Messages

**Check:**
- Twilio webhook URL is correct (include `/webhook` at end)
- Railway app is deployed and running (green status)
- Check Railway logs for incoming requests

**Fix:**
- Verify Twilio webhook configuration
- Test health endpoint first
- Check Twilio debugger: https://console.twilio.com/us1/monitor/logs/debugger

### Issue: Database Connection Errors

**Check:**
- PostgreSQL service is running in Railway
- Environment variables are set correctly
- `schema.sql` was executed successfully

**Fix:**
- Restart PostgreSQL service in Railway
- Re-run `schema.sql`
- Check Railway logs for specific error messages

### Issue: Score Not Saving

**Check:**
- Player phone number matches `PHONE_MAPPINGS` in `twilio_webhook_app.py`
- Player exists in database (league_id = 6)
- Wordle number is today's number

**Fix:**
- Run query: `SELECT * FROM players WHERE league_id = 6;`
- Check logs for "Player not found" or "old_score" messages
- Verify phone number format (with/without country code)

### Issue: Wrong Wordle Number Rejected

**Check:**
- Today's Wordle number calculation
- Reference date: Wordle #1503 = July 31, 2025

**Fix:**
- Verify current date
- Check logs for "only today's Wordle #XXXX is accepted"
- Update reference date if needed in `twilio_webhook_app.py`

## Monitoring

### Health Check Endpoint
`GET https://your-app-name.up.railway.app/health`

Returns app status and timestamp.

### View Application Logs
Railway Dashboard → Your App → Logs

Filter by:
- "Received SMS" - incoming messages
- "Inserted new score" - successful saves
- "Error" - problems

### Database Queries

**Recent scores:**
```sql
SELECT p.name, s.wordle_number, s.score, s.date
FROM scores s
JOIN players p ON s.player_id = p.id
WHERE p.league_id = 6
ORDER BY s.date DESC, s.timestamp DESC
LIMIT 10;
```

**Player statistics:**
```sql
SELECT p.name, COUNT(*) as total_scores, AVG(s.score) as avg_score
FROM scores s
JOIN players p ON s.player_id = p.id
WHERE p.league_id = 6
GROUP BY p.name
ORDER BY avg_score;
```

## Cost Estimate

**Railway Hobby Plan**: ~$5/month
- Includes PostgreSQL database
- 500 hours/month execution time
- $5 credit/month included
- More than enough for this application

**Free Tier Available:**
- $5 credit/month
- Should cover League 6 beta testing
- Upgrade only if you exceed limits

## Next Steps

Once League 6 is working successfully:

1. **Test for 1-2 weeks** with beta players
2. **Verify data accuracy** - compare with expected results
3. **Monitor costs** - ensure within budget
4. **Migrate historical data** from SQLite (optional)
5. **Add other leagues** - update phone mappings, add to Twilio threads
6. **Shut down server PC** - no more Google Voice!

## Support

### Railway Documentation
- https://docs.railway.app

### Twilio Documentation
- https://www.twilio.com/docs/sms/quickstart/python

### PostgreSQL Documentation
- https://www.postgresql.org/docs/

## Success Checklist

- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Environment variables configured
- [ ] Database schema initialized
- [ ] Application deployed successfully
- [ ] Twilio webhook configured
- [ ] Health check returns 200 OK
- [ ] Test SMS sent and received confirmation
- [ ] Score visible in database
- [ ] Logs show successful processing

## 🎉 Congratulations!

Your Wordle League cloud deployment is complete! The system is now:
- ✅ Running 24/7 in the cloud
- ✅ Receiving SMS via Twilio
- ✅ Storing scores in PostgreSQL
- ✅ No more Google Voice authentication issues!

Enjoy your maintenance-free Wordle League! 🚀
