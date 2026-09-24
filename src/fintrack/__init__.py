"""fintrack - analyse bank transactions from the command line or from Python.

The package turns a CSV export of bank transactions into three things:

1. a list of recurring payments and incomes (rent, salary, subscriptions),
2. a day by day forecast of the account balance,
3. plain language recommendations for saving money.

Everything the command line interface does is available as importable
functions, so the package can also be used from a notebook or another script.

Examples:
    >>> import fintrack
    >>> transactions = fintrack.load_transactions(fintrack.sample_data_path())
    >>> transactions = fintrack.Categorizer().categorize_all(transactions)
    >>> series = fintrack.detect_recurring(transactions)
    >>> forecast = fintrack.forecast_balance(transactions, horizon_days=60)
    >>> advice = fintrack.generate_recommendations(
    ...     fintrack.monthly_summaries(transactions), series, forecast
    ... )
"""

#: Package version, kept in sync with ``pyproject.toml``.
__version__ = "0.1.0"

from .advice import generate_recommendations
from .categorization import DEFAULT_RULES, Categorizer
from .data import sample_data_path
from .forecasting import daily_discretionary_rate, forecast_balance
from .loading import (
    TransactionParseError,
    load_transactions,
    parse_amount,
    parse_date,
    save_transactions,
)
from .models import (
    Forecast,
    ForecastPoint,
    MonthlySummary,
    Recommendation,
    RecurringSeries,
    Transaction,
    format_money,
    round_money,
)
from .recurring import detect_recurring, normalize_description, upcoming_occurrences
from .reporting import build_report
from .sample_data import generate_sample_transactions
from .summary import (
    average_monthly_expenses,
    monthly_summaries,
    net_balance,
    spending_by_category,
    top_merchants,
)

__all__ = [
    "DEFAULT_RULES",
    "Categorizer",
    "Forecast",
    "ForecastPoint",
    "MonthlySummary",
    "Recommendation",
    "RecurringSeries",
    "Transaction",
    "TransactionParseError",
    "__version__",
    "average_monthly_expenses",
    "build_report",
    "daily_discretionary_rate",
    "detect_recurring",
    "forecast_balance",
    "format_money",
    "generate_recommendations",
    "generate_sample_transactions",
    "load_transactions",
    "monthly_summaries",
    "net_balance",
    "normalize_description",
    "parse_amount",
    "parse_date",
    "round_money",
    "sample_data_path",
    "save_transactions",
    "spending_by_category",
    "top_merchants",
    "upcoming_occurrences",
]