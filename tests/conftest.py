"""Fixtures that every test file can use."""

from datetime import date

import pytest

from fintrack.sample_data import generate_sample_transactions


@pytest.fixture(scope="session")
def sample_transactions():
    """A fixed 24 month transaction history, the same every run."""
    return generate_sample_transactions(months=24, seed=7, end=date(2025, 6, 30))
