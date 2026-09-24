"""Core data structures used across :mod:`fintrack`.

Every class here is a small dataclass that holds data and offers a few
convenience properties. Money is stored as a normal float rounded to two
decimal places by :func:`round_money`.
"""

from dataclasses import dataclass, field
from datetime import date

__all__ = [
    "Forecast",
    "ForecastPoint",
    "MonthlySummary",
    "Recommendation",
    "RecurringSeries",
    "Transaction",
    "format_money",
    "round_money",
]

#: Sort weight per severity, most urgent first. Used by Recommendation.rank.
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def round_money(value):
    """Round a number to two decimal places, the way cents work.

    Args:
        value: A number, or a string containing a number.

    Returns:
        float: The value rounded to two decimals.

    Raises:
        ValueError: If the value is not a number.

    Examples:
        >>> round_money("12.3456")
        12.35
        >>> round_money(-7)
        -7.0
    """
    return round(float(value), 2)


def format_money(value):
    """Format a number as a string with exactly two decimals.

    Args:
        value: The amount to format.

    Returns:
        str: The formatted amount, for example ``"-895.00"``.

    Examples:
        >>> format_money(-895)
        '-895.00'
    """
    return f"{float(value):.2f}"


@dataclass
class Transaction:
    """A single booking on a bank account.

    Attributes:
        date: Day the transaction was booked.
        description: Free-text description as provided by the bank.
        amount: Signed amount. Negative means money left the account,
            positive means money came in.
        account: Name of the account the booking belongs to.
        category: Spending category, or None if not categorised yet.
    """

    date: date
    description: str
    amount: float
    account: str = "main"
    category: str | None = None

    def __post_init__(self):
        """Clean up the amount and the description after the object is built."""
        self.amount = round_money(self.amount)
        self.description = " ".join(self.description.split())

    @property
    def is_expense(self):
        """bool: True if the transaction takes money out of the account."""
        return self.amount < 0

    @property
    def is_income(self):
        """bool: True if the transaction brings money into the account."""
        return self.amount > 0

    @property
    def abs_amount(self):
        """float: The size of the transaction, ignoring its direction."""
        return abs(self.amount)

    @property
    def month(self):
        """str: The booking month, for example ``"2026-05"``."""
        return f"{self.date.year:04d}-{self.date.month:02d}"

    def with_category(self, category):
        """Return a copy of this transaction with a category attached.

        Args:
            category: The category name to set.

        Returns:
            Transaction: A new transaction; the original is left unchanged.
        """
        return Transaction(self.date, self.description, self.amount, self.account, category)

    def __str__(self):
        """Return a short one-line description of the transaction."""
        return f"{self.date.isoformat()}  {format_money(self.amount):>10}  {self.description}"


@dataclass
class RecurringSeries:
    """A group of transactions that repeat on a regular schedule.

    Attributes:
        label: Readable name, taken from the most common description.
        key: Normalised description used to group the transactions.
        transactions: The detected occurrences, oldest first.
        period_days: Idealised period length: 7, 14, 30, 91 or 365 days.
        period_label: Readable period name such as ``"monthly"``.
        average_amount: Average signed amount of the occurrences.
        amount_spread: How much the amounts vary; 0 means they are identical.
        confidence: How sure the detector is, between 0 and 1.
        next_due: The date the next occurrence is expected.
    """

    label: str
    key: str
    transactions: list
    period_days: int
    period_label: str
    average_amount: float
    amount_spread: float
    confidence: float
    next_due: date

    @property
    def occurrences(self):
        """int: How many times this series was seen."""
        return len(self.transactions)

    @property
    def is_income(self):
        """bool: True if this series pays money into the account."""
        return self.average_amount > 0

    @property
    def first_seen(self):
        """date: Date of the earliest occurrence."""
        return self.transactions[0].date

    @property
    def last_seen(self):
        """date: Date of the most recent occurrence."""
        return self.transactions[-1].date

    @property
    def monthly_equivalent(self):
        """float: What this series costs or pays per month."""
        return round_money(self.average_amount * 30 / self.period_days)

    @property
    def yearly_equivalent(self):
        """float: What this series costs or pays per year."""
        return round_money(self.average_amount * 365 / self.period_days)

    def __str__(self):
        """Return a short one-line description of the series."""
        return (
            f"{self.label} - {format_money(self.average_amount)} {self.period_label} "
            f"(next {self.next_due.isoformat()}, confidence {self.confidence:.0%})"
        )


@dataclass
class ForecastPoint:
    """The projected balance on a single future day.

    Attributes:
        date: The day being projected.
        balance: Projected balance at the end of that day.
        events: Names of the recurring items expected on that day.
    """

    date: date
    balance: float
    events: list = field(default_factory=list)


@dataclass
class Forecast:
    """The result of projecting an account balance into the future.

    Attributes:
        points: One ForecastPoint per day of the horizon.
        starting_balance: The balance the projection started from.
        daily_discretionary: Average non-recurring spending per day.
    """

    points: list
    starting_balance: float
    daily_discretionary: float

    @property
    def horizon_days(self):
        """int: How many days the forecast covers."""
        return len(self.points)

    @property
    def ending_balance(self):
        """float: Balance on the last projected day."""
        if not self.points:
            return self.starting_balance
        return self.points[-1].balance

    @property
    def minimum_point(self):
        """ForecastPoint | None: The day with the lowest projected balance."""
        if not self.points:
            return None
        return min(self.points, key=lambda point: point.balance)

    @property
    def first_negative(self):
        """ForecastPoint | None: The first day the balance goes below zero."""
        for point in self.points:
            if point.balance < 0:
                return point
        return None

    def to_rows(self):
        """Return the forecast as printable ``(date, balance, events)`` rows."""
        rows = []
        for point in self.points:
            rows.append(
                (point.date.isoformat(), format_money(point.balance), ", ".join(point.events))
            )
        return rows


@dataclass
class MonthlySummary:
    """Income and expenses added up for one calendar month.

    Attributes:
        month: The month, for example ``"2026-05"``.
        income: Total money that came in.
        expenses: Total money that went out, as a positive number.
        by_category: Spending per category, positive numbers.
    """

    month: str
    income: float
    expenses: float
    by_category: dict = field(default_factory=dict)

    @property
    def net(self):
        """float: Income minus expenses."""
        return round_money(self.income - self.expenses)

    @property
    def savings_rate(self):
        """float: Share of the income that was not spent, between 0 and 1."""
        if self.income <= 0:
            return 0.0
        return max(0.0, self.net / self.income)


@dataclass
class Recommendation:
    """One piece of advice produced from the analysis.

    Attributes:
        title: Short headline.
        detail: One or two sentences explaining the finding.
        severity: Either ``"info"``, ``"warning"`` or ``"critical"``.
        monthly_impact: Money per month involved, or None if not measurable.
    """

    title: str
    detail: str
    severity: str = "info"
    monthly_impact: float | None = None

    @property
    def rank(self):
        """int: Sort key so that critical findings come first."""
        return SEVERITY_ORDER.get(self.severity, 3)

    def __str__(self):
        """Return the recommendation as a printable bullet point."""
        markers = {"critical": "[!!]", "warning": "[! ]", "info": "[i ]"}
        impact = ""
        if self.monthly_impact is not None:
            impact = f" (~{format_money(self.monthly_impact)}/month)"
        return f"{markers[self.severity]} {self.title}{impact}\n     {self.detail}"
