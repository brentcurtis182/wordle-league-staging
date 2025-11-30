# Wordle League - Product Roadmap

## Current Status (Dec 2025)
- ✅ **Beta Deployment**: Leagues 6 & 7 running on Railway + GitHub Pages
- ✅ **Core Features**: Score tracking, weekly winners, season tracking, daily/weekly resets
- ✅ **Automation**: Twilio webhook, automated HTML generation, cron-based resets

---

## Phase 1: League Management UI
**Goal**: Self-service league creation and management

### Features:
- **Admin Dashboard** (`admin.html`)
  - Protected by authentication (password/OAuth)
  - Master view: See all active leagues
  - Per-league view: Click into any league to edit
  
- **Create League**
  - Modal/form with inputs:
    - League name
    - Player names
    - Phone numbers
    - Season settings (configurable)
  - "Create" button triggers backend API
  - Auto-generates league page and publishes to GitHub Pages
  
- **Configurable League Settings**
  - Weekly wins needed for season (default: 5)
  - Season length (weeks)
  - Minimum games for eligibility (default: 5)
  - League display name
  - Custom styling/branding (optional)
  
- **Edit League**
  - Modify league settings
  - Add/remove players
  - Update phone numbers
  - Set player nicknames
  - Archive/delete league

### Technical Implementation:
- **Frontend**: React or vanilla JS with forms
- **Backend API Endpoints**:
  - `POST /api/create-league`
  - `GET /api/leagues` (list all)
  - `GET /api/league/{id}` (get details)
  - `PUT /api/league/{id}` (update)
  - `DELETE /api/league/{id}` (archive)
  - `POST /api/league/{id}/player` (add player)
  - `DELETE /api/league/{id}/player/{player_id}` (remove player)
- **Auth**: Simple password or OAuth integration
- **Database**: Extend existing PostgreSQL schema with league settings table

### User Roles:
- **Master Admin**: Can see/edit all leagues (you)
- **League Admin**: Can only edit their own league (future)
- **Player**: View-only access (future)

---

## Phase 2: Player Management
**Goal**: Easy player administration

### Features:
- **Add Players**
  - Single player add (name + phone)
  - Bulk import (CSV upload)
  - Auto-detect duplicates
  
- **Edit Players**
  - Update phone numbers
  - Set/change nicknames
  - Mark as active/inactive
  
- **Player Stats**
  - Historical performance
  - All-time stats
  - Cross-league stats (if player in multiple leagues)
  
- **Remove Players**
  - Soft delete (preserve historical data)
  - Hard delete (remove all data - with confirmation)

### Technical Implementation:
- **API Endpoints**:
  - `POST /api/player` (create)
  - `PUT /api/player/{id}` (update)
  - `DELETE /api/player/{id}` (remove)
  - `GET /api/player/{id}/stats` (get stats)
- **Database**: Player status field, soft delete flag

---

## Phase 3: Opt-In Compliance & Legal
**Goal**: TCPA compliance for SMS messaging

### Features:
- **Automated Opt-In Flow**
  - When new player added, Twilio bot sends:
    - "Welcome to [League Name] Wordle League! Reply YES to opt in to score tracking."
  - Track opt-in status in database
  - Only process scores from opted-in numbers
  
- **Opt-Out Handling**
  - "Reply STOP to opt out anytime"
  - Auto-process STOP messages
  - Mark player as opted-out in database
  - Stop processing their scores
  
- **Compliance Logging**
  - Log all opt-in/opt-out events with timestamps
  - Store consent records (required by law)
  - Audit trail for legal compliance
  
- **Re-Opt-In**
  - Allow opted-out players to rejoin
  - "Reply START to rejoin [League Name]"

### Technical Implementation:
- **Database Schema**:
  - `opt_in_status` field on players table
  - `consent_log` table (player_id, action, timestamp, message_sid)
- **Webhook Updates**:
  - Check opt-in status before processing scores
  - Handle STOP/START/YES keywords
- **Admin UI**:
  - View opt-in status per player
  - Manually trigger opt-in message
  - Export consent logs for compliance

### Legal Requirements:
- ✅ Express written consent before sending messages
- ✅ Clear opt-out mechanism (STOP)
- ✅ Opt-out honored immediately
- ✅ Consent records retained for 4+ years
- ✅ Privacy policy disclosure

---

## Phase 4: Multi-League Dashboard
**Goal**: Master view for users with multiple leagues

### Features:
- **Dashboard Overview**
  - Grid/list of all active leagues
  - Quick stats per league:
    - Current weekly leader
    - Last weekly winner
    - Season standings (top 3)
    - Active players count
  - One-click navigation to each league's page
  
- **Cross-League Stats** (optional)
  - Players in multiple leagues
  - Combined performance metrics
  - "Best overall player" across all leagues
  
