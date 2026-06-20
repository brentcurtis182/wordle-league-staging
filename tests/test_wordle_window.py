"""Unit tests for the timezone-aware Wordle submission window.

Pure tests: they pass a fixed Pacific datetime into acceptable_wordle_numbers(),
so they don't depend on the real clock or the database.
"""
import pytz
from datetime import datetime

from league_data_adapter import acceptable_wordle_numbers, calculate_wordle_number

PT = pytz.timezone('America/Los_Angeles')


def _pt(y, m, d, hh, mm=0):
    """A Pacific-localized datetime (DST-aware)."""
    return PT.localize(datetime(y, m, d, hh, mm))


def test_midday_accepts_only_today():
    now = _pt(2026, 6, 20, 12, 0)
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n}


def test_forward_buffer_opens_at_9pm():
    now = _pt(2026, 6, 20, 21, 0)  # exactly 9:00pm PT — 3h before midnight
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n, n + 1}


def test_forward_buffer_closed_just_before_9pm():
    now = _pt(2026, 6, 20, 20, 59)
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n}


def test_backward_buffer_open_after_midnight():
    now = _pt(2026, 6, 20, 0, 30)  # 12:30am PT
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n, n - 1}


def test_backward_buffer_open_just_before_3am():
    now = _pt(2026, 6, 20, 2, 59)
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n, n - 1}


def test_backward_buffer_closed_at_3am():
    now = _pt(2026, 6, 20, 3, 0)
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now) == {n}


def test_east_coast_can_post_next_puzzle_early():
    # 9:01pm PT == 12:01am ET next day: ET player has tomorrow's puzzle (#N+1)
    now = _pt(2026, 6, 20, 21, 1)
    n = calculate_wordle_number(now.date())
    assert (n + 1) in acceptable_wordle_numbers(now)


def test_hawaii_can_post_prior_puzzle_late():
    # ~2:30am PT (summer) == ~11:30pm Hawaii: still finishing yesterday's puzzle
    now = _pt(2026, 6, 21, 2, 30)
    n = calculate_wordle_number(now.date())
    assert (n - 1) in acceptable_wordle_numbers(now)


def test_never_more_than_two_adjacent_numbers():
    for hh in range(24):
        acc = acceptable_wordle_numbers(_pt(2026, 6, 20, hh, 0))
        assert len(acc) <= 2
        assert max(acc) - min(acc) <= 1


def test_custom_buffer_hours():
    # With a 1h buffer, 9pm should NOT open the forward window yet
    now = _pt(2026, 6, 20, 21, 0)
    n = calculate_wordle_number(now.date())
    assert acceptable_wordle_numbers(now, buffer_hours=1) == {n}
    # but 11:30pm should
    late = _pt(2026, 6, 20, 23, 30)
    assert acceptable_wordle_numbers(late, buffer_hours=1) == {n, n + 1}
