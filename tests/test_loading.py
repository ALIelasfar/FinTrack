"""Tests for reading and writing CSV files."""

from datetime import date

import pytest

from fintrack.data import sample_data_path
from fintrack.loading import (
    TransactionParseError,
    find_columns,
    load_transactions,
    parse_amount,
    parse_date,
    save_transactions,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-03-01", date(2024, 3, 1)),
        ("01.03.2024", date(2024, 3, 1)),
        ("01/03/2024", date(2024, 3, 1)),
        ("  2024/03/01 ", date(2024, 3, 1)),
    ],
)
def test_parse_date_accepts_common_formats(raw, expected):
    assert parse_date(raw) == expected


def test_parse_date_rejects_unknown_format():
    with pytest.raises(TransactionParseError):
        parse_date("March 1st, 2024")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12.50", 12.50),
        ("12,50", 12.50),
        ("-1.234,56 EUR", -1234.56),
        ("1,234.56", 1234.56),
        ("1,234", 1234.0),
        ("895", 895.0),
    ],
)
def test_parse_amount_handles_both_number_styles(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_amount_rejects_empty_and_text():
    with pytest.raises(TransactionParseError):
        parse_amount("   ")
    with pytest.raises(TransactionParseError):
        parse_amount("abc")


def test_find_columns_matches_german_and_english_headers():
    columns = find_columns(["Buchungstag", "Verwendungszweck", "Betrag"])
    assert columns["date"] == "Buchungstag"
    assert columns["amount"] == "Betrag"


def test_find_columns_complains_about_missing_columns():
    with pytest.raises(TransactionParseError, match="missing required column"):
        find_columns(["foo", "bar"])


def test_load_the_bundled_example_dataset():
    transactions = load_transactions(sample_data_path())
    assert len(transactions) > 100
    assert transactions == sorted(transactions, key=lambda item: (item.date, item.description))


def test_load_handles_semicolons_and_german_columns(tmp_path):
    path = tmp_path / "bank.csv"
    path.write_text(
        "Buchungstag;Verwendungszweck;Betrag\n"
        "01.03.2024;REWE Markt;-12,50\n"
        "27.03.2024;Gehalt;2.500,00\n",
        encoding="utf-8",
    )
    transactions = load_transactions(path)
    assert [item.amount for item in transactions] == [-12.50, 2500.00]


def test_load_raises_on_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(TransactionParseError, match="missing required column"):
        load_transactions(path)


def test_broken_rows_are_skipped_when_not_strict(tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text(
        "date,description,amount\n2024-03-01,Good,-10.00\nnope,Bad,-10.00\n", encoding="utf-8"
    )
    assert len(load_transactions(path, strict=False)) == 1
    with pytest.raises(TransactionParseError):
        load_transactions(path, strict=True)


def test_saving_and_loading_gives_the_same_data(tmp_path, sample_transactions):
    original = sorted(sample_transactions[:50], key=lambda item: (item.date, item.description))
    path = save_transactions(original, tmp_path / "out.csv")
    assert load_transactions(path) == original
