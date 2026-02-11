"""Number to words utility."""

from __future__ import annotations

from num2words import num2words


def amount_to_words_inr(amount: float) -> str:
    """Convert numeric amount to Indian Rupee words."""
    rounded = round(float(amount), 2)
    rupees = int(rounded)
    paise = int(round((rounded - rupees) * 100))

    rupee_words = num2words(rupees, to="cardinal", lang="en_IN").replace("-", " ")
    if paise:
        paise_words = num2words(paise, to="cardinal", lang="en_IN").replace("-", " ")
        return f"{rupee_words.title()} Rupees and {paise_words.title()} Paise Only"
    return f"{rupee_words.title()} Rupees Only"

