"""Bundled example data shipped with :mod:`fintrack`."""

from pathlib import Path

__all__ = ["sample_data_path"]

#: File name of the bundled example transaction history.
SAMPLE_FILE = "sample_transactions.csv"


def sample_data_path() -> Path:
    """Return the path to the bundled example transaction history.

    Returns:
        Absolute path to the CSV file that ships with the package.

    Raises:
        FileNotFoundError: If the package was installed without its data files.

    Examples:
        >>> sample_data_path().name
        'sample_transactions.csv'
    """
    path = Path(__file__).parent / SAMPLE_FILE
    if not path.exists():  # pragma: no cover - only on a broken installation
        raise FileNotFoundError(f"bundled dataset is missing: {path}")
    return path
