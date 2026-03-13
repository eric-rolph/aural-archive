"""
Aural Archive — Base Extractor
================================
Abstract base class for all media extractors. Each site/source type
gets its own subclass with URL matching and download logic.

Inspired by yt-dlp's decentralized Extractor architecture.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path


class BaseExtractor(ABC):
    """
    Abstract base class for media extractors.

    Subclasses must implement:
      - name: human-readable extractor name
      - _URL_PATTERNS: list of compiled regex patterns for URL matching
      - extract_info(): fetch metadata without downloading
      - download(): download and convert media
    """

    name: str = "base"
    _URL_PATTERNS: list[re.Pattern] = []

    def suitable(self, url: str) -> bool:
        """Check if this extractor can handle the given URL."""
        return any(pattern.search(url) for pattern in self._URL_PATTERNS)

    @abstractmethod
    def extract_info(self, url: str) -> dict:
        """
        Fetch metadata for the given URL without downloading.

        Returns a dict with keys like: id, title, url, duration, channel,
        description, tags, upload_date, thumbnail, etc.
        """
        ...

    @abstractmethod
    def download(
        self,
        url: str,
        output_dir: Path,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        output_format: str = "wav",
        title_hint: str = "",
        extra_args: list[str] | None = None,
    ) -> dict | None:
        """
        Download media from *url*, convert to the target format.

        Returns a manifest entry dict on success, or None on failure.
        The dict should include at minimum:
          file, source_url, title, duration_seconds, sample_rate,
          bit_depth, format, downloaded_at, extractor
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
