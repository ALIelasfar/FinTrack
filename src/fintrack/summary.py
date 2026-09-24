"""Helpers that add transactions up into monthly and per-category totals."""

from .models import MonthlySummary, round_money

__all__ = [
    "average_monthly_expenses",
    "monthly_summaries",
    "net_balance",
    "spending_by_category",
    "top_merchants",
]


def net_balance(transactions):
    """Add up every transaction, keeping the signs.

    Args:
        transactions: The transactions to add up.

    Returns:
        float: Income minus expenses over the whole period.
    """
    total = 0.0
    for item in transactions:
        total += item.amount
    return round_money(total)


def spending_by_category(transactions, uncategorised="Uncategorised"):
    """Add up expenses per category, biggest first.

    Income is skipped and the totals are positive numbers.

    Args:
        transactions: The transactions to add up.
        uncategorised: Label used for transactions with no category.

    Returns:
        dict: Category name to total spent, sorted from biggest to smallest.
    """
    totals = {}
    for item in transactions:
        if item.is_expense:
            name = item.category or uncategorised
            totals[name] = totals.get(name, 0.0) + item.abs_amount

    ordered = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    return {name: round_money(total) for name, total in ordered}


def monthly_summaries(transactions):
    """Group the transactions into one summary per calendar month.

    Args:
        transactions: The transactions to group.

    Returns:
        list: One :class:`~fintrack.models.MonthlySummary` per month, oldest
        first.
    """
    grouped = {}
    for item in transactions:
        grouped.setdefault(item.month, []).append(item)

    summaries = []
    for month in sorted(grouped):
        items = grouped[month]
        income = 0.0
        expenses = 0.0
        for item in items:
            if item.is_income:
                income += item.amount
            else:
                expenses += item.abs_amount
        summaries.append(
            MonthlySummary(
                month=month,
                income=round_money(income),
                expenses=round_money(expenses),
                by_category=spending_by_category(items),
            )
        )
    return summaries


def average_monthly_expenses(summaries, skip_partial=True):
    """Work out the average spending per month.

    Args:
        summaries: Monthly summaries from :func:`monthly_summaries`.
        skip_partial: If True, the first and last month are left out because
            they are usually incomplete and would drag the average down.

    Returns:
        float: The average monthly spend, or 0 if there is nothing to average.
    """
    usable = list(summaries)
    if skip_partial and len(usable) > 2:
        usable = usable[1:-1]
    if not usable:
        return 0.0

    total = 0.0
    for summary in usable:
        total += summary.expenses
    return round_money(total / len(usable))


def top_merchants(transactions, limit=10):
    """Find the merchants you spent the most money at.

    Args:
        transactions: The transactions to look through.
        limit: How many merchants to return.

    Returns:
        list: ``(description, total_spent, number_of_bookings)`` tuples,
        biggest total first.
    """
    totals = {}
    counts = {}
    for item in transactions:
        if item.is_expense:
            totals[item.description] = totals.get(item.description, 0.0) + item.abs_amount
            counts[item.description] = counts.get(item.description, 0) + 1

    ordered = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    return [(name, round_money(total), counts[name]) for name, total in ordered]
