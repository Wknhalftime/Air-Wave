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
    # Includes format variants, edition types, years, and part numbers
    VERSION_REGEX = re.compile(
        r"[\(\[]\s*("
        r"remastered?|instrumental|unplugged|acoustic|explicit|"
        r"lyrical|live|remix|mix|edit|version|demo|radio|clean|"
        r"cover|track|fade|lyrics|dub|telethon|lv|original|alt|"
        r"single|album|extended|short|mono|stereo|"
        r"deluxe|bonus|anniversary|special|limited|"
        r"\d{4}|"
        r"pt\.?\s*\d+|part\s*\d+"
        r").*?[\)\]]",
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
        if not text:
            return ""
        text = re.sub(r"\(.*remaster.*\)", "", text)
        text = re.sub(r" - remaster\s?\d*", "", text)
        return text

    @staticmethod
    def remove_year_brackets(text: str) -> str:
        """Remove year indicators in brackets/parentheses.

        Removes patterns like (2018), [1999], (2023 Remaster), etc.

        Args:
            text: Text potentially containing year brackets.

        Returns:
            Text with year brackets removed.

        Example:
            >>> Normalizer.remove_year_brackets("Song Title (2018)")
            'Song Title'
            >>> Normalizer.remove_year_brackets("Song [1999 Remaster]")
            'Song'
        """
        if not text:
            return ""
        # Standalone years: (2018), [1999]
        text = re.sub(r"\s*[\(\[]\s*\d{4}\s*[\)\]]", "", text)
        # Years with additional text: (2023 Remaster), [1999 Deluxe]
        text = re.sub(r"\s*[\(\[]\s*\d{4}[^\)\]]*[\)\]]", "", text)
        return text.strip()

    @staticmethod
    def remove_truncation_markers(text: str) -> str:
        """Remove truncation indicators like (...) or [...].

        Radio stations often truncate long titles with ellipsis markers.

        Args:
            text: Text potentially containing truncation markers.

        Returns:
            Text with truncation markers removed.

        Example:
            >>> Normalizer.remove_truncation_markers("Long Song Title (...)")
            'Long Song Title'
            >>> Normalizer.remove_truncation_markers("Artist Name [...]")
            'Artist Name'
        """
        if not text:
            return ""
        # Bracketed ellipsis: (...), [...]
        text = re.sub(r"\s*[\(\[]\s*\.{3,}\s*[\)\]]", "", text)
        # Unicode ellipsis
        text = text.replace("\u2026", "")
        # Standalone ellipsis
        text = re.sub(r"\s*\.{3,}\s*", " ", text)
        return text.strip()

    @staticmethod
    def clean(text: str) -> str:
        """Enhanced text cleaning for titles with comprehensive normalization.

        Normalization steps:
        1. Smart quote normalization (', ", ", ' → straight quotes)
        2. Unicode NFKD normalization + accent stripping
        3. Lowercase + trim
        4. Remove remaster tags
        5. Remove year brackets (2018), [1999]
        6. Remove truncation markers (...), [...]
        7. Remove feat. suffix (feat., ft., featuring, with)
        8. Normalize special characters (&→and, +→and, /→space)
        9. Remove all punctuation
        10. Normalize whitespace

        Args:
            text: Raw text to normalize.

        Returns:
            Normalized text suitable for matching.

        Example:
            >>> Normalizer.clean("Song's Title (2018) feat. Artist")
            'songs title'
            >>> Normalizer.clean("Rock & Roll!")
            'rock and roll'
        """
        if not text:
            return ""

        # 1. Smart quote normalization (before accent stripping)
        text = text.replace("\u2018", "'").replace("\u2019", "'")  # Smart single
        text = text.replace("\u201c", '"').replace("\u201d", '"')  # Smart double

        # 2. Strip accents
        text = Normalizer.strip_accents(text)
        text = text.lower().strip()

        # 3. Remove remaster tags
        text = Normalizer.remove_remaster_tags(text)

        # 4. Remove year brackets
        text = Normalizer.remove_year_brackets(text)

        # 5. Remove truncation markers
        text = Normalizer.remove_truncation_markers(text)

        # 6. Remove feat. suffix from titles (optional space after keyword: "ft. X" or "ft.X")
        # IMPORTANT: Use word boundaries (\b) to avoid matching partial words
        # e.g., "f." should not match "fire", "feat" should not match "feature"
        # NOTE: "with" is NOT included because it appears in many legitimate song titles
        # (e.g., "Fight Fire with Fire", "With or Without You", "Dancing with Myself")
        text = re.sub(
            r"\s+\b(feat\.?|ft\.?|f\.?|featuring)\b\s*.*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 7. Normalize special characters
        text = text.replace("&", "and")
        text = text.replace("+", "plus")
        text = text.replace("/", " ")

        # 8. Strip all non-word characters (except spaces)
        text = re.sub(r"[^\w\s]", "", text)

        # 9. Normalize whitespace
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

        # 3. Remove year brackets and truncation (AC2: same as clean())
        text = Normalizer.remove_year_brackets(text)
        text = Normalizer.remove_truncation_markers(text)

        # 4. Remove leading articles (The, A, An)
        text = re.sub(r"^(the|a|an)\s+", "", text)

        # 5. Remove collaboration keyword suffixes (duet, feat., ft., featuring, vs.) and anything after
        # Use \b before and (?!\w) after (not \b after, since punctuation e.g. "feat." breaks \b)
        # Require period for feat/ft to avoid stripping "Little Feat" (band name)
        text = re.sub(
            r"\s+\b(duet|feat\.|ft\.|f\.|featuring|vs\.?)(?!\w)\s*.*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 6. Normalize special characters
        text = text.replace("&", "and")
        text = text.replace("+", "plus")
        text = text.replace("/", " ")
        # Note: Commas are removed in step 7 (punctuation removal)
        # This preserves numbers like "10,000" → "10000"

        # 7. Remove all punctuation/symbols (but keep spaces)
        text = re.sub(r"[^\w\s]", "", text)

        # 8. Normalize spacing
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def normalize_artist_full(text: str) -> str:
        """Normalize artist name preserving collaboration strings for Work primary.

        Same as clean_artist but does NOT strip feat./duet/etc and what follows.
        Used for Work.artist_id so "Daft Punk feat. Pharrell Williams" becomes
        "daft punk feat pharrell williams" (one artist), while split_artists
        still extracts individual artists for WorkArtist links.
        """
        if not text:
            return ""

        # 1. Strip accents
        text = Normalizer.strip_accents(text)
        text = text.lower().strip()

        # 2. Remove remaster tags
        text = Normalizer.remove_remaster_tags(text)

        # 3. Remove year brackets and truncation
        text = Normalizer.remove_year_brackets(text)
        text = Normalizer.remove_truncation_markers(text)

        # 4. Remove leading articles
        text = re.sub(r"^(the|a|an)\s+", "", text)

        # 5. NO collaboration strip - preserve full string

        # 6. Normalize special characters
        text = text.replace("&", "and")
        text = text.replace("+", "plus")
        text = text.replace("/", " ")

        # 7. Remove all punctuation/symbols (feat. -> feat)
        text = re.sub(r"[^\w\s]", "", text)

        # 8. Normalize spacing
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

        # Standardize separators to a pipe for easier splitting.
        # Longer patterns first. F/ and W/ must precede generic / for "KORN F/SKRILLEX".
        separators = [
            r"\s+feat\.?\s+",
            r"\s+ft\.?\s+",
            r"\s+featuring\s+",
            r"\s+duet\s+with\s+",  # "Artist A duet with Artist B"
            r"\s+duet\s+",  # "2pac duet" or "Artist A duet Artist B"
            r"\s+vs\.?\s+",  # "Artist A vs Artist B"
            r"\s+with\s+",
            r"\s+F/\s*",  # Featuring shorthand, e.g. "KORN F/SKRILLEX"
            r"\s+W/\s*",  # With shorthand
            r"\s+&\s+",
            r"\s+/\s+",
            # Comma: split "A, B" and "Smith, John" but NOT "10,000" (thousands separator)
            r"(?<!\d),\s*(?!\d)",
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

    @staticmethod
    def extract_version_type_enhanced(
        title: str, album_title: str | None = None
    ) -> tuple[str, str]:
        """Enhanced version extraction with multiple strategies and negative patterns.

        Improvements over extract_version_type():
        - Extracts ALL version tags, not just first
        - Handles dash-separated versions ("Song - Live Version")
        - Extracts embedded remix/mix descriptors without delimiters
        - Uses album context for live detection (conservative)
        - Classifies ambiguous parentheses using heuristics
        - Negative patterns for part numbers and subtitles

        Args:
            title: Raw track title potentially containing version tags
            album_title: Optional album title for context-based detection

        Returns:
            Tuple of (clean_title, version_type).
            version_type can be combined (e.g., "Live / Radio Edit")

        Examples:
            >>> Normalizer.extract_version_type_enhanced("Song (Live) (Radio Edit)")
            ('Song', 'Live / Radio')

            >>> Normalizer.extract_version_type_enhanced("Song - Live Version")
            ('Song', 'Live')

            >>> Normalizer.extract_version_type_enhanced("Song davidson ospina radio mix")
            ('Song', 'Radio')  # Embedded remix descriptor extracted

            >>> Normalizer.extract_version_type_enhanced("Song the video mix")
            ('Song', 'Video')  # Generic mix pattern extracted

            >>> Normalizer.extract_version_type_enhanced("Song (Part 1)")
            ('Song (Part 1)', 'Original')  # Part numbers NOT extracted

            >>> Normalizer.extract_version_type_enhanced("Song (The Ballad)")
            ('Song (The Ballad)', 'Original')  # Subtitles NOT extracted

            >>> Normalizer.extract_version_type_enhanced("Song", album_title="Live at Wembley")
            ('Song', 'Live')  # Album context used
        """
        if not title:
            return "", "Original"

        version_parts = []
        clean_title = title

        # Strategy 1: Extract parentheses/brackets with version keywords
        # BUT check negative patterns first to avoid extracting part numbers/subtitles
        extracted_positions = []  # Track what we've extracted to avoid duplicates
        matches = list(Normalizer.VERSION_REGEX.finditer(title))
        for match in matches:
            paren_content = match.group(1)
            paren_lower = paren_content.lower()
            words = paren_content.split()

            # NEGATIVE PATTERN 1: Skip part numbers (different works, not versions)
            if re.search(r"\b(part|pt\.?)\s*\d+\b", paren_lower):
                continue

            # NEGATIVE PATTERN 2: Skip subtitles starting with "The"
            if paren_lower.startswith("the ") and len(words) > 2:
                continue

            # Extract this version tag
            version_parts.append(paren_content.title())
            clean_title = clean_title.replace(match.group(0), "")
            extracted_positions.append((match.start(), match.end()))

        # Strategy 1.5: Extract parentheses/brackets with mix/remix descriptors
        # Handles cases like "(the video mix)", "(davidson ospina radio mix)"
        # This catches mix descriptors that don't start with a keyword (missed by Strategy 1)
        mix_paren_pattern = r"[\(\[]\s*([^)\]]*(?:mix|remix|edit|version)[^)\]]*)\s*[\)\]]"
        mix_matches = list(re.finditer(mix_paren_pattern, title, re.IGNORECASE))
        for match in mix_matches:
            # Skip if already extracted by Strategy 1
            if any(match.start() >= start and match.end() <= end for start, end in extracted_positions):
                continue

            paren_content = match.group(1).strip()
            paren_lower = paren_content.lower()

            # NEGATIVE PATTERN: Skip part numbers
            if re.search(r"\b(part|pt\.?)\s*\d+\b", paren_lower):
                continue

            # Classify the version type based on keywords
            if 'radio' in paren_lower or 'edit' in paren_lower:
                version_parts.append('Radio')
            elif 'video' in paren_lower:
                version_parts.append('Video')
            elif any(word in paren_lower for word in ['club', 'dance']):
                version_parts.append('Remix')
            elif 'instrumental' in paren_lower:
                version_parts.append('Instrumental')
            elif 'acoustic' in paren_lower:
                version_parts.append('Acoustic')
            elif 'extended' in paren_lower:
                version_parts.append('Extended')
            elif 'live' in paren_lower:
                version_parts.append('Live')
            else:
                version_parts.append('Remix')

            clean_title = clean_title.replace(match.group(0), "").strip()
            extracted_positions.append((match.start(), match.end()))

        # Strategy 2: Check for dash-separated versions
        # "Song Title - Live Version" or "Song Title - Radio Edit"
        dash_pattern = r"\s+-\s+(live|remix|mix|edit|version|demo|radio|acoustic|unplugged)\b.*$"
        dash_match = re.search(dash_pattern, clean_title, re.IGNORECASE)
        if dash_match:
            version_parts.append(dash_match.group(1).title())
            clean_title = re.sub(dash_pattern, "", clean_title, flags=re.IGNORECASE)

        # Strategy 3: Album context heuristics (conservative)
        # Only apply if no version info already extracted
        if album_title and not version_parts:
            album_lower = album_title.lower()
            live_keywords = ["live", "concert", "unplugged", "acoustic session"]
            if any(keyword in album_lower for keyword in live_keywords):
                version_parts.append("Live")

        # Strategy 4: Extract embedded remix/mix descriptors (no delimiters)
        # These patterns catch descriptive remix names embedded in titles
        # Examples: "song davidson ospina radio mix", "song the video mix"
        #
        # Note: We use capitalized words to identify remix artist names (e.g., "Davidson Ospina")
        # to avoid matching common lowercase words like "to give radio mix"
        embedded_patterns = [
            # Named remixes with capitalized names: "Davidson Ospina Radio Mix"
            # This pattern requires at least one capital letter in the remix artist name
            (r'\s+([A-Z]\w+\s+){1,2}(radio|video|club|dance)\s+mix$', 'named_remix'),

            # Generic "the X mix" patterns at end
            # Examples: "the video mix", "the conversation mix"
            (r'\s+the\s+\w+\s+mix$', 'generic_mix'),

            # Common mix types at end of title (simple patterns)
            (r'\s+(radio|video|club|dance|extended|instrumental|vocal|dub|acoustic)\s+mix$', 'mix_type'),
            (r'\s+(radio|video|club|dance|extended)\s+edit$', 'edit_type'),
            (r'\s+(radio|video|club|dance)\s+version$', 'version_type'),
        ]

        for pattern, pattern_type in embedded_patterns:
            match = re.search(pattern, clean_title, re.IGNORECASE)
            if match:
                descriptor = match.group(0).strip()
                clean_title = clean_title[:match.start()].strip()

                # Classify the version type based on keywords
                descriptor_lower = descriptor.lower()
                if 'radio' in descriptor_lower or 'edit' in descriptor_lower:
                    version_parts.append('Radio')
                elif 'video' in descriptor_lower:
                    version_parts.append('Video')
                elif any(word in descriptor_lower for word in ['club', 'dance']):
                    version_parts.append('Remix')
                elif 'instrumental' in descriptor_lower:
                    version_parts.append('Instrumental')
                elif 'acoustic' in descriptor_lower:
                    version_parts.append('Acoustic')
                elif 'extended' in descriptor_lower:
                    version_parts.append('Extended')
                else:
                    version_parts.append('Remix')

                # Only extract first embedded pattern to avoid over-extraction
                break

        # Strategy 5: Handle remaining parentheses with negative patterns
        remaining_parens = re.findall(r"[\(\[]([^\)\]]+)[\)\]]", clean_title)
        for paren_content in remaining_parens:
            words = paren_content.split()
            paren_lower = paren_content.lower()

            # NEGATIVE PATTERN 1: Skip part numbers (different works, not versions)
            if re.search(r"\b(part|pt\.?)\s*\d+\b", paren_lower):
                continue

            # NEGATIVE PATTERN 2: Skip subtitles starting with "The"
            if paren_lower.startswith("the ") and len(words) > 2:
                continue

            # Extract if short and contains version keywords
            if len(words) <= 3 and any(
                word in paren_lower
                for word in ["edit", "mix", "version", "cut", "take", "session"]
            ):
                version_parts.append(paren_content.title())
                clean_title = clean_title.replace(f"({paren_content})", "")
                clean_title = clean_title.replace(f"[{paren_content}]", "")

        # Clean up the title
        clean_title = re.sub(r"\s*[\(\[]\s*[\)\]]", "", clean_title)  # Empty brackets
        clean_title = re.sub(r"\s+", " ", clean_title).strip()

        # Combine version parts
        if version_parts:
            # Deduplicate while preserving order
            seen = set()
            unique_parts = []
            for part in version_parts:
                if part.lower() not in seen:
                    unique_parts.append(part)
                    seen.add(part.lower())
            version_type = " / ".join(unique_parts)
        else:
            version_type = "Original"

        return clean_title, version_type
