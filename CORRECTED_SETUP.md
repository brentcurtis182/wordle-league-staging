# ✅ CORRECTED Setup Guide (Thanks GPT!)

## 🚨 Critical Corrections Made

### 1. Security Issue - FIXED ✅
Your tokens were exposed in chat. **Rotate immediately**:
- **Twilio**: https://console.twilio.com → Account → API Keys → Regenerate
- **GitHub**: https://github.com/settings/tokens → Regenerate

### 2. Webhook Configuration - FIXED ✅
**Wrong**: Configuring phone number's "A MESSAGE COMES IN" webhook  
**Right**: Configuring **Conversations Service** webhook

### 3. Webhook Code - FIXED ✅
Updated `twilio_webhook_app.py` to handle **Conversations JSON payload** instead of simple SMS form data.

---

## 🎯 Correct Deployment Steps

### Step 1: Rotate Tokens (DO THIS FIRST!)
1. **Twilio Auth Token**: 
   - Go to https://console.twilio.com
   - Account → API Keys & Tokens
   - Regenerate Auth Token
   - Save the new token

2. **GitHub Token**:
   - Go to https://github.com/settings/tokens
   - Find your token → Regenerate
   - Save the new token

### Step 2: Push to GitHub
```bash
cd f:\Wordle-League
git add cloud_deployment/
git commit -m "Add Railway Twilio Conversations webhook"
git push
```

### Step 3: Deploy to Railway
1. Go to https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Select `wordle-league` repository
4. Railway auto-detects and builds

### Step 4: Add PostgreSQL
1. In Railway project: "+ New"
2. "Database" → "PostgreSQL"
3. Railway auto-configures `DATABASE_URL` and `PG*` variables

### Step 5: Set Environment Variables
In Railway → Your App → Variables tab:

```
TWILIO_ACCOUNT_SID=<YOUR_TWILIO_ACCOUNT_SID>
TWILIO_AUTH_TOKEN=<YOUR_TWILIO_AUTH_TOKEN>
TWILIO_PHONE_NUMBER=+18586666827
GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
GITHUB_USERNAME=brentcurtis182
GITHUB_REPO_NAME=wordle-league
GITHUB_PAGES_BRANCH=gh-pages
```

**Use your NEW tokens from Step 1!**

### Step 6: Initialize Database
1. Railway → PostgreSQL → Query tab
2. Copy entire `schema.sql` file
3. Paste and "Run Query"
4. Verify: `SELECT * FROM players WHERE league_id = 6;`
   - Should show: Brent, Matt, Rob, Jason

### Step 7: Configure Twilio Conversations Webhook ⚠️ CRITICAL
**This is the corrected step!**

1. Twilio Console → **Conversations** → **Services**
2. Click: **"Wordle League Group Text Threads"**
3. Go to **Webhooks** tab
4. Set **Post-Event URL**: `https://your-app-name.up.railway.app/webhook`
5. Check **Post-webhooks**: ✅ **onMessageAdded**
6. Leave **Pre-Event URL** blank
7. Save

**DO NOT touch the phone number's "A MESSAGE COMES IN" setting!**  
Your phone number should already be configured with:
- Messaging Service: "Wordle League Group Text Threads"

### Step 8: Test End-to-End
From your **League 6 group thread** (with Brent, Matt, Rob, Jason + 858-666-6827), send:

```
Wordle 1618 4/6
⬛🟩⬛⬛⬛
⬛⬛🟨⬛⬛
🟨🟩🟨⬛🟩
🟩🟩🟩🟩🟩
```

**Verify in Railway Logs**:
```
Conversations webhook: onMessageAdded from +18587359353
✅ Score recorded! Brent: Wordle #1618 - 4/6
```

**Verify in PostgreSQL**:
```sql
SELECT p.name, s.wordle_number, s.score, s.date
FROM scores s
JOIN players p ON s.player_id = p.id
WHERE p.league_id = 6
ORDER BY s.timestamp DESC
LIMIT 5;
```

Should show your test score!

---

## 🔍 What Changed in the Code

### `twilio_webhook_app.py`
```python
# OLD (wrong for Conversations):
from_number = request.form.get('From', '')
message_body = request.form.get('Body', '')

# NEW (handles Conversations JSON):
if request.is_json:
    data = request.get_json()
    from_number = data.get('Author', '')
    message_body = data.get('Body', '')
    event_type = data.get('EventType', '')
else:
    # Fallback for simple SMS
    from_number = request.form.get('From', '')
    message_body = request.form.get('Body', '')
```

---

## 📊 Architecture Flow

```
Group Thread (League 6)
    ↓
Twilio Phone: (858) 666-6827
    ↓
Messaging Service: "Wordle League Group Text Threads"
    ↓
Conversations Service (CH...)
    ↓
Webhook: onMessageAdded → POST JSON
    ↓
Railway: /webhook endpoint
    ↓
Parse Wordle score
    ↓
PostgreSQL: Save to scores table
    ↓
Railway Logs: ✅ Confirmation
```

---

## ✅ Success Checklist

- [ ] Twilio Auth Token rotated
- [ ] GitHub Token rotated
- [ ] Code pushed to GitHub
- [ ] Railway app deployed
- [ ] PostgreSQL database created
- [ ] `schema.sql` executed successfully
- [ ] Environment variables set (with NEW tokens)
- [ ] **Conversations Service webhook configured** (not phone number!)
- [ ] Test message sent from group thread
- [ ] Railway logs show "✅ Score recorded!"
- [ ] PostgreSQL shows score in database

---

## 🆘 Troubleshooting

### Webhook not receiving messages?
**Check**: Conversations → Services → Webhooks → Post-Event URL is correct  
**NOT**: Phone Numbers → Messaging Configuration

### Getting form data instead of JSON?
**Check**: You configured the Conversations webhook, not the phone number webhook

### Phone number not recognized?
**Check**: `PHONE_MAPPINGS` in `twilio_webhook_app.py` matches your actual phone numbers

### Database connection error?
**Check**: Railway auto-set `DATABASE_URL` or `PG*` variables exist

---

## 🎉 Once Working

You'll have:
- ✅ Real-time score capture from group thread
- ✅ No Google Voice authentication issues
- ✅ Silent mode (no spam replies)
- ✅ Cloud-hosted 24/7
- ✅ Ready for table updates & HTML generation

**Next phase**: Build the scoring aggregation and GitHub Pages publishing!
