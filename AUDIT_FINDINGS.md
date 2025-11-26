# Cloud Deployment Audit - Missing Features & Logic

## CRITICAL ISSUES

### 1. ❌ Missing Wordle Number Validation (SECURITY RISK)
**Location:** `twilio_webhook_app.py` - `extract_wordle_score()`
**Issue:** Accepts ANY Wordle number, no validation
**Proven Script:** `integrated_auto_update_multi_league.py` lines 901-907
**Fix Needed:** Only accept TODAY's or YESTERDAY's Wordle number

```python
# MISSING FROM CLOUD:
if wordle_num == today_wordle:
    logging.info(f"VALIDATED: This is today's Wordle #{today_wordle}")
elif wordle_num == yesterday_wordle:
    logging.info(f"VALIDATED: This is yesterday's Wordle #{yesterday_wordle}")
else:
    logging.info(f"REJECTED: Wordle #{wordle_num} is neither today's ({today_wordle}) nor yesterday's ({yesterday_wordle})")
    continue
```

### 2. ✅ FIXED: Reaction Filtering
**Status:** NOW COMPLETE - filters all reaction types

### 3. ✅ FIXED: Database Schema Issues
**Status:** FIXED - added `emoji_pattern` column and unique constraint to `latest_scores`

---

## WEEKLY TOTALS LOGIC

### Comparison: Proven vs Cloud

**Proven Script (`update_tables_preserve_structure.py` lines 427-565):**
- ✅ Calculates best 5 scores
- ✅ Tracks thrown out scores
- ✅ Eligibility check (5+ valid scores)
- ✅ Daily scores by weekday (Mon-Sun)
- ✅ Handles X scores as 7
- ✅ CSS class assignment for scores
- ✅ Sorting: eligible first, then by total, then by valid games

**Cloud Script (`league_data_adapter.py` lines 142-215):**
- ✅ Calculates best 5 scores
- ✅ Tracks thrown out scores
- ✅ Handles X scores as 7
- ✅ Daily scores by Wordle number (converted to day names in HTML)
- ✅ CSS class assignment in HTML generator
- ❌ **SORTING MISMATCH:** Doesn't separate eligible/ineligible first!

### ISSUE: Sorting Logic Mismatch
**Proven:** Eligible players (5+ scores) ALWAYS appear first, sorted by score
**Cloud:** All players sorted by game count, then score (no eligible/ineligible separation)

**Impact:** Players with 4 games could appear above players with 5 games if they have a better score
**Fix Needed:** Update `html_generator_v2.py` lines 133-138 to match proven sorting

---

## SEASON TABLE LOGIC

### Status: NEEDS FULL AUDIT

**Proven Script:** `update_tables_preserve_structure.py` has season table logic
**Cloud Script:** `update_tables_cloud.py` has weekly winners logic

**Questions:**
1. Does cloud track season winners correctly?
2. Monday reset for new week?
3. Season reset logic?
4. Weekly winner calculation matches?

---

## ALL-TIME STATS

**Proven Script (`update_tables_preserve_structure.py`):**
- Has reset_date logic
- Filters scores after specific date
- Detailed stats calculation

**Cloud Script (`league_data_adapter.py` lines 217-265):**
- Simple AVG calculation
- No reset_date filtering
- May be missing features

**Action:** Compare all-time stats logic in detail

---

## DAILY/WEEKLY RESET

**Proven Script:** Has sophisticated reset logic
**Cloud Script (`scheduled_tasks.py`):**
- Daily reset clears `latest_scores`
- Date-aware (won't reset twice)
- Triggers pipeline

**Questions:**
1. Weekly reset on Monday?
2. Season reset logic?
3. Weekly winner finalization?

---

## HTML GENERATION

**Proven Script:** `update_tables_preserve_structure.py` has detailed HTML update functions
**Cloud Script:** `html_generator_v2.py`

**Need to compare:**
1. Latest scores display format
2. Weekly totals table structure
3. Season table structure
4. All-time stats display
5. CSS classes and styling
6. Highlighting logic (winners, eligible players)

---

## FIXES COMPLETED

1. ✅ **Wordle number validation** - Only accepts today/yesterday
2. ✅ **Reaction filtering** - All reaction types ignored
3. ✅ **Weekly totals sorting** - Eligible players first, then by score
4. ✅ **Database schema** - Added emoji_pattern column and constraints

## STILL TO AUDIT

1. ⏳ **Season table HTML generation** - Compare proven vs cloud
2. ✅ **All-time stats** - reset_date is FUTURE FEATURE (admin panel), not needed now
3. ⏳ **Weekly reset logic** - Monday reset behavior
4. ⏳ **Daily reset** - Verify it doesn't clear permanent scores
5. ⏳ **Edge cases** - X scores display, missing days, etc.

## FUTURE FEATURES (Not Needed Now)

1. **reset_date filtering** - For admin panel where users can reset leagues
   - Reset seasons but keep all-time stats
   - Reset all-time but keep seasons
   - Full league reset
   - User wants this for future league management UI

## NEXT STEPS

1. Compare season table HTML generation
2. Verify all-time stats calculation matches
3. Check Monday weekly reset logic
4. Test edge cases (X scores, missing days, etc.)

---

## TEST SCENARIOS NEEDED

1. Post old Wordle number (should reject)
2. Post X/6 score (should handle as 7)
3. Player with <5 scores (should show as ineligible)
4. Weekly winner with exactly 5 scores
5. Thrown out scores display
6. Monday reset behavior
7. Season winner calculation
