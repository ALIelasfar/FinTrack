"""Finding payments that repeat: rent, salary, subscriptions and so on.

The idea is simple. Group the transactions by a cleaned-up version of their
description, then look at two things for each group: are the gaps between the
bookings roughly equal, and are the amounts roughly the same? If both hold,
the group is a recurring series.
"""

import re
import statistics
from datetime import date, timedelta

from .models import RecurringSeries, round_money

__all__ = [
    "KNOWN_PERIODS",
    "advance",
    "detect_recurring",
    "normalize_description",
    "upcoming_occurrences",
]

#: The rhythms we look for: length in days to a readable name.
KNOWN_PERIODS = {7: "weekly", 14: "biweekly", 30: "monthly", 91: "quarterly", 365: "yearly"}

#: Words that say nothing about who was paid, so we drop them.
NOISE_WORDS = [
    "gmbh", "ag", "kg", "co", "ltd", "inc", "sepa", "lastschrift", "dauerauftrag",
    "ueberweisung", "uberweisung", "payment", "zahlung", "ref", "mandate", "mandat",
    "nr", "no", "de", "eur", "card", "kartenzahlung", "vom", "the",
]


def normalize_description(description):
    """Turn a description into a stable key for the shop or company.

    Digits, punctuation and banking words are removed, so ``"NETFLIX.COM 4711
    SEPA"`` and ``"Netflix.com 0815"`` end up as the same key.

    Args:
        description: The raw transaction description.

    Returns:
        str: The cleaned key, which may be empty.

    Examples:
        >>> normalize_description("SEPA Lastschrift NETFLIX.COM 4711")
        'netflixcom'
        >>> normalize_description("REWE Markt GmbH 220")
        'rewe markt'
    """
    text = re.sub(r"[^a-z\s]+", "", description.lower())
    words = []
    for word in text.split():
        if word and word not in NOISE_WORDS:
            words.append(word)
    return " ".join(words[:4])


def days_in_month(year, month):
    """Return how many days the given month has.

    Args:
        year: The year, for example 2026.
        month: The month as a number from 1 to 12.

    Returns:
        int: The number of days in that month.
    """
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def advance(start, period_days, steps=1):
    """Move a date forward by whole periods.

    Monthly, quarterly and yearly periods move by real calendar months, so a
    payment on the 31st does not slowly drift through the month the way adding
    30 days would.

    Args:
        start: The date to move forward from.
        period_days: One of the keys of :data:`KNOWN_PERIODS`.
        steps: How many periods to move.

    Returns:
        date: The new date.

    Examples:
        >>> advance(date(2024, 1, 31), 30)
        datetime.date(2024, 2, 29)
        >>> advance(date(2024, 1, 5), 7, 2)
        datetime.date(2024, 1, 19)
    """
    months_per_step = {30: 1, 91: 3, 365: 12}
    if period_days not in months_per_step:
        return start + timedelta(days=period_days * steps)

    # Count months since year zero, add, then convert back.
    total_months = (start.year * 12 + start.month - 1) + months_per_step[period_days] * steps
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(start.day, days_in_month(year, month))
    return date(year, month, day)


def match_period(median_gap, tolerance=0.25):
    """Snap a measured gap onto one of the periods we know.

    Args:
        median_gap: The typical number of days between two bookings.
        tolerance: How far off the gap may be, as a share of the period.

    Returns:
        tuple | None: ``(period_days, label)`` if one fits, otherwise None.

    Examples:
        >>> match_period(31)
        (30, 'monthly')
        >>> match_period(45) is None
        True
    """
    for period_days, label in KNOWN_PERIODS.items():
        allowed = max(2.0, period_days * tolerance)
        if abs(median_gap - period_days) <= allowed:
            return period_days, label
    return None


def spread(values):
    """Measure how much a list of numbers varies, relative to its average.

    A result of 0 means all the numbers are identical; 0.2 means they wobble
    by about 20 percent around the average.

    Args:
        values: The numbers to measure.

    Returns:
        float: The relative spread. Returns 0 for a single value.

    Examples:
        >>> spread([10, 10, 10])
        0.0
    """
    if len(values) < 2:
        return 0.0
    average = statistics.mean(values)
    if average == 0:
        return 1.0
    return statistics.pstdev(values) / abs(average)