- **Notifications** (future)
  - Weekly winner announcements
  - Season winner alerts
  - New player joined
  - Opt-out notifications

### Technical Implementation:
- **Dashboard Page** (`dashboard.html`)
  - Fetch data from all leagues via API
  - Real-time updates (optional: WebSocket)
- **API Endpoints**:
  - `GET /api/dashboard` (all leagues summary)
  - `GET /api/dashboard/stats` (cross-league stats)

---

## Phase 5: Enhanced Features (Future)
**Goal**: Advanced functionality and user experience

### Potential Features:
- **Historical Data Visualization**
  - Charts/graphs of player performance over time
  - Season-by-season comparison
  - Win/loss trends
  
- **Leaderboards**
  - All-time best scores
  - Fastest to complete (fewest days to season win)
  - Streak tracking (consecutive wins)
  
- **Social Features**
  - Player profiles
  - Achievements/badges
  - Trash talk board (moderated)
  
- **Mobile App** (long-term)
  - Native iOS/Android apps
  - Push notifications
  - In-app score submission (alternative to SMS)
  
- **Custom Branding**
  - Per-league themes/colors
  - Custom logos
  - White-label option for enterprise

---

## Migration Plan: Leagues 1-5
**Goal**: Move existing leagues from Google Voice + SQLite to Twilio + PostgreSQL

### Prerequisites:
- ✅ Monday reset (Dec 2) proves stable for Leagues 6 & 7
- ✅ Copy legacy codebase to subdirectory

### Migration Order:
1. **League 3** (first migration test)
2. **League 1** (second migration test)
3. **Leagues 2, 4, 5** (batch migration)

### Migration Process:
1. Export data from SQLite:
   - Players table
   - Scores table (all historical data)
   - Weekly winners table
   - Season winners table (if any)
2. Import to PostgreSQL (Railway)
3. Add phone mappings to webhook
4. Create Twilio conversation
5. Generate initial HTML pages
6. Publish to GitHub Pages
7. Test score submission
8. Notify players of new system

### Data Validation:
- ✅ Player count matches
- ✅ Score count matches
- ✅ Weekly winners match
- ✅ Season standings match
- ✅ All-time stats match

---

## Technical Debt & Improvements

### Code Quality:
- [ ] Add comprehensive unit tests
- [ ] Add integration tests for webhook
- [ ] Add end-to-end tests for full pipeline
- [ ] Improve error handling and logging
- [ ] Add monitoring/alerting (e.g., Sentry)

### Performance:
- [ ] Cache frequently accessed data (Redis)
- [ ] Optimize database queries
- [ ] Batch HTML generation for multiple leagues
- [ ] CDN for static assets

### Security:
- [ ] Add authentication to admin endpoints
- [ ] Rate limiting on webhook
- [ ] Input validation and sanitization
- [ ] SQL injection prevention (use parameterized queries)
- [ ] HTTPS everywhere

### DevOps:
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Automated testing on PR
- [ ] Staging environment
- [ ] Database backups (automated)
- [ ] Disaster recovery plan

---

## Success Metrics

### Phase 1 Success:
- [ ] 5+ leagues created via UI (not manual)
- [ ] Zero manual database edits needed
- [ ] League creation takes <2 minutes

### Phase 2 Success:
- [ ] Players can be added/removed without code changes
- [ ] Bulk import works for 10+ players

### Phase 3 Success:
- [ ] 100% opt-in rate for new players
- [ ] Zero TCPA violations
- [ ] Opt-out handled within 1 minute

### Phase 4 Success:
- [ ] Dashboard loads in <2 seconds
- [ ] All leagues visible at a glance
- [ ] One-click navigation works

### Overall Success:
- [ ] 10+ active leagues running simultaneously
- [ ] 100+ active players across all leagues
- [ ] 99.9% uptime
- [ ] Zero data loss incidents
- [ ] Positive user feedback

---

## Timeline (Estimated)

- **Phase 1**: 2-3 weeks (League Management UI)
- **Phase 2**: 1 week (Player Management)
- **Phase 3**: 1-2 weeks (Opt-In Compliance)
- **Phase 4**: 1 week (Multi-League Dashboard)
- **Migration**: 1 week (Leagues 1-5)

**Total**: ~6-8 weeks to full production with all legacy leagues migrated

---

## Notes

- Prioritize stability and data integrity over new features
- Test thoroughly in staging before production rollout
- Keep user experience simple and intuitive
- Document everything for future maintainability
- Consider monetization options (future):
  - Freemium model (free for 1 league, paid for multiple)
  - White-label licensing for organizations
  - Premium features (custom branding, advanced stats)

---

**Last Updated**: November 30, 2025
**Status**: Roadmap Draft - Pending Phase 1 Kickoff
