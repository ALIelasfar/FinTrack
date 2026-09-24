"""The command line interface.

Run ``python -m fintrack --help`` to see what it can do.
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .advice import generate_recommendations
from .categorization import Categorizer
from .data import sample_data_path
from .forecasting import forecast_balance
from .loading import load_transactions, save_transactions
from .models import format_money
from .recurring import detect_recurring
from .reporting import build_report, format_table, section
from .sample_data import generate_sample_transactions
from .summary import monthly_summaries, spending_by_category

__all__ = ["build_parser", "main"]


def build_parser():
    """Build the argument parser with all of its sub-commands.

    Returns:
        argparse.ArgumentParser: The ready-to-use parser.
    """
    parser = argparse.ArgumentParser(
        prog="fintrack",
        description=(
            "Analyse a history of bank transactions: find recurring payments, "
            "forecast the account balance and get savings recommendations."
        ),
        epilog="Example: python -m fintrack analyze --days 120 --charts",
    )
    parser.add_argument("--version", action="version", version=f"fintrack {__version__}")

    # Options that several sub-commands share, defined once.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-f", "--file", type=Path, default=None,
        help="CSV file with transactions (default: the bundled example data)",
    )
    common.add_argument(
        "--rules", type=Path, default=None, help="JSON file with your own category rules"
    )
    common.add_argument(
        "--encoding", default="utf-8", help="text encoding of the CSV file (default: utf-8)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze", parents=[common], help="run the full analysis and print a report"
    )
    analyze.add_argument("--days", type=int, default=90, help="forecast length in days")
    analyze.add_argument("--balance", default=None, help="the balance to forecast from")
    analyze.add_argument("--charts", action="store_true", help="also draw the PNG charts")
    analyze.add_argument(
        "-o", "--output-dir", type=Path, default=Path("output"),
        help="folder for the charts and the saved report (default: output)",
    )
    analyze.add_argument(
        "--save-report", action="store_true", help="write the report to output-dir/report.txt"
    )

    subparsers.add_parser("recurring", parents=[common], help="list the recurring payments only")

    categories = subparsers.add_parser(
        "categories", parents=[common], help="show spending grouped by category"
    )
    categories.add_argument("--month", default=None, help="show one month only (YYYY-MM)")

    forecast = subparsers.add_parser(
        "forecast", parents=[common], help="project the balance into the future"
    )
    forecast.add_argument("--days", type=int, default=90, help="forecast length in days")
    forecast.add_argument("--balance", default=None, help="the balance to start from")
    forecast.add_argument("--show-days", type=int, default=20, help="how many rows to print")

    generate = subparsers.add_parser(
        "generate-sample", help="write a fresh made-up dataset to a CSV file"
    )
    generate.add_argument(
        "-o", "--output", type=Path, default=Path("transactions.csv"), help="destination file"
    )
    generate.add_argument("--months", type=int, default=18, help="months of history to make")
    generate.add_argument("--seed", type=int, default=42, help="random seed")

    return parser


def load_and_categorize(args):
    """Load the CSV file the user chose and give every transaction a category.

    Args:
        args: The parsed command line arguments.

    Returns:
        list: The categorised transactions.
    """
    path = args.file or sample_data_path()
    transactions = load_transactions(path, encoding=args.encoding)

    categorizer = Categorizer.from_json(args.rules) if args.rules else Categorizer()
    return categorizer.categorize_all(transactions)


def command_analyze(args):
    """Run the ``analyze`` sub-command.

    Args:
        args: The parsed command line arguments.

    Returns:
        int: 0 when everything worked.
    """
    transactions = load_and_categorize(args)
    summaries = monthly_summaries(transactions)
    spending = spending_by_category(transactions)
    series = detect_recurring(transactions)
    forecast = forecast_balance(
        transactions, horizon_days=args.days, starting_balance=args.balance, series=series
    )
    recommendations = generate_recommendations(summaries, series, forecast)

    chart_paths = []
    if args.charts:
        from .visualization import plot_all

        chart_paths = plot_all(
            summaries, spending, series, forecast, args.output_dir, history=transactions
        )

    report = build_report(
        transactions, summaries, spending, series, forecast, recommendations, chart_paths
    )
    print(report)

    if args.save_report:
        destination = Path(args.output_dir) / "report.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report, encoding="utf-8")
        print(f"Report written to {destination}")
    return 0


def command_recurring(args):
    """Run the ``recurring`` sub-command.

    Args:
        args: The parsed command line arguments.

    Returns:
        int: 0 when everything worked.
    """
    series_list = detect_recurring(load_and_categorize(args))
    rows = []
    for series in series_list:
        rows.append(
            [
                series.label[:34],
                series.period_label,
                format_money(series.average_amount),
                format_money(series.monthly_equivalent),
                format_money(series.yearly_equivalent),
                series.next_due.isoformat(),
                f"{series.confidence:.0%}",
            ]
        )
    headers = ["Description", "Period", "Amount", "Per month", "Per year", "Next due", "Conf."]
    print(section("Detected recurring payments"))
    print(format_table(rows, headers))
    return 0


def command_categories(args):
    """Run the ``categories`` sub-command.

    Args:
        args: The parsed command line arguments.

    Returns:
        int: 0 when everything worked, 1 if the chosen month has no data.
    """
    transactions = load_and_categorize(args)
    if args.month:
        transactions = [item for item in transactions if item.month == args.month]
        if not transactions:
            print(f"No transactions found for {args.month}.", file=sys.stderr)
            return 1

    spending = spending_by_category(transactions)
    total = sum(spending.values())
    rows = []
    for name, amount in spending.items():
        share = f"{amount / total:.1%}" if total else "-"
        rows.append([name, format_money(amount), share])

    title = "Spending by category"
    if args.month:
        title += f" in {args.month}"
    print(section(title))
    print(format_table(rows, ["Category", "Total", "Share"]))
    return 0


def command_forecast(args):
    """Run the ``forecast`` sub-command.

    Args:
        args: The parsed command line arguments.

    Returns:
        int: 0 when everything worked.
    """
    transactions = load_and_categorize(args)
    forecast = forecast_balance(
        transactions, horizon_days=args.days, starting_balance=args.balance
    )

    rows = forecast.to_rows()
    step = max(1, len(rows) // max(1, args.show_days))
    print(section(f"Balance forecast over {forecast.horizon_days} days"))
    print(format_table(rows[::step], ["Date", "Balance", "Expected bookings"]))

    lowest = forecast.minimum_point
    if lowest is not None:
        print(
            f"\nLowest projected balance: {format_money(lowest.balance)} "
            f"on {lowest.date.isoformat()}"
        )
    negative = forecast.first_negative
    if negative is not None:
        print(f"WARNING: balance is projected to go negative on {negative.date.isoformat()}.")
    return 0


def command_generate_sample(args):
    """Run the ``generate-sample`` sub-command.

    Args:
        args: The parsed command line arguments.

    Returns:
        int: 0 when everything worked.
    """
    transactions = generate_sample_transactions(months=args.months, seed=args.seed)
    destination = save_transactions(transactions, args.output)
    print(f"Wrote {len(transactions)} transactions to {destination}")
    return 0


def main(argv=None):
    """Start the command line interface.

    Args:
        argv: The arguments to read. Defaults to what the user typed.

    Returns:
        int: 0 when everything worked, 1 when something went wrong.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "analyze":
            return command_analyze(args)
        elif args.command == "recurring":
            return command_recurring(args)
        elif args.command == "categories":
            return command_categories(args)
        elif args.command == "forecast":
            return command_forecast(args)
        elif args.command == "generate-sample":
            return command_generate_sample(args)
    except (FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1
