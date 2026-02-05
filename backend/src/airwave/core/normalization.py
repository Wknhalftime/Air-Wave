"""Text normalization utilities for consistent matching and identity resolution.

This module provides centralized text processing functions for normalizing
artist names, track titles, and generating consistent signatures. The
normalization pipeline handles unicode, accents, punctuation, articles,
version tags, and collaboration markers.

All matching operations in Airwave use these normalization functions to
ensure consistent comparisons between messy broadcast logs and library metadata.

Typical usage example:
    artist = Normalizer.clean_artist("The Beatles")  # "beatles"
    title = Normalizer.clean("Hey Jude (Remastered)")  # "hey jude"
    signature = Normalizer.generate_signature(artist, title)
    artists = Normalizer.split_artists("A feat. B & C")  # ["a", "b", "c"]
"""

import hashlib
import re
import unicodedata
from typing import List


class Normalizer:
    """Centralized text normalization and signature generation utilities.

    This class provides static methods for normalizing text in various contexts:
    - Basic cleaning for titles and general text
    - Aggressive artist name normalization for matching
    - Artist collaboration splitting
    - Version tag extraction (Live, Remix, etc.)
    - MD5 signature generation for identity bridges

    All methods are static and stateless for easy reuse across the application.
    """

    # Regex for common version/mix descriptors in parentheses or brackets
    # Note: Longer matches (e.g., "remastered") must come before shorter ones (e.g., "remaster")
    VERSION_REGEX = re.compile(
        r"[\(\[]\s*(remastered|instrumental|unplugged|acoustic|explicit|"
        r"lyrical|live|remix|mix|edit|version|demo|radio|clean|"
        r"cover|remaster|track|fade|lyrics|dub|telethon|lv|original|alt).*?[\)\]]",
        re.IGNORECASE,
    )

    @staticmethod
    def strip_accents(text: str) -> str:
        """Remove accents from unicode text using NFKD normalization.

        Normalizes unicode characters to their decomposed form (NFKD) and
        removes combining characters (accents, diacritics). This is used
        as a preprocessing step in all text normalization methods.

        Args:
            text: Text string potentially containing accented characters.

        Returns:
            Text with accents removed. Empty string if input is None or empty.

        Example:
            >>> Normalizer.strip_accents("Café")
            'Cafe'
            >>> Normalizer.strip_accents("Beyoncé")
            'Beyonce'
        """
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        return "".join([c for c in text if not unicodedata.combining(c)])

    @staticmethod
    def remove_remaster_tags(text: str) -> str:
        """Remove remaster qualifiers from text.

        Removes common remaster indicators like "(Remastered 2023)" or
        "- Remaster" from text. This is used in both title and artist
        normalization to focus on the core content.

        Args:
            text: Text potentially containing remaster tags.

        Returns:
            Text with remaster tags removed.

        Example:
            >>> Normalizer.remove_remaster_tags("Song (Remastered 2023)")
            'Song '
            >>> Normalizer.remove_remaster_tags("Artist - Remaster 2020")
            'Artist '
        """
        text = re.sub(r"\(.*remaster.*\)", "", text)
        text = re.sub(r" - remaster\s?\d*", "", text)
        return text

    @staticmethod
    def clean(text: str) -> str:
        """Basic text cleaning for titles and general text.

        Performs unicode normalization, accent stripping, and punctuation
        removal. This is the standard cleaning method for track titles.

        Args:
            text: Raw text string to normalize.

        Returns:
            Normalized lowercase string with accents and punctuation removed.
            Empty string if input is None or empty.

        Example:
            >>> Normalizer.clean("Café (Remastered 2023)")
            'cafe'
            >>> Normalizer.clean("Rock & Roll!")
            'rock and roll'
            >>> Normalizer.clean("AC/DC")
            'ac dc'
        """
        if not text:
            return ""

        # 1. Strip accents
        text = Normalizer.strip_accents(text)
        text = text.lower().strip()

        # 2. Remove remaster tags
        text = Normalizer.remove_remaster_tags(text)

        # 3. Normalize special characters
        text = text.replace("&", "and")
        text = text.replace("+", "and")
        text = text.replace("/", " ")

        # 4. Strip all non-word characters (except spaces)
        text = re.sub(r"[^\w\s]", "", text)

        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def generate_signature(artist: str, title: str) -> str:
        """Create a consistent MD5 hash signature for log entries.

        Generates a deterministic hash from normalized artist and title,
        used for identity bridge lookups. The same raw log entry will
        always produce the same signature.

        Uses clean_artist() for artist normalization to ensure consistency
        with the rest of the matching pipeline (which removes articles like
        "The", "A", "An").

        Args:
            artist: Raw artist name from broadcast log.
            title: Raw track title from broadcast log.

        Returns:
            32-character hexadecimal MD5 hash string.

        Example:
            >>> Normalizer.generate_signature("The Beatles", "Hey Jude")
            'a1b2c3d4e5f6...'  # Consistent hash
        """
        payload = f"{Normalizer.clean_artist(artist)}|{Normalizer.clean(title)}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def clean_artist(text: str) -> str:
        """Aggressive artist name normalization for matching.

        Performs more aggressive normalization than clean(), specifically
        designed for artist name matching. Removes articles (The, A, An),
        normalizes separators, and handles special characters.

        Args:
            text: Raw artist name to normalize.

        Returns:
            Aggressively normalized lowercase artist name.
            Empty string if input is None or empty.

        Example:
            >>> Normalizer.clean_artist("The Rolling Stones")
            'rolling stones'
            >>> Normalizer.clean_artist("AC/DC")
            'ac dc'
            >>> Normalizer.clean_artist("Guns N' Roses")
            'guns n roses'
        """
        if not text:
            return ""

        # 1. Strip accents
        text = Normalizer.strip_accents(text)
        text = text.lower().strip()

        # 2. Remove remaster tags
        text = Normalizer.remove_remaster_tags(text)

        # 3. Remove leading articles (The, A, An)
        text = re.sub(r"^(the|a|an)\s+", "", text)

        # 4. Normalize special characters
        text = text.replace("&", "and")
        text = text.replace("+", "and")
        text = text.replace("/", " ")
        # Note: Commas are removed in step 5 (punctuation removal)
        # This preserves numbers like "10,000" → "10000"

        # 5. Remove all punctuation/symbols (but keep spaces)
        text = re.sub(r"[^\w\s]", "", text)

        # 6. Normalize spacing
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def split_artists(text: str) -> List[str]:
        """Split a collaboration string into individual artist names.

        Handles common separators like &, /, feat., with, and, etc.
        Returns deduplicated list of normalized artist names while
        preserving order.

        Args:
            text: Artist string potentially containing multiple artists.
                Example: "Artist A feat. Artist B & Artist C"

        Returns:
            List of normalized individual artist names.
            Empty list if input is None or empty.

        Example:
            >>> Normalizer.split_artists("A feat. B & C")
            ['a', 'b', 'c']
            >>> Normalizer.split_artists("The Beatles with Eric Clapton")
            ['beatles', 'eric clapton']
        """
        if not text:
            return []

        # Standardize separators to a pipe for easier splitting
        separators = [
            r"\s+feat\.?\s+",
            r"\s+ft\.?\s+",
            r"\s+featuring\s+",
            r"\s+with\s+",
            r"\s+&\s+",
            r"\s+/\s+",
            r",\s+",
            r"\s+and\s+",
        ]

        normalized = text
        for sep in separators:
            normalized = re.sub(sep, "|", normalized, flags=re.IGNORECASE)

        # Split and clean
        artists = [
            Normalizer.clean_artist(a)
            for a in normalized.split("|")
            if a.strip()
        ]

        # Deduplicate while preserving order
        seen = set()
        unique_artists = []
        for a in artists:
            if a.lower() not in seen:
                unique_artists.append(a)
                seen.add(a.lower())

        return unique_artists

    @staticmethod
    def extract_version_type(title: str) -> tuple[str, str]:
        """Parse title for version information and extract clean title.

        Detects version tags like (Live), [Remix], (Acoustic) and separates
        them from the base title. Returns both the clean title and the
        detected version type.

        Args:
            title: Raw track title potentially containing version tags.

        Returns:
            Tuple of (clean_title, version_type).
            version_type defaults to "Original" if no tag detected.

        Example:
            >>> Normalizer.extract_version_type("Song Title (Live)")
            ('Song Title', 'Live')
            >>> Normalizer.extract_version_type("Song Title [Remix]")
            ('Song Title', 'Remix')
            >>> Normalizer.extract_version_type("Song Title")
            ('Song Title', 'Original')
        """
        if not title:
            return "", "Original"

        match = Normalizer.VERSION_REGEX.search(title)
        if match:
            # Extract found version type (e.g. "Live")
            version_type = match.group(1).title()

            # Remove the version tag from title
            clean_title = Normalizer.VERSION_REGEX.sub("", title).strip()

            # Cleanup any leftover empty brackets () or []
            clean_title = re.sub(r"\s*[\(\[]\s*[\)\]]", "", clean_title).strip()

            return clean_title, version_type

        return title, "Original"
