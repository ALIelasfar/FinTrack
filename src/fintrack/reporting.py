"""Building the text report that the command line prints."""

from .models import format_money
from .summary import average_monthly_expenses, net_balance, top_merchants

__all__ = ["build_report", "format_table", "section"]

#: How wide the horizontal lines of the report are.
WIDTH = 78


def section(title):
    """Return a section heading with a line under it.

    Args:
        title: The heading text.

    Returns:
        str: The heading followed by a line of dashes.
    """
    return f"\n{title}\n{'-' * WIDTH}"


def looks_numeric(text):
    """Check whether a cell should be lined up on the right like a number.

    Args:
        text: The cell content.

    Returns:
        bool: True if the cell is only digits, signs and separators.

    Examples:
        >>> looks_numeric("-12.50")
        True
        >>> looks_numeric("Netflix")
        False
    """
    stripped = text.replace("-", "").replace(".", "").replace("%", "").replace(",", "")
    return stripped.isdigit()


def format_table(rows, headers):
    """Draw a simple text table with the columns lined up.

    Args:
        rows: The table body. Every row needs one cell per header.
        headers: The column titles.

    Returns:
        str: The finished table, or ``"(no data)"`` if there are no rows.

    Raises:
        ValueError: If a row has the wrong number of cells.

    Examples:
        >>> print(format_table([["a", 1]], ["letter", "number"]))
        letter  number
        a            1
    """
    if not rows:
        return "(no data)"
    for row in rows:
        if len(row) != len(headers):
            raise ValueError(f"row {row!r} does not match headers {headers!r}")

    cells = [[str(value) for value in row] for row in rows]

    # Each column is as wide as its widest cell.
    widths = []
    numeric = []
    for index, header in enumerate(headers):
        column = [row[index] for row in cells]
        widths.append(max([len(header)] + [len(value) for value in column]))
        numeric.append(all(looks_numeric(value) for value in column))

    lines = []
    for row in [list(headers), *cells]:
        parts = []
        for index, value in enumerate(row):
            if numeric[index]:
                parts.append(value.rjust(widths[index]))
            else:
                parts.append(value.ljust(widths[index]))
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines)


def build_report(
    transactions, summaries, spending, series_list, forecast, recommendations, chart_paths=()
):
    """Put the whole text report together.

    Args:
        transactions: The transactions that were analysed.
        summaries: Monthly summaries.
        spending: Spending per category.
        series_list: The recurring series that were found.
        forecast: The balance projection, or None to leave that part out.
        recommendations: The advice to print at the end.
        chart_paths: Paths of any charts that were saved.

    Returns:
        str: The complete report.
    """
    parts = ["=" * WIDTH, "FINTRACK ANALYSIS REPORT".center(WIDTH), "=" * WIDTH]
    parts.append(overview_section(transactions, summaries))
    parts.append(monthly_section(summaries))
    parts.append(category_section(spending))
    parts.append(recurring_section(series_list))
    if forecast is not None:
        parts.append(forecast_section(forecast))
    parts.append(merchant_section(transactions))
    parts.append(advice_section(recommendations))

    if chart_paths:
        parts.append(section("Generated charts"))
        for path in chart_paths:
            parts.append(f"  - {path}")
    parts.append("")
    return "\n".join(parts)


def overview_section(transactions, summaries):
    """Build the headline numbers at the top of the report."""
    if not transactions:
        return section("Overview") + "\n(no transactions)"

    first = min(item.date for item in transactions)
    last = max(item.date for item in transactions)
    total_income = round(sum(summary.income for summary in summaries), 2)
    total_expenses = round(sum(summary.expenses for summary in summaries), 2)

    rows = [
        ["Period", f"{first.isoformat()} to {last.isoformat()}"],
        ["Transactions", len(transactions)],
        ["Months covered", len(summaries)],
        ["Total income", format_money(total_income)],
        ["Total expenses", format_money(total_expenses)],
        ["Net result", format_money(net_balance(transactions))],
        ["Average expenses per month", format_money(average_monthly_expenses(summaries))],
    ]
    return section("Overview") + "\n" + format_table(rows, ["Metric", "Value"])


def monthly_section(summaries):
    """Build the month by month table."""
    rows = []
    for summary in summaries:
        rows.append(
            [
                summary.month,
                format_money(summary.income),
                format_money(summary.expenses),
                format_money(summary.net),
                f"{summary.savings_rate:.0%}",
            ]
        )
    headers = ["Month", "Income", "Expenses", "Net", "Saved"]
    return section("Month by month") + "\n" + format_table(rows, headers)


def category_section(spending):
    """Build the spending per category table."""
    total = sum(spending.values())
    rows = []
    for name, amount in spending.items():
        share = f"{amount / total:.1%}" if total else "-"
        rows.append([name, format_money(amount), share])
    return section("Spending by category") + "\n" + format_table(
        rows, ["Category", "Total", "Share"]
    )


def recurring_section(series_list):
    """Build the table of detected recurring payments."""
    rows = []
    for series in series_list:
        rows.append(
            [
                series.label[:34],
                series.period_label,
                format_money(series.average_amount),
                format_money(series.monthly_equivalent),
                series.occurrences,
                series.next_due.isoformat(),
                f"{series.confidence:.0%}",
            ]
        )
    headers = ["Description", "Period", "Amount", "Per month", "Seen", "Next due", "Conf."]
    return section("Detected recurring payments") + "\n" + format_table(rows, headers)


def forecast_section(forecast):
    """Build the forecast summary and the list of upcoming bookings."""
    rows = [
        ["Starting balance", format_money(forecast.starting_balance)],
        ["Horizon", f"{forecast.horizon_days} days"],
        ["Daily irregular spending", format_money(forecast.daily_discretionary)],
        ["Projected end balance", format_money(forecast.ending_balance)],
    ]

    lowest = forecast.minimum_point
    if lowest is not None:
        rows.append(
            ["Lowest point", f"{format_money(lowest.balance)} on {lowest.date.isoformat()}"]
        )

    negative = forecast.first_negative
    if negative is None:
        rows.append(["First negative day", "none projected"])
    else:
        rows.append(["First negative day", negative.date.isoformat()])

    events = []
    for point in forecast.points:
        for event in point.events:
            events.append([point.date.isoformat(), event])
    events = events[:12]

    text = section("Balance forecast") + "\n" + format_table(rows, ["Metric", "Value"])
    text += "\n\nNext expected recurring bookings:\n"
    text += format_table(events, ["Date", "Item"])
    return text


def merchant_section(transactions):
    """Build the table of the merchants with the highest total spend."""
    rows = []
    for name, total, count in top_merchants(transactions, limit=8):
        rows.append([name, format_money(total), count])
    return section("Largest merchants") + "\n" + format_table(
        rows, ["Merchant", "Total", "Bookings"]
    )


def advice_section(recommendations):
    """Build the recommendation list."""
    if not recommendations:
        return section("Recommendations") + "\n(no findings)"
    return section("Recommendations") + "\n" + "\n\n".join(
        str(item) for item in recommendations
    )
