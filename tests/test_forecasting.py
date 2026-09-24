"""Tests for the balance projection."""

from datetime import date, timedelta

import pytest

from fintrack.forecasting import daily_discretionary_rate, forecast_balance, recurring_keys
from fintrack.models import Transaction
from fintrack.recurring import detect_recurring


def build_monthly(description, amount, start, count):
    """Build one transaction per month, always on the same day of month."""
    transactions = []
    for index in range(count):
        month_index = start.month - 1 + index
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        transactions.append(Transaction(date(year, month, start.day), description, amount))
    return transactions


def test_forecast_length_matches_the_horizon(sample_transactions):
    forecast = forecast_balance(sample_transactions, horizon_days=45)
    assert forecast.horizon_days == 45
    assert len(forecast.to_rows()) == 45


def test_forecast_rejects_bad_input(sample_transactions):
    with pytest.raises(ValueError):
        forecast_balance(sample_transactions, horizon_days=0)
    with pytest.raises(ValueError):
        forecast_balance([], horizon_days=30)


def test_a_given_starting_balance_is_used(sample_transactions):
    forecast = forecast_balance(sample_transactions, horizon_days=10, starting_balance="1500")
    assert forecast.starting_balance == 1500.00


def test_recurring_items_change_the_balance():
    transactions = build_monthly("Rent", -500.00, date(2024, 1, 1), 6)
    forecast = forecast_balance(
        transactions, horizon_days=40, starting_balance=1000, include_discretionary=False
    )
    assert forecast.ending_balance == 500.00


def test_running_out_of_money_is_detected():
    transactions = build_monthly("Rent", -500.00, date(2024, 1, 1), 6)
    forecast = forecast_balance(
        transactions, horizon_days=70, starting_balance=600, include_discretionary=False
    )
    negative = forecast.first_negative
    assert negative is not None
    assert negative.balance < 0


def test_no_warning_when_income_covers_the_expenses(sample_transactions):
    forecast = forecast_balance(sample_transactions, horizon_days=60, starting_balance=5000)
    assert forecast.first_negative is None
    assert forecast.minimum_point is not None


def test_recurring_keys_lists_every_booking_of_a_series():
    transactions = build_monthly("Rent", -300.00, date(2024, 1, 1), 6)
    assert len(recurring_keys(detect_recurring(transactions))) == 6


def test_daily_rate_leaves_out_the_recurring_bookings():
    recurring = build_monthly("Rent", -300.00, date(2024, 1, 1), 6)
    coffees = [
        Transaction(date(2024, 6, 1) - timedelta(days=i), "Coffee", -3.00) for i in range(30)
    ]
    series = detect_recurring(recurring)
    rate = daily_discretionary_rate(
        recurring + coffees, series, lookback_days=90, today=date(2024, 6, 1)
    )
    assert rate == -1.00


def test_daily_rate_checks_the_lookback():
    with pytest.raises(ValueError):
        daily_discretionary_rate([], [], lookback_days=0)


def test_days_with_a_recurring_booking_are_labelled(sample_transactions):
    forecast = forecast_balance(sample_transactions, horizon_days=60)
    assert any(point.events for point in forecast.points)
