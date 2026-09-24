"""Tests for the recommendations, the text report and the command line."""

import pytest

from fintrack.advice import generate_recommendations
from fintrack.cli import main
from fintrack.forecasting import forecast_balance
from fintrack.models import MonthlySummary
from fintrack.recurring import detect_recurring
from fintrack.reporting import build_report, format_table, looks_numeric
from fintrack.summary import monthly_summaries, spending_by_category


def test_no_recommendations_without_data():
    assert generate_recommendations([], []) == []


def test_a_low_savings_rate_gives_a_warning():
    summaries = [
        MonthlySummary(f"2024-{month:02d}", 2000.00, 1980.00) for month in range(1, 6)
    ]
    findings = generate_recommendations(summaries, [])
    assert any(item.severity == "warning" and "Savings rate" in item.title for item in findings)


def test_a_high_savings_rate_suggests_investing():
    summaries = [
        MonthlySummary(f"2024-{month:02d}", 2000.00, 1200.00) for month in range(1, 6)
    ]
    findings = generate_recommendations(summaries, [])
    assert any("Healthy savings rate" in item.title for item in findings)


def test_running_out_of_money_gives_a_critical_finding(sample_transactions):
    summaries = monthly_summaries(sample_transactions)
    series = detect_recurring(sample_transactions)
    forecast = forecast_balance(
        sample_transactions, horizon_days=90, starting_balance=-2000, series=series
    )
    findings = generate_recommendations(summaries, series, forecast)
    assert any(item.severity == "critical" for item in findings)


def test_recommendations_come_out_sorted_by_urgency(sample_transactions):
    summaries = monthly_summaries(sample_transactions)
    series = detect_recurring(sample_transactions)
    findings = generate_recommendations(summaries, series)
    assert [item.rank for item in findings] == sorted(item.rank for item in findings)


def test_subscriptions_are_added_up(sample_transactions):
    series = detect_recurring(sample_transactions)
    findings = generate_recommendations(monthly_summaries(sample_transactions), series)
    assert any("recurring payments cost" in item.title for item in findings)


def test_looks_numeric_tells_numbers_from_words():
    assert looks_numeric("-12.50")
    assert looks_numeric("15%")
    assert not looks_numeric("Netflix")


def test_format_table_lines_up_and_checks_the_rows():
    rendered = format_table([["a", 1], ["bb", 22]], ["letter", "number"])
    assert rendered.splitlines()[0].startswith("letter")
    assert format_table([], ["x"]) == "(no data)"
    with pytest.raises(ValueError):
        format_table([["a"]], ["x", "y"])


def test_the_report_has_all_of_its_sections(sample_transactions):
    summaries = monthly_summaries(sample_transactions)
    series = detect_recurring(sample_transactions)
    forecast = forecast_balance(sample_transactions, horizon_days=30, series=series)
    report = build_report(
        sample_transactions,
        summaries,
        spending_by_category(sample_transactions),
        series,
        forecast,
        generate_recommendations(summaries, series, forecast),
    )
    for heading in (
        "Overview",
        "Month by month",
        "Spending by category",
        "Detected recurring payments",
        "Balance forecast",
        "Largest merchants",
        "Recommendations",
    ):
        assert heading in report


@pytest.mark.parametrize(
    "argv",
    [
        ["analyze", "--days", "30"],
        ["recurring"],
        ["categories"],
        ["categories", "--month", "2025-03"],
        ["forecast", "--days", "30", "--show-days", "5"],
    ],
)
def test_every_command_works_on_the_bundled_data(argv, capsys):
    assert main(argv) == 0
    assert capsys.readouterr().out.strip()


def test_a_missing_file_gives_an_error_message(capsys):
    assert main(["analyze", "--file", "does-not-exist.csv"]) == 1
    assert "error:" in capsys.readouterr().err


def test_an_empty_month_gives_an_error_message(capsys):
    assert main(["categories", "--month", "1999-01"]) == 1
    assert "No transactions found" in capsys.readouterr().err


def test_generate_sample_writes_a_file_we_can_read_back(tmp_path, capsys):
    destination = tmp_path / "generated.csv"
    assert main(["generate-sample", "-o", str(destination), "--months", "6"]) == 0
    assert destination.exists()
    assert main(["analyze", "--file", str(destination), "--days", "20"]) == 0
    assert "FINTRACK ANALYSIS REPORT" in capsys.readouterr().out


def test_charts_are_written_to_the_output_folder(tmp_path):
    argv = ["analyze", "--days", "30", "--charts", "-o", str(tmp_path), "--save-report"]
    assert main(argv) == 0
    assert (tmp_path / "report.txt").exists()
    assert list(tmp_path.glob("*.png"))
