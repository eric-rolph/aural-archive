"""
Aural Archive — Generic Extractor
====================================
Fallback extractor that attempts yt-dlp for any URL.
yt-dlp supports 1000+ sites, so this catches most things
that the specialized extractors don't explicitly claim.
"""

import re
from pathlib import Path

from .base import BaseExtractor
from .youtube import YouTubeExtractor


class GenericExtractor(BaseExtractor):
    """
    Fallback extractor for arbitrary URLs.

    Delegates to yt-dlp under the hood (since yt-dlp supports an enormous
    range of sites). This extractor has the lowest priority — it matches
    any http/https URL that no other extractor claimed.
    """

    name = "generic"

    _URL_PATTERNS = [
        re.compile(r"https?://"),  # matches any URL
    ]

    def __init__(self):
        # Reuse YouTube extractor's yt-dlp-based implementation
        self._delegate = YouTubeExtractor()

    def extract_info(self, url: str) -> dict:
        """Delegate to yt-dlp metadata extraction."""
        info = self._delegate.extract_info(url)
        if info:
            info["extractor"] = self.name
        return info

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
        """Delegate to yt-dlp download, tag as 'generic' extractor."""
        result = self._delegate.download(
            url=url,
            output_dir=output_dir,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            output_format=output_format,
            title_hint=title_hint,
            extra_args=extra_args,
        )
        if result:
            result["extractor"] = self.name
        return result
