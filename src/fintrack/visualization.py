"""Charts drawn with Matplotlib and saved as PNG files.

Nothing is ever shown on screen: every function writes a file and returns the
path it wrote to, so the code also works on a machine without a display.
"""
from contextlib import suppress
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

__all__ = [
    "plot_all",
    "plot_balance_forecast",
    "plot_category_breakdown",
    "plot_monthly_cashflow",
    "plot_recurring_overview",
]

#: Colour for income and positive numbers.
INCOME_COLOR = "#2a9d8f"
#: Colour for expenses and negative numbers.
EXPENSE_COLOR = "#e76f51"
#: A dark neutral colour for lines.
ACCENT_COLOR = "#264653"


def save_figure(figure, path):
    """Save a figure to a PNG file and close it.

    Args:
        figure: The Matplotlib figure to save.
        path: Where to write it. Missing folders are created.

    Returns:
        Path: The file that was written.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)
    return destination


def plot_monthly_cashflow(summaries, path="output/monthly_cashflow.png"):
    """Draw income, expenses and the net result for each month.

    Args:
        summaries: Monthly summaries, oldest first.
        path: Where to save the PNG.

    Returns:
        Path: The file that was written.

    Raises:
        ValueError: If there are no summaries to draw.
    """
    if not summaries:
        raise ValueError("nothing to plot: no monthly summaries")

    months = [summary.month for summary in summaries]
    positions = list(range(len(months)))
    income = [summary.income for summary in summaries]
    expenses = [summary.expenses for summary in summaries]
    net = [summary.net for summary in summaries]

    figure, axes = plt.subplots(figsize=(max(8, len(months) * 0.8), 4.5))
    width = 0.38
    axes.bar(
        [position - width / 2 for position in positions], income, width,
        label="Income", color=INCOME_COLOR,
    )
    axes.bar(
        [position + width / 2 for position in positions], expenses, width,
        label="Expenses", color=EXPENSE_COLOR,
    )
    axes.plot(positions, net, color=ACCENT_COLOR, marker="o", linewidth=2, label="Net")
    axes.axhline(0, color="grey", linewidth=0.8)
    axes.set_xticks(positions)
    axes.set_xticklabels(months, rotation=45, ha="right")
    axes.set_ylabel("EUR")
    axes.set_title("Monthly cashflow")
    axes.legend()
    axes.grid(axis="y", alpha=0.3)
    return save_figure(figure, path)


def plot_category_breakdown(spending, path="output/category_breakdown.png", top_n=10):
    """Draw total spending per category as horizontal bars.

    Args:
        spending: Category name to total spent.
        path: Where to save the PNG.
        top_n: How many categories to show before merging the rest.

    Returns:
        Path: The file that was written.

    Raises:
        ValueError: If there is no spending data.
    """
    if not spending:
        raise ValueError("nothing to plot: no spending data")

    items = sorted(spending.items(), key=lambda pair: pair[1], reverse=True)
    shown = items[:top_n]
    rest = items[top_n:]
    if rest:
        shown.append(("Other categories", sum(amount for _, amount in rest)))

    labels = [name for name, _ in reversed(shown)]
    values = [amount for _, amount in reversed(shown)]

    figure, axes = plt.subplots(figsize=(8, max(4, len(labels) * 0.45)))
    bars = axes.barh(labels, values, color=EXPENSE_COLOR)
    axes.bar_label(bars, fmt="%.0f", padding=3, fontsize=8)
    axes.set_xlabel("EUR spent")
    axes.set_title("Spending by category")
    axes.grid(axis="x", alpha=0.3)
    axes.margins(x=0.12)
    return save_figure(figure, path)


def plot_balance_forecast(forecast, path="output/balance_forecast.png", history=None):
    """Draw the projected balance, with the real history in front of it.

    Args:
        forecast: The projection to draw.
        path: Where to save the PNG.
        history: The transactions, drawn as a running balance. Optional.

    Returns:
        Path: The file that was written.

    Raises:
        ValueError: If the forecast has no points.
    """
    if not forecast.points:
        raise ValueError("nothing to plot: empty forecast")

    figure, axes = plt.subplots(figsize=(10, 4.5))

    if history:
        running = 0.0
        dates = []
        balances = []
        for item in sorted(history, key=lambda item: item.date):
            running += item.amount
            dates.append(item.date)
            balances.append(running)
        axes.plot(dates, balances, color=ACCENT_COLOR, linewidth=1.5, label="Actual balance")

    forecast_dates = [point.date for point in forecast.points]
    forecast_balances = [point.balance for point in forecast.points]
    axes.plot(
        forecast_dates, forecast_balances, color=INCOME_COLOR, linewidth=2,
        linestyle="--", label="Projected balance",
    )
    axes.fill_between(forecast_dates, forecast_balances, alpha=0.12, color=INCOME_COLOR)

    lowest = forecast.minimum_point
    if lowest is not None:
        axes.annotate(
            f"low {lowest.balance:.2f}",
            xy=(lowest.date, lowest.balance),
            xytext=(0, -28),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            arrowprops={"arrowstyle": "->", "color": EXPENSE_COLOR},
        )

    axes.axhline(0, color=EXPENSE_COLOR, linewidth=0.9, linestyle=":")
    axes.set_ylabel("EUR")
    axes.set_title(f"Balance forecast over {forecast.horizon_days} days")
    axes.legend()
    axes.grid(alpha=0.3)
    figure.autofmt_xdate()
    return save_figure(figure, path)


def plot_recurring_overview(series_list, path="output/recurring_overview.png"):
    """Draw what each recurring item costs per month.

    Args:
        series_list: The recurring series to draw.
        path: Where to save the PNG.

    Returns:
        Path: The file that was written.

    Raises:
        ValueError: If there are no series to draw.
    """
    if not series_list:
        raise ValueError("nothing to plot: no recurring series detected")

    ordered = sorted(series_list, key=lambda series: series.monthly_equivalent)
    labels = [f"{series.label[:28]} ({series.period_label})" for series in ordered]
    values = [series.monthly_equivalent for series in ordered]
    colors = [INCOME_COLOR if value > 0 else EXPENSE_COLOR for value in values]

    figure, axes = plt.subplots(figsize=(9, max(4, len(labels) * 0.42)))
    bars = axes.barh(labels, values, color=colors)
    axes.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    axes.axvline(0, color="grey", linewidth=0.8)
    axes.set_xlabel("EUR per month (normalised)")
    axes.set_title("Recurring payments and income")
    axes.grid(axis="x", alpha=0.3)
    axes.margins(x=0.18)
    return save_figure(figure, path)


def plot_all(summaries, spending, series_list, forecast, output_dir="output", history=None):
    """Draw every chart of the package into one folder.

    A chart whose data is missing is skipped instead of raising an error.

    Args:
        summaries: Monthly summaries.
        spending: Spending per category.
        series_list: The recurring series.
        forecast: The balance projection.
        output_dir: Folder to write the PNG files into.
        history: The transactions, for the forecast chart. Optional.

    Returns:
        list: The paths of the charts that were written.
    """
    folder = Path(output_dir)
    written = []
    
    with suppress(ValueError):
        written.append(plot_monthly_cashflow(summaries, folder / "monthly_cashflow.png"))

    with suppress(ValueError):
        written.append(plot_category_breakdown(spending, folder / "category_breakdown.png"))

    with suppress(ValueError):
        written.append(plot_recurring_overview(series_list, folder / "recurring_overview.png"))

    with suppress(ValueError):
        written.append(
            plot_balance_forecast(forecast, folder / "balance_forecast.png", history=history)
        )

    return written