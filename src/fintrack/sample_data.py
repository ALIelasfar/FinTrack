"""Making a realistic but completely made-up transaction history.

The generator always produces the same data for the same seed, so the example
dataset and the tests stay reproducible. No real bank data is involved.
"""

import random
from datetime import date, timedelta

from .models import Transaction
from .recurring import advance

__all__ = ["generate_sample_transactions"]

#: Regular items: description, amount, period in days, day of month, wobble.
RECURRING_TEMPLATE = [
    ("Arbeitgeber GmbH Gehalt", 2640.00, 30, 27, 0.01),
    ("Hausverwaltung Mueller Miete", -895.00, 30, 1, 0.0),
    ("Stadtwerke Dortmund Strom", -64.00, 30, 3, 0.12),
    ("Telekom Deutschland Internet", -39.99, 30, 5, 0.0),
    ("Vodafone Mobilfunk", -19.99, 30, 8, 0.0),
    ("Barmenia Versicherung", -78.50, 30, 12, 0.0),
    ("Netflix.com", -12.99, 30, 17, 0.0),
    ("Spotify AB", -9.99, 30, 21, 0.0),
    ("McFit Fitnessstudio", -29.90, 30, 2, 0.0),
    ("Sparplan ETF Depot Transfer", -300.00, 30, 28, 0.0),
    ("VRR Abo Ticket", -89.40, 91, 6, 0.0),
    ("Domain Hosting Rechnung", -119.00, 365, 14, 0.0),
]

#: Irregular spending: description, cheapest, dearest, roughly how often a month.
DISCRETIONARY_TEMPLATE = [
    ("REWE Markt Dortmund", 14.0, 68.0, 6.0),
    ("ALDI Sued", 9.0, 42.0, 3.0),
    ("Lidl Filiale 220", 11.0, 38.0, 2.0),
    ("Cafe Central", 3.5, 12.0, 4.0),
    ("Lieferando Bestellung", 12.0, 34.0, 2.0),
    ("Pizzeria Da Marco", 18.0, 55.0, 1.2),
    ("Shell Tankstelle", 40.0, 85.0, 1.0),
    ("Amazon Marketplace", 8.0, 120.0, 2.0),
    ("Apotheke am Markt", 6.0, 45.0, 0.6),
    ("MediaMarkt", 25.0, 260.0, 0.3),
    ("Deutsche Bahn Ticket", 19.0, 89.0, 0.5),
    ("Buchhandlung Uni", 12.0, 40.0, 0.4),
]


def generate_sample_transactions(months=18, seed=42, end=None, account="Girokonto"):
    """Create a made-up transaction history that looks like a real one.

    The result has twelve regular items (salary, rent, bills, subscriptions, a
    quarterly transport pass and a yearly invoice) plus everyday spending.

    Args:
        months: How many months of history to make.
        seed: Seed for the random generator, so the result is repeatable.
        end: The last day of the history. Defaults to today.
        account: Account name written on every transaction.

    Returns:
        list: The transactions, oldest first.

    Raises:
        ValueError: If months is not positive.

    Examples:
        >>> transactions = generate_sample_transactions(months=6, seed=1)
        >>> len(transactions) > 50
        True
    """
    if months <= 0:
        raise ValueError("months must be positive")

    generator = random.Random(seed)
    last_day = end or date.today()
    first_day = advance(last_day, 30, -months)

    transactions = []
    transactions += make_recurring(generator, first_day, last_day, account)
    transactions += make_discretionary(generator, first_day, last_day, months, account)
    transactions.sort(key=lambda item: (item.date, item.description))
    return transactions


def first_due_date(first_day, period_days, day_of_month):
    """Find the first day a regular item is due, on or after a start date.

    Args:
        first_day: The start of the history.
        period_days: How often the item repeats.
        day_of_month: The day of the month it usually lands on.

    Returns:
        date: The first due date.
    """
    if period_days in (30, 91, 365):
        candidate = date(first_day.year, first_day.month, min(day_of_month, 28))
        if candidate < first_day:
            candidate = advance(candidate, 30)
        return candidate
    return first_day + timedelta(days=day_of_month % period_days)


def move_off_weekend(moment, generator):
    """Move a booking that lands on a weekend to a nearby weekday.

    Args:
        moment: The booking date.
        generator: The random generator, so the shift stays repeatable.

    Returns:
        date: A weekday close to the original date.
    """
    if moment.weekday() == 5:
        return moment + timedelta(days=generator.choice([-1, 2]))
    if moment.weekday() == 6:
        return moment + timedelta(days=generator.choice([-2, 1]))
    return moment


def make_recurring(generator, first_day, last_day, account):
    """Build the regular part of the history.

    Args:
        generator: The random generator.
        first_day: Start of the history.
        last_day: End of the history.
        account: Account name for every transaction.

    Returns:
        list: The regular transactions.
    """
    result = []
    for description, base_amount, period_days, day_of_month, wobble in RECURRING_TEMPLATE:
        start = first_due_date(first_day, period_days, day_of_month)
        step = 0
        moment = start
        while moment <= last_day:
            if moment >= first_day:
                amount = base_amount
                if wobble:
                    amount = base_amount * (1 + generator.uniform(-wobble, wobble))
                result.append(
                    Transaction(
                        date=move_off_weekend(moment, generator),
                        description=description,
                        amount=amount,
                        account=account,
                    )
                )
            step += 1
            moment = advance(start, period_days, step)
    return result


def make_discretionary(generator, first_day, last_day, months, account):
    """Build the irregular, everyday part of the history.

    Args:
        generator: The random generator.
        first_day: Start of the history.
        last_day: End of the history.
        months: How many months the history covers.
        account: Account name for every transaction.

    Returns:
        list: The irregular transactions.
    """
    result = []
    span_days = (last_day - first_day).days or 1
    for description, cheapest, dearest, per_month in DISCRETIONARY_TEMPLATE:
        count = max(1, int(generator.gauss(per_month * months, per_month * 0.5)))
        for _ in range(count):
            offset = generator.randrange(span_days + 1)
            result.append(
                Transaction(
                    date=first_day + timedelta(days=offset),
                    description=description,
                    amount=-round(generator.uniform(cheapest, dearest), 2),
                    account=account,
                )
            )
    return result
