"""Reading and writing transaction data in CSV format.

Bank exports differ a lot: different column names, date formats, decimal
separators and delimiters. :func:`load_transactions` tries to work all of
that out on its own.
"""

import csv
from datetime import date, datetime
from pathlib import Path

from .models import Transaction, format_money, round_money

__all__ = [
    "TransactionParseError",
    "iter_months",
    "load_transactions",
    "parse_amount",
    "parse_date",
    "save_transactions",
]

#: Date patterns tried in order when reading a date cell.
DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%y"]

#: Accepted header names for each field we care about, all in lower case.
COLUMN_ALIASES = {
    "date": ["date", "datum", "booking date", "buchungstag", "transaction date", "valuta"],
    "description": [
        "description", "text", "purpose", "beschreibung", "verwendungszweck", "payee", "name",
    ],
    "amount": ["amount", "betrag", "value", "sum", "umsatz"],
    "account": ["account", "konto", "iban", "account name"],
    "category": ["category", "kategorie", "type"],
}

#: Columns the file must contain, otherwise we cannot build a transaction.
REQUIRED_COLUMNS = ["date", "description", "amount"]


class TransactionParseError(ValueError):
    """Raised when a row of the input file cannot be turned into a transaction."""


def parse_date(raw):
    """Read a date cell using the patterns in :data:`DATE_FORMATS`.

    Args:
        raw: The raw cell content. Spaces around it are ignored.

    Returns:
        date: The parsed calendar date.

    Raises:
        TransactionParseError: If none of the known patterns fit.

    Examples:
        >>> parse_date("01.03.2024")
        datetime.date(2024, 3, 1)
    """
    text = raw.strip()
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise TransactionParseError(f"unrecognised date format: {raw!r}")


def parse_amount(raw):
    """Read an amount cell, handling both German and English number formats.

    ``1.234,56`` and ``1,234.56`` both mean the same thing. Currency symbols
    and a sign at either end are ignored.

    Args:
        raw: The raw cell content.

    Returns:
        float: The amount, rounded to two decimals.

    Raises:
        TransactionParseError: If the cell holds no number.

    Examples:
        >>> parse_amount("-1.234,56 EUR")
        -1234.56
        >>> parse_amount("1,234.56")
        1234.56
    """
    text = raw.strip()
    if not text:
        raise TransactionParseError("empty amount")

    negative = text.startswith("-") or text.endswith("-")

    # Throw away everything that is not a digit or a separator.
    cleaned = ""
    for character in text:
        if character.isdigit() or character in ".,":
            cleaned += character
    if not any(character.isdigit() for character in cleaned):
        raise TransactionParseError(f"no digits in amount: {raw!r}")

    if "," in cleaned and "." in cleaned:
        # Whichever separator comes last is the decimal separator.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # A lone comma is a decimal separator, unless it groups three digits.
        head, _, tail = cleaned.rpartition(",")
        if len(tail) == 3 and head:
            cleaned = head + tail
        else:
            cleaned = f"{head}.{tail}"

    value = round_money(cleaned)
    if negative and value > 0:
        return -value
    return value


def find_columns(fieldnames):
    """Work out which real column holds each field we need.

    Args:
        fieldnames: The header row of the CSV file.

    Returns:
        dict: Maps ``"date"``, ``"description"`` and so on to the real header.

    Raises:
        TransactionParseError: If a required column is missing.
    """
    headers = {}
    for name in fieldnames:
        if name:
            headers[name.strip().lower()] = name

    columns = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in headers:
                columns[field_name] = headers[alias]
                break

    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise TransactionParseError(
            f"missing required column(s): {', '.join(missing)}; "
            f"found headers: {', '.join(fieldnames)}"
        )
    return columns


def load_transactions(path, encoding="utf-8", default_account="main", strict=True):
    """Load transactions from a CSV file.

    Args:
        path: Path to the CSV file.
        encoding: Text encoding of the file.
        default_account: Account name used if the file has no account column.
        strict: If True, a broken row stops the import. If False, broken rows
            are skipped.

    Returns:
        list: The transactions, sorted with the oldest first.

    Raises:
        FileNotFoundError: If the file does not exist.
        TransactionParseError: If the header is unusable, or if strict is on
            and a row cannot be read.

    Examples:
        >>> from fintrack.data import sample_data_path
        >>> transactions = load_transactions(sample_data_path())
        >>> len(transactions) > 100
        True
    """
    file_path = Path(path)
    text = file_path.read_text(encoding=encoding)
    if not text.strip():
        raise TransactionParseError(f"{file_path} is empty")

    # Guess whether the file uses commas, semicolons or tabs.
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if reader.fieldnames is None:
        raise TransactionParseError(f"{file_path} has no header row")
    columns = find_columns(reader.fieldnames)

    transactions = []
    line_number = 1
    for row in reader:
        line_number += 1
        try:
            transactions.append(row_to_transaction(row, columns, default_account))
        except TransactionParseError as error:
            if strict:
                raise TransactionParseError(f"{file_path}:{line_number}: {error}") from error

    transactions.sort(key=lambda item: (item.date, item.description))
    return transactions


def row_to_transaction(row, columns, default_account="main"):
    """Turn one CSV row into a :class:`~fintrack.models.Transaction`.

    Args:
        row: One row of the file as a dictionary.
        columns: The column mapping from :func:`find_columns`.
        default_account: Account name used if the file has no account column.

    Returns:
        Transaction: The transaction built from the row.

    Raises:
        TransactionParseError: If the description is empty or a cell is broken.
    """
    description = (row.get(columns["description"]) or "").strip()
    if not description:
        raise TransactionParseError("empty description")

    account = default_account
    if "account" in columns:
        account = (row.get(columns["account"]) or "").strip() or default_account

    category = None
    if "category" in columns:
        category = (row.get(columns["category"]) or "").strip() or None

    return Transaction(
        date=parse_date(row.get(columns["date"]) or ""),
        description=description,
        amount=parse_amount(row.get(columns["amount"]) or ""),
        account=account,
        category=category,
    )


def save_transactions(transactions, path):
    """Write transactions to a CSV file that :func:`load_transactions` can read.

    Args:
        transactions: The transactions to write.
        path: Destination file. Missing folders are created.

    Returns:
        Path: The file that was written.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "description", "amount", "account", "category"])
        for item in transactions:
            writer.writerow(
                [
                    item.date.isoformat(),
                    item.description,
                    format_money(item.amount),
                    item.account,
                    item.category or "",
                ]
            )
    return destination


def iter_months(transactions):
    """Yield every ``YYYY-MM`` month found in the transactions, in order.

    Args:
        transactions: The transactions to look through.

    Yields:
        str: Each month, without repeats.
    """
    seen = set()
    for item in transactions:
        if item.month not in seen:
            seen.add(item.month)
            yield item.month
