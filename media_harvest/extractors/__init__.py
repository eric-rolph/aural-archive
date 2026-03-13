"""
Aural Archive — Extractor Registry
=====================================
Auto-discovers all BaseExtractor subclasses and provides
a single entry point: get_extractor(url).

Extractors are tried in priority order (specialized first,
generic last).
"""

from .base import BaseExtractor
from .generic import GenericExtractor
from .youtube import YouTubeExtractor

# Registry — ordered by specificity (most specific first, generic last)
_EXTRACTORS: list[BaseExtractor] = [
    YouTubeExtractor(),
    GenericExtractor(),     # always last — matches any URL
]


def get_extractor(url: str) -> BaseExtractor:
    """
    Return the best-matching extractor for the given URL.

    Tries extractors in priority order. The GenericExtractor at the end
    ensures we always return something (it matches any http/https URL).

    Raises ValueError if no extractor matches (shouldn't happen with
    GenericExtractor in the list).
    """
    for extractor in _EXTRACTORS:
        if extractor.suitable(url):
            return extractor
    raise ValueError(f"No extractor found for URL: {url}")


def list_extractors() -> list[BaseExtractor]:
    """Return all registered extractors."""
    return list(_EXTRACTORS)
