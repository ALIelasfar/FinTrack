"""Tests for the aggregation helpers."""

from datetime import date

from fintrack.models import MonthlySummary, Transaction
from fintrack.summary import (
    average_monthly_expenses,
    monthly_summaries,
    net_balance,
    spending_by_category,
    top_merchants,
)

TRANSACTIONS = [
    Transaction(date(2024, 1, 5), "REWE", -20.00, category="Groceries"),
    Transaction(date(2024, 1, 6), "REWE", -30.00, category="Groceries"),
    Transaction(date(2024, 1, 27), "Salary", 2000.00, category="Income"),
    Transaction(date(2024, 2, 3), "Rent", -800.00, category="Housing"),
    Transaction(date(2024, 2, 27), "Salary", 2000.00, category="Income"),
    Transaction(date(2024, 3, 1), "Unknown shop", -50.00),
]


def test_net_balance_keeps_the_signs():
    assert net_balance(TRANSACTIONS) == 3100.00
    assert net_balance([]) == 0.0


def test_spending_by_category_skips_income_and_sorts_by_size():
    spending = spending_by_category(TRANSACTIONS)
    assert list(spending) == ["Housing", "Groceries", "Uncategorised"]
    assert spending["Groceries"] == 50.00
    assert "Income" not in spending


def test_monthly_summaries_group_by_calendar_month():
    summaries = monthly_summaries(TRANSACTIONS)
    assert [summary.month for summary in summaries] == ["2024-01", "2024-02", "2024-03"]
    assert summaries[0].income == 2000.00
    assert summaries[0].expenses == 50.00
    assert summaries[1].net == 1200.00


def test_average_monthly_expenses_can_skip_partial_months():
    summaries = [
        MonthlySummary("2024-01", 0.0, 10.0),
        MonthlySummary("2024-02", 0.0, 100.0),
        MonthlySummary("2024-03", 0.0, 200.0),
        MonthlySummary("2024-04", 0.0, 10.0),
    ]
    assert average_monthly_expenses(summaries) == 150.00
    assert average_monthly_expenses(summaries, skip_partial=False) == 80.00
    assert average_monthly_expenses([]) == 0.0


def test_top_merchants_reports_totals_and_counts():
    ranked = top_merchants(TRANSACTIONS, limit=2)
    assert ranked[0] == ("Rent", 800.00, 1)
    assert ranked[1] == ("REWE", 50.00, 2)
