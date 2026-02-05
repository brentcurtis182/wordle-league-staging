# Cloud Deployment Cleanup Analysis

## CORE FILES (DO NOT MOVE - Required for production)

### Main Application
- `twilio_webhook_app.py` - Main Flask app (all routes, webhooks)
- `Procfile` - Railway startup command
- `requirements.txt` - Python dependencies
- `railway.json` - Railway config
- `railway.cron.json` - Cron job config

### Core Modules (imported by main app)
- `auth.py` - User authentication
- `dashboard.py` - Dashboard UI rendering
- `slack_integration.py` - Slack bot integration
- `discord_integration.py` - Discord bot integration
- `update_pipeline.py` - Score update pipeline
- `league_data_adapter.py` - Database queries for league data
- `html_generator_v2.py` - Generates leaderboard HTML
- `image_generator.py` - Generates weekly/season images
- `message_router.py` - AI message routing
- `season_management.py` - Season tracking
- `table_aggregation.py` - Stats aggregation
- `weekly_winners_adapter.py` - Weekly winner calculations

### Scheduled Tasks (Railway cron jobs)
- `scheduled_tasks.py` - Daily midnight reset
- `sunday_race_update.py` - Sunday race updates
- `update_tables_cloud.py` - Full league update logic
- `railway.sunday-cron.json` - Sunday cron config
- `railway.sunday.json` - Sunday job config

### Static Assets (served by app)
- `styles.css` - Leaderboard styles
- `script.js` - Leaderboard scripts
- `tabs.js` - Tab switching
- `wordplayLOGO.png` - Logo image
- `Marcellus-Regular.ttf` - Font file

### Database
- `schema.sql` - Database schema reference
- `migrations/` - Database migrations folder

---

## LIKELY SAFE TO MOVE (One-off scripts)

### Bulk Insert Scripts (historical data imports)
- `bulk_insert_league1_scores.py`
- `bulk_insert_league1_scores_v2.py`
- `bulk_insert_league4_scores.py`
- `insert_league4_scores.py`
- `force_insert_league1.py`
- `force_insert_league3.py`

### Migration Scripts (one-time league setup)
- `migrate_league1.py`
- `migrate_league3.py`
- `migrate_league4.py`
- `add_league7.py`
- `import_league4_history.py`
- `import_league4_history_local.py`

### Data Extraction Scripts
- `extract_league1_data.py`
- `extract_league3_data.py`
- `extract_league4_data.py`
- `extract_output.txt`

### Restore/Fix Scripts (emergency recovery)
- `restore_scores.py`
- `restore_nov30.py`
- `restore_today.py`
- `restore_todays_scores.py`
- `restore_league4_dec2.py`
- `fix_jeremy_score.py`
- `fix_jeremy_endpoint.py`
- `fix_jeremy.sql`
- `delete_week_1618.py`

### Check/Debug Scripts
- `check_scores.py`
- `check_league4_scores.py`
- `check_table_schema.py`
- `check_weekly_winners_db.py`
- `check_last_week_scores.py`
- `check_and_clean_winners.py`
- `calculate_weekly_winners.py`

### Database Setup Scripts
- `create_missing_tables.py`
- `add_ai_messaging_columns.py`
- `update_conversation_names.py`
- `update_conversation_sids.py`

### Test Files
- `test_local.py`
- `test_image_send.py`
- `test_league7.html`
- `test_output.html`
- `test_output_script.js`
- `test_output_styles.css`
- `test_output_tabs.js`

### Historical Data Files
- `league1_historical_scores.json`
- `league3_historical_scores.json`
- `league4_historical_scores.json`

### Utility Scripts
- `trigger_update.py`
- `trigger_update.ps1`

---

## LEGACY (No longer used)
- `github_publisher.py` - Was for GitHub Pages, now serving from Railway
- `html_generator.py` - Old version, replaced by html_generator_v2.py
- `league6_beta.html` - Old test file

---

## DOCUMENTATION (Keep in root)
- `README.md`
- `QUICKSTART.md`
- `DEPLOYMENT_GUIDE.md`
- `PIPELINE_COMPLETE.md`
- `PRODUCT_ROADMAP.md`
- `AUDIT_FINDINGS.md`
- `CORRECTED_SETUP.md`

---

## Config Files (Keep in root)
- `.env.railway`
- `.gitignore`
