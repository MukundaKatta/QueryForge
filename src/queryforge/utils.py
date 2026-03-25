"""Utility functions for QueryForge."""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces and strip leading/trailing whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def strip_currency(text: str) -> str:
    """Remove currency symbols ($, EUR, etc.) from text."""
    return re.sub(r"[$€£¥]", "", text)


def pluralize(word: str) -> str:
    """Naive English pluralization."""
    if word.endswith("s"):
        return word
    if word.endswith("y"):
        return word[:-1] + "ies"
    return word + "s"


def singularize(word: str) -> str:
    """Naive English singularization."""
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word
