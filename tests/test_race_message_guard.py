"""Unit tests for the Sunday race message fact-check guard.

Pure tests — no clock, DB, or OpenAI. They feed the deterministic scenario text
(what the code builds) plus a candidate AI message and assert the guard's verdict.
"""
from race_message_guard import (
    find_violations, allowed_win_counts, stakes_allowed, build_fallback_message,
)


# --- the real bugs that triggered this work (must be CAUGHT) ---

def test_pal_inflation_caught():
    # PAL: scenario says Fuzwuz 2nd / Vox 1st; AI inflated to 3rd/2nd
    scenario = ("RACE OVER! Fuzwuz and Vox are tied at 13 and will share the weekly win! "
                "This makes it Fuzwuz's 2nd win and Vox's 1st win this season.")
    msg = "🎉 RACE OVER! Fuzwuz and Vox tie at 13! Fuzwuz marks their 3rd win, Vox their 2nd! 🏆"
    assert find_violations(msg, scenario)  # non-empty -> caught


def test_tiny_words_inflation_caught():
    # League 19: Rally's 1st win, AI said 2nd
    scenario = "RACE OVER! Rally wins the week with 18! This is their 1st win this season."
    msg = "🎉 RACE OVER! Rally triumphs with 18! Rally marks their 2nd win this season! 🌟"
    assert find_violations(msg, scenario)


def test_invented_promotion_caught():
    # Pickle Party Div II: no stakes in scenario, AI invented promotion
    scenario = ("Division II: RACE OVER! Brent and Dani are tied at 17 and will share the weekly "
                "win! (Season wins: Brent now has 1, Dani now has 1)")
    msg = ("Division II: RACE OVER! Brent and Dani tie at 17! Both now have 1 win. "
           "With another win, either could secure promotion to Division I! 🚀")
    assert find_violations(msg, scenario)


# --- legit messages that must PASS untouched (no false positives) ---

def test_correct_counts_pass():
    scenario = ("RACE OVER! Fuzwuz and Vox are tied at 13 and will share the weekly win! "
                "This makes it Fuzwuz's 2nd win and Vox's 1st win this season.")
    msg = "🎉 RACE OVER! Fuzwuz & Vox tie at 13! Fuzwuz's 2nd win, Vox's 1st! 🏆"
    assert find_violations(msg, scenario) == []


def test_legit_promotion_passes():
    scenario = ("Division I: Jess could clinch Division I Season 9 with a win! SEASON STAKES: "
                "Jess has 2 wins (one away).")
    msg = "Division I: SEASON STAKES! Jess could clinch Season 9 with a win — their promotion run is on! 🔥"
    assert find_violations(msg, scenario) == []


def test_legit_clinch_passes():
    scenario = ("RACE OVER! Brent wins the week with 17! SEASON CLINCH: Brent clinches Season 8 "
                "with their 4th win!")
    msg = "🏆 RACE OVER! Brent takes the week with 17 and CLINCHES Season 8 with their 4th win! 🎊"
    assert find_violations(msg, scenario) == []


def test_word_ordinal_inflation_caught():
    scenario = "RACE OVER! Rally wins the week with 18! This is their 1st win this season."
    msg = "RACE OVER! Rally wins with 18 — their second win this season! 🌟"
    assert find_violations(msg, scenario)


def test_lower_ordinal_not_flagged():
    # mentioning a number at/below the supported max is fine (contextual)
    scenario = ("RACE OVER! Fuzwuz and Vox are tied at 13 and will share the weekly win! "
                "This makes it Fuzwuz's 2nd win and Vox's 1st win this season.")
    msg = "RACE OVER! Fuzwuz & Vox share it — Vox grabs their 1st win! 🎉"
    assert find_violations(msg, scenario) == []


def test_no_scenario_fails_open():
    assert find_violations("anything at all, 5th win, promotion!", None) == []
    assert find_violations("anything", "") == []


def test_this_season_not_flagged_as_stakes():
    # "this season" must NOT trip the clinch/season detector
    scenario = "RACE OVER! Rally wins the week with 18! This is their 1st win this season."
    msg = "RACE OVER! Rally wins with 18 — their 1st win this season! Nice work! 🎉"
    assert find_violations(msg, scenario) == []


# --- helper-level checks ---

def test_allowed_win_counts_extraction():
    s = "This makes it Fuzwuz's 2nd win and Vox's 1st win this season."
    assert allowed_win_counts(s) == {1, 2}
    assert allowed_win_counts("Brent now has 1, Dani now has 1") == {1}


def test_stakes_detection():
    assert stakes_allowed("SEASON STAKES: ...") is True
    assert stakes_allowed("...Promotion: Jess...") is True
    assert stakes_allowed("RACE OVER! plain weekly win.") is False


def test_fallback_message_is_factual():
    scenario = "RACE OVER! Rally wins the week with 18! This is their 1st win this season."
    out = build_fallback_message(scenario)
    assert "Rally" in out and "1st win" in out
    assert find_violations(out, scenario) == []  # the template must pass its own check
