"""Deterministic fact-check guard for the Sunday race update.

The Sunday message is written by an LLM for personality/flair, but the LLM has
historically inflated season win counts (saying "3rd win" when it was the 2nd)
and invented promotion/clinch drama that wasn't real. This module checks the
generated message against the AUTHORITATIVE deterministic scenario text that the
code already builds, and reports factual violations so the caller can re-roll or
fall back to a clean template.

Design goals:
- Catch the two real bug classes: (1) win-count INFLATION, (2) INVENTED
  season/promotion/relegation stakes.
- Very low false-positive rate, so 99% of messages pass through untouched and
  keep their original voice/emojis.
- Pure functions — unit-testable without the clock, DB, or OpenAI.
"""
import re

# "2nd win", "3 rd win", etc.
_ORDINAL_WIN_RE = re.compile(r'(\d+)\s*(?:st|nd|rd|th)\s+win', re.IGNORECASE)
# "second win", "third win"
_WORD_ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
             'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10}
_WORD_ORD_RE = re.compile(r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+win',
                          re.IGNORECASE)
# division phrasing "now has 2"
_NOW_HAS_RE = re.compile(r'now has (\d+)', re.IGNORECASE)

# Season/promotion/relegation language the AI must not use unless the scenario raised it.
_STAKES_PRESENT_RE = re.compile(r'SEASON STAKES|SEASON CLINCH|Promotion|Relegation', re.IGNORECASE)
_CLAIMED_STAKES_RE = re.compile(
    r'clinch|win[s]? the season|take[s]? the season|season (?:champ|title|victory)|promot|relegat',
    re.IGNORECASE)


def _ordinals_in(text):
    nums = {int(m) for m in _ORDINAL_WIN_RE.findall(text)}
    nums |= {_WORD_ORD[m.lower()] for m in _WORD_ORD_RE.findall(text)}
    nums |= {int(m) for m in _NOW_HAS_RE.findall(text)}
    return nums


def allowed_win_counts(scenario_text):
    """The set of win-count numbers the deterministic scenario actually states."""
    return _ordinals_in(scenario_text or "")


def stakes_allowed(scenario_text):
    """True if the scenario legitimately raised season/promotion/relegation stakes."""
    return bool(_STAKES_PRESENT_RE.search(scenario_text or ""))


def find_violations(message, scenario_text):
    """Return a list of human-readable factual violations (empty = message is clean).

    Conservative: only flags win-count INFLATION (a claimed count higher than the
    data supports) and stakes language when the scenario raised none.
    """
    issues = []
    if not scenario_text:
        return issues  # nothing authoritative to check against — fail open

    allowed = allowed_win_counts(scenario_text)
    claimed = _ordinals_in(message)
    if allowed:
        ceiling = max(allowed)
        for n in claimed:
            if n > ceiling:
                issues.append(f"claims '{n}th win' but the data supports at most {ceiling} ({sorted(allowed)})")

    if not stakes_allowed(scenario_text) and _CLAIMED_STAKES_RE.search(message):
        issues.append("mentions clinch/promotion/relegation but the scenario raised no season stakes")

    return issues


def build_fallback_message(scenario_text):
    """Deterministic, factually-correct message built from the scenario text.

    Used only when the LLM repeatedly fails the fact check. Less flair than an AI
    message, but the scenario text is already readable and complete, so it still
    reads as a real update — just plainer.
    """
    text = (scenario_text or "").strip()
    if not text:
        return text
    prefix = "🏆 " if "RACE OVER" in text else "📊 "
    return prefix + text
