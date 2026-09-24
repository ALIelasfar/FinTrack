"""Tests for :mod:`fintrack.categorization`."""

import json
from datetime import date

import pytest

from fintrack.categorization import Categorizer
from fintrack.models import Transaction


def test_default_rules_match_known_merchants():
    categorizer = Categorizer()
    assert categorizer.categorize("REWE Markt Dortmund") == "Groceries"
    assert categorizer.categorize("Netflix.com") == "Subscriptions"
    assert categorizer.categorize("Hausverwaltung Miete") == "Housing"


def test_unknown_descriptions_fall_back_to_default():
    assert Categorizer().categorize("Zzz unknown payee") == "Other"
    assert Categorizer(default_category="Unsorted").categorize("Zzz") == "Unsorted"


def test_longer_keyword_wins():
    categorizer = Categorizer({"Shopping": ["amazon"], "Subscriptions": ["amazon prime"]})
    assert categorizer.categorize("AMAZON PRIME Monthly") == "Subscriptions"
    assert categorizer.categorize("Amazon Marketplace") == "Shopping"


def test_add_rule_extends_a_category():
    categorizer = Categorizer()
    categorizer.add_rule("Groceries", "Trinkgut")
    assert categorizer.categorize("Trinkgut Getraenke") == "Groceries"


def test_add_rule_without_keywords_is_rejected():
    with pytest.raises(ValueError):
        Categorizer().add_rule("Groceries")


def test_categorize_all_preserves_existing_categories():
    transactions = [
        Transaction(date(2024, 1, 1), "REWE Markt", "-10", category="Manual"),
        Transaction(date(2024, 1, 2), "REWE Markt", "-10"),
    ]
    result = Categorizer().categorize_all(transactions)
    assert [t.category for t in result] == ["Manual", "Groceries"]

    overwritten = Categorizer().categorize_all(transactions, overwrite=True)
    assert [t.category for t in overwritten] == ["Groceries", "Groceries"]


def test_json_round_trip(tmp_path):
    path = tmp_path / "rules.json"
    Categorizer({"Coffee": ["starbucks"]}).to_json(path)
    assert json.loads(path.read_text())["Coffee"] == ["starbucks"]
    assert Categorizer.from_json(path).categorize("STARBUCKS 12") == "Coffee"


def test_from_json_rejects_non_object(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        Categorizer.from_json(path)