def detect_recurring(
    transactions,
    min_occurrences=3,
    amount_tolerance=0.20,
    period_tolerance=0.25,
    min_confidence=0.55,
):
    """Find the payments and incomes that repeat.

    Args:
        transactions: The transaction history, in any order.
        min_occurrences: How many bookings a group needs before we even look
            at it. Three is the minimum, since two bookings give only one gap.
        amount_tolerance: How much the amounts may vary. 0.20 allows a 20
            percent wobble, which covers bills like electricity.
        period_tolerance: How far the measured gap may be from a known period.
        min_confidence: The lowest confidence score we still report.

    Returns:
        list: The series found, most expensive per month first.

    Raises:
        ValueError: If min_occurrences is smaller than three.

    Examples:
        >>> from fintrack.sample_data import generate_sample_transactions
        >>> series = detect_recurring(generate_sample_transactions(months=12))
        >>> any(item.label.startswith("Netflix") for item in series)
        True
    """
    if min_occurrences < 3:
        raise ValueError("at least three occurrences are needed to establish a period")

    groups = {}
    for item in transactions:
        key = normalize_description(item.description)
        if key:
            groups.setdefault(key, []).append(item)

    found = []
    for key, items in groups.items():
        items = sorted(items, key=lambda item: item.date)
        series = evaluate_group(
            key, items, min_occurrences, amount_tolerance, period_tolerance, min_confidence
        )
        if series is not None:
            found.append(series)

    found.sort(key=lambda series: abs(series.monthly_equivalent), reverse=True)
    return found


def evaluate_group(
    key, items, min_occurrences=3, amount_tolerance=0.20, period_tolerance=0.25,
    min_confidence=0.55,
):
    """Decide whether one group of transactions is really a recurring series.

    Args:
        key: The normalised description shared by the group.
        items: The transactions of the group, sorted oldest first.
        min_occurrences: How many bookings the group needs.
        amount_tolerance: How much the amounts may vary.
        period_tolerance: How far the gap may be from a known period.
        min_confidence: The lowest confidence score we accept.

    Returns:
        RecurringSeries | None: The series, or None if the group does not
        repeat regularly enough.
    """
    if len(items) < min_occurrences:
        return None

    # If income and expenses share a description, keep only the expenses.
    has_income = any(item.is_income for item in items)
    has_expense = any(item.is_expense for item in items)
    if has_income and has_expense:
        expenses = [item for item in items if item.is_expense]
        if expenses:
            items = expenses

    # Measure the gaps in days between one booking and the next.
    gaps = []
    for earlier, later in zip(items, items[1:]):
        gap = (later.date - earlier.date).days
        if gap > 0:
            gaps.append(gap)
    if len(gaps) < min_occurrences - 1:
        return None

    median_gap = statistics.median(gaps)
    period = match_period(median_gap, period_tolerance)
    if period is None:
        return None
    period_days, period_label = period

    amounts = [item.amount for item in items]
    amount_spread = spread(amounts)
    if amount_spread > amount_tolerance:
        return None

    # Confidence: how even the gaps are, how steady the amounts are, and how
    # many times we have seen it. Each part is between 0 and 1.
    even_gaps = max(0.0, 1.0 - spread(gaps))
    steady_amounts = max(0.0, 1.0 - amount_spread / amount_tolerance)
    seen_often = min(1.0, len(items) / 6)
    confidence = 0.45 * even_gaps + 0.35 * steady_amounts + 0.20 * seen_often
    if confidence < min_confidence:
        return None

    return RecurringSeries(
        label=statistics.mode([item.description for item in items]),
        key=key,
        transactions=items,
        period_days=period_days,
        period_label=period_label,
        average_amount=round_money(statistics.mean(amounts)),
        amount_spread=amount_spread,
        confidence=min(1.0, confidence),
        next_due=advance(items[-1].date, period_days),
    )


def upcoming_occurrences(series_list, start, end):
    """List every booking the series are expected to make in a time window.

    Args:
        series_list: The recurring series to look at.
        start: First day of the window.
        end: Last day of the window.

    Returns:
        list: ``(date, series)`` pairs, sorted by date.

    Raises:
        ValueError: If end comes before start.
    """
    if end < start:
        raise ValueError("end must not be before start")

    events = []
    for series in series_list:
        step = 0
        moment = series.next_due
        # The next due date may already be in the past, so catch up first.
        while moment < start and step < 1000:
            step += 1
            moment = advance(series.next_due, series.period_days, step)
        while moment <= end:
            events.append((moment, series))
            step += 1
            moment = advance(series.next_due, series.period_days, step)

    events.sort(key=lambda pair: pair[0])
    return events
