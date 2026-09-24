"""Tests for the data structures in :mod:`fintrack.models`."""

from datetime import date

import pytest

from fintrack.models import (
    ForecastPoint,
    MonthlySummary,
    Recommendation,
    Transaction,
    format_money,
    round_money,
)


def test_round_money_rounds_to_two_decimals():
    assert round_money("12.3456") == 12.35
    assert round_money(-7) == -7.0
    assert round_money(0.001) == 0.0


def test_round_money_rejects_text():
    with pytest.raises(ValueError):
        round_money("not a number")


def test_format_money_always_shows_two_decimals():
    assert format_money(-895) == "-895.00"
    assert format_money(12.5) == "12.50"


def test_transaction_cleans_amount_and_whitespace():
    transaction = Transaction(date(2024, 1, 5), "  REWE   Markt  ", -12.999)
    assert transaction.amount == -13.0
    assert transaction.description == "REWE Markt"


def test_transaction_knows_income_from_expense():
    expense = Transaction(date(2024, 1, 5), "Rent", -895)
    income = Transaction(date(2024, 1, 5), "Salary", 2500)
    assert expense.is_expense and not expense.is_income
    assert income.is_income and not income.is_expense
    assert expense.abs_amount == 895.0
    assert expense.month == "2024-01"


def test_with_category_does_not_change_the_original():
    original = Transaction(date(2024, 1, 5), "Rent", -895)
    tagged = original.with_category("Housing")
    assert original.category is None
    assert tagged.category == "Housing"
    assert tagged.amount == original.amount


def test_monthly_summary_net_and_savings_rate():
    summary = MonthlySummary("2024-01", 2000.0, 1500.0)
    assert summary.net == 500.0
    assert summary.savings_rate == pytest.approx(0.25)


def test_savings_rate_is_zero_without_income():
    assert MonthlySummary("2024-01", 0.0, 50.0).savings_rate == 0.0


def test_recommendation_ranking_puts_critical_first():
    items = [
        Recommendation("b", "d", "info"),
        Recommendation("a", "d", "critical"),
        Recommendation("c", "d", "warning"),
    ]
    assert [item.title for item in sorted(items, key=lambda item: item.rank)] == ["a", "c", "b"]


def test_recommendation_prints_its_severity_marker():
    assert str(Recommendation("t", "d", "critical")).startswith("[!!]")


def test_forecast_point_starts_with_no_events():
    assert ForecastPoint(date(2024, 1, 1), 10.0).events == []
