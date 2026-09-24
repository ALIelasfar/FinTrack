"""Projecting the account balance into the future.

The projection has two parts. The recurring items we already found get placed
on the days they are expected. Everything else is smoothed into one average
amount per day.
"""

from datetime import timedelta

from .models import Forecast, ForecastPoint, round_money
from .recurring import detect_recurring, upcoming_occurrences

__all__ = ["daily_discretionary_rate", "forecast_balance"]


def recurring_keys(series_list):
    """Collect an identity tuple for every transaction inside the series.

    Args:
        series_list: The recurring series.

    Returns:
        set: ``(date, description, amount)`` tuples we can look transactions
        up by.
    """
    keys = set()
    for series in series_list:
        for item in series.transactions:
            keys.add((item.date, item.description, item.amount))
    return keys


def daily_discretionary_rate(transactions, series_list, lookback_days=90, today=None):
    """Average daily amount of everything that is *not* recurring.

    Args:
        transactions: The full transaction history.
        series_list: The recurring series, which are counted elsewhere.
        lookback_days: How many days back to look.
        today: The day to count back from. Defaults to the newest transaction.

    Returns:
        float: The average amount per day, usually negative.

    Raises:
        ValueError: If lookback_days is not positive.
    """
    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")
    if not transactions:
        return 0.0

    reference = today or max(item.date for item in transactions)
    window_start = reference - timedelta(days=lookback_days)
    known = recurring_keys(series_list)

    total = 0.0
    for item in transactions:
        if not window_start <= item.date <= reference:
            continue
        if (item.date, item.description, item.amount) in known:
            continue
        total += item.amount
    return round_money(total / lookback_days)


def forecast_balance(
    transactions,
    horizon_days=90,
    starting_balance=None,
    series=None,
    include_discretionary=True,
    today=None,
):
    """Project the account balance day by day.

    Args:
        transactions: The history the projection is based on.
        horizon_days: How many days into the future to go.
        starting_balance: The balance to start from. If left out, the sum of
            the whole history is used.
        series: Recurring series you already detected. Detected here if left
            out.
        include_discretionary: Whether to also subtract the average daily
            spending for irregular purchases.
        today: The day the projection starts from. Defaults to the newest
            transaction.

    Returns:
        Forecast: One point per day of the horizon.

    Raises:
        ValueError: If horizon_days is not positive or the history is empty.

    Examples:
        >>> from fintrack.sample_data import generate_sample_transactions
        >>> history = generate_sample_transactions(months=12)
        >>> forecast_balance(history, horizon_days=30).horizon_days
        30
    """
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    if not transactions:
        raise ValueError("cannot forecast from an empty transaction history")

    if series is None:
        series = detect_recurring(transactions)

    reference = today or max(item.date for item in transactions)
    start = reference + timedelta(days=1)
    end = reference + timedelta(days=horizon_days)

    if starting_balance is None:
        balance = 0.0
        for item in transactions:
            balance += item.amount
        balance = round_money(balance)
    else:
        balance = round_money(starting_balance)
    opening_balance = balance

    rate = 0.0
    if include_discretionary:
        rate = daily_discretionary_rate(transactions, series, today=reference)

    # Work out which series are due on which day.
    scheduled = {}
    for moment, one_series in upcoming_occurrences(series, start, end):
        scheduled.setdefault(moment, []).append(one_series)

    points = []
    for offset in range(horizon_days):
        current = start + timedelta(days=offset)
        events = []
        for one_series in scheduled.get(current, []):
            balance = round_money(balance + one_series.average_amount)
            events.append(f"{one_series.label} ({one_series.average_amount:.2f})")
        balance = round_money(balance + rate)
        points.append(ForecastPoint(date=current, balance=balance, events=events))

    return Forecast(points=points, starting_balance=opening_balance, daily_discretionary=rate)
