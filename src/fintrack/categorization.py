"""Sorting transactions into categories using keyword rules.

A rule is just a category name plus the words that hint at it. The default
rules cover common German and international shops; you can add your own or
load a completely different set from a JSON file.
"""

import json
from pathlib import Path

__all__ = ["DEFAULT_RULES", "Categorizer"]

#: The default rules: category name to the keywords that point at it.
DEFAULT_RULES = {
    "Income": ["salary", "gehalt", "lohn", "payroll", "refund", "erstattung", "dividend"],
    "Housing": ["rent", "miete", "hausverwaltung", "nebenkosten", "grundsteuer"],
    "Utilities": ["stadtwerke", "electric", "strom", "gas", "wasser", "energie", "vattenfall"],
    "Internet & Phone": ["telekom", "vodafone", "o2", "1und1", "internet", "mobilfunk"],
    "Groceries": ["rewe", "aldi", "lidl", "edeka", "penny", "netto", "supermarkt", "kaufland"],
    "Restaurants": ["restaurant", "cafe", "coffee", "pizzeria", "imbiss", "lieferando", "bistro"],
    "Transport": [
        "db bahn", "deutsche bahn", "vrr", "dsw21", "ticket", "tankstelle", "shell", "aral",
        "uber", "taxi",
    ],
    "Subscriptions": [
        "netflix", "spotify", "disney", "amazon prime", "youtube premium", "icloud", "dropbox",
        "github",
    ],
    "Health": ["apotheke", "pharmacy", "arzt", "zahnarzt", "optiker"],
    "Insurance": ["versicherung", "insurance", "allianz", "huk", "barmenia"],
    "Fitness": ["gym", "fitness", "mcfit", "urban sports"],
    "Shopping": ["amazon", "zalando", "mediamarkt", "saturn", "ikea", "h&m", "decathlon"],
    "Education": ["uni", "university", "tu dortmund", "buchhandlung", "udemy", "coursera"],
    "Savings & Transfers": ["savings", "sparen", "transfer", "depot", "etf", "broker"],
}


class Categorizer:
    """Gives each transaction a category based on keywords in its description.

    Upper and lower case do not matter, and a keyword only has to appear
    somewhere inside the description. The longest matching keyword wins, so a
    rule for ``"amazon prime"`` beats the more general ``"amazon"``.

    Attributes:
        rules: Category name to list of keywords.
        default_category: Category used when nothing matches.

    Examples:
        >>> categorizer = Categorizer()
        >>> categorizer.categorize("REWE Markt Dortmund")
        'Groceries'
        >>> categorizer.categorize("Something unknown")
        'Other'
    """

    def __init__(self, rules=None, default_category="Other"):
        """Set up the categorizer.

        Args:
            rules: Category name to keywords. Uses :data:`DEFAULT_RULES` if
                left out.
            default_category: Category used when no keyword matches.
        """
        if rules is None:
            rules = DEFAULT_RULES

        self.rules = {}
        for category, keywords in rules.items():
            self.rules[category] = [keyword.lower() for keyword in keywords]
        self.default_category = default_category

    @property
    def categories(self):
        """list: All category names this categorizer knows, sorted."""
        names = set(self.rules)
        names.add(self.default_category)
        return sorted(names)

    def add_rule(self, category, *keywords):
        """Add keywords to a category, creating the category if it is new.

        Args:
            category: Name of the category.
            *keywords: One or more keywords to add to it.

        Raises:
            ValueError: If no keyword was given.
        """
        if not keywords:
            raise ValueError("at least one keyword is required")
        existing = self.rules.get(category, [])
        self.rules[category] = existing + [keyword.lower() for keyword in keywords]

    def categorize(self, description):
        """Find the category for a single description.

        Args:
            description: The transaction description.

        Returns:
            str: The best matching category, or the default category.
        """
        text = description.lower()
        best_category = self.default_category
        best_length = 0

        for category, keywords in self.rules.items():
            for keyword in keywords:
                if keyword in text and len(keyword) > best_length:
                    best_category = category
                    best_length = len(keyword)
        return best_category

    def categorize_all(self, transactions, overwrite=False):
        """Give a category to a whole list of transactions.

        Args:
            transactions: The transactions to categorise.
            overwrite: If True, categories that are already set get replaced.

        Returns:
            list: A new list of transactions with categories filled in.
        """
        result = []
        for item in transactions:
            if item.category and not overwrite:
                result.append(item)
            else:
                result.append(item.with_category(self.categorize(item.description)))
        return result

    @classmethod
    def from_json(cls, path, default_category="Other"):
        """Build a categorizer from a JSON file of rules.

        Args:
            path: A JSON file such as ``{"Groceries": ["rewe", "aldi"]}``.
            default_category: Category used when no keyword matches.

        Returns:
            Categorizer: A categorizer using the rules from that file.

        Raises:
            ValueError: If the file does not hold a JSON object.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a JSON object of category -> keywords")
        return cls(data, default_category)

    def to_json(self, path):
        """Write the current rules to a JSON file.

        Args:
            path: Destination file. Missing folders are created.

        Returns:
            Path: The file that was written.
        """
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.rules, indent=2), encoding="utf-8")
        return destination

    def __repr__(self):
        """Return a short description of the categorizer."""
        return (
            f"Categorizer(categories={len(self.rules)}, "
            f"default={self.default_category!r})"
        )
