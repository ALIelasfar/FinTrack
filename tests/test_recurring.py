"""Tests for finding recurring payments."""

from datetime import date, timedelta

import pytest

from fintrack.models import Transaction
from fintrack.recurring import (
    advance,
    days_in_month,
    detect_recurring,
    match_period,
    normalize_description,
    spread,
    upcoming_occurrences,
)


def build_series(description, amount, start, step, count):
    """Build a list of transactions spaced evenly apart."""
    return [
        Transaction(start + timedelta(days=step * i), description, amount) for i in range(count)
    ]


def test_normalize_removes_digits_and_banking_words():
    assert normalize_description("SEPA Lastschrift NETFLIX.COM 4711") == "netflixcom"
    assert normalize_description("REWE Markt GmbH 220") == "rewe markt"
    assert normalize_description("12345") == ""


def test_days_in_month_handles_february_and_december():
    assert days_in_month(2024, 2) == 29
    assert days_in_month(2023, 2) == 28
    assert days_in_month(2024, 12) == 31


def test_advance_keeps_the_day_of_the_month():
    assert advance(date(2024, 1, 15), 30) == date(2024, 2, 15)
    assert advance(date(2024, 1, 31), 30) == date(2024, 2, 29)
    assert advance(date(2024, 1, 15), 91) == date(2024, 4, 15)
    assert advance(date(2024, 1, 15), 365) == date(2025, 1, 15)


def test_advance_just_adds_days_for_weekly_periods():
    assert advance(date(2024, 1, 5), 7, 2) == date(2024, 1, 19)


def test_match_period_snaps_to_the_nearest_known_rhythm():
    assert match_period(31) == (30, "monthly")
    assert match_period(7) == (7, "weekly")
    assert match_period(45) is None


def test_spread_is_zero_for_identical_numbers():
    assert spread([10, 10, 10]) == 0.0
    assert spread([10]) == 0.0
    assert spread([10, 20]) > 0.0


def test_detects_a_clean_monthly_subscription():
    detected = detect_recurring(build_series("Netflix.com", -12.99, date(2024, 1, 17), 30, 8))
    assert len(detected) == 1
    assert detected[0].period_label == "monthly"
    assert detected[0].occurrences == 8
    assert detected[0].confidence > 0.9


def test_ignores_irregular_grocery_shopping():
    transactions = [
        Transaction(date(2024, 1, 3), "REWE Markt", -14.20),
        Transaction(date(2024, 1, 5), "REWE Markt", -63.90),
        Transaction(date(2024, 1, 19), "REWE Markt", -22.00),
        Transaction(date(2024, 2, 2), "REWE Markt", -51.10),
        Transaction(date(2024, 2, 3), "REWE Markt", -8.40),
    ]
    assert detect_recurring(transactions) == []


def test_needs_at_least_three_bookings():
    assert detect_recurring(build_series("Gym", -29.90, date(2024, 1, 2), 30, 2)) == []
    with pytest.raises(ValueError):
        detect_recurring([], min_occurrences=2)


def test_income_series_is_marked_as_income():
    detected = detect_recurring(build_series("Employer Salary", 2500.0, date(2024, 1, 27), 30, 6))
    assert detected[0].is_income
    assert detected[0].monthly_equivalent > 0
    assert detected[0].yearly_equivalent > detected[0].monthly_equivalent


def test_quarterly_cost_is_spread_over_the_months():
    detected = detect_recurring(build_series("VRR Ticket", -90.0, date(2024, 1, 6), 91, 5))
    assert detected[0].period_label == "quarterly"
    assert detected[0].monthly_equivalent == pytest.approx(-29.67, abs=0.05)


def test_wildly_changing_amounts_are_not_recurring():
    amounts = [-10.0, -90.0, -20.0, -150.0, -15.0]
    transactions = [
        Transaction(date(2024, 1, 1) + timedelta(days=30 * i), "Bill", amount)
        for i, amount in enumerate(amounts)
    ]
    assert detect_recurring(transactions) == []


def test_finds_the_right_things_in_the_sample_history(sample_transactions):
    labels = {series.label for series in detect_recurring(sample_transactions)}
    assert "Netflix.com" in labels
    assert "Hausverwaltung Mueller Miete" in labels
    assert "Arbeitgeber GmbH Gehalt" in labels
    assert not any("REWE" in label for label in labels)


def test_upcoming_occurrences_stay_inside_the_window():
    detected = detect_recurring(build_series("Netflix.com", -12.99, date(2024, 1, 17), 30, 8))
    start, end = date(2024, 9, 1), date(2024, 12, 31)
    events = upcoming_occurrences(detected, start, end)
    assert len(events) == 4
    assert all(start <= moment <= end for moment, _ in events)
    assert events == sorted(events, key=lambda pair: pair[0])


def test_upcoming_occurrences_rejects_a_backwards_window():
    with pytest.raises(ValueError):
        upcoming_occurrences([], date(2024, 5, 1), date(2024, 4, 1))
