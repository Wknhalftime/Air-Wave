import logging
import re
import unicodedata
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airwave.core.models import ArtistAlias, ProposedSplit
from airwave.core.normalization import Normalizer

logger = logging.getLogger(__name__)


class IdentityResolver:
    """Handles artist identity resolution, including alias mapping and collaboration splitting.
    Uses a 'Clean-First' strategy to resolve artist strings before song matching.
    """

    # Markers that indicate a collaboration or feature
    # Used for both splitting ("A feat. B") and cleaning ("feat. B")
    METADATA_MARKERS = [
        "feat.",
        "feat",
        "featuring",
        "ft.",
        "ft",
        "w/",
        "with",
        "f.",
        "f/",
        "featuring",
        "and",
        "&",
    ]

    # Regex patterns for splitting artists (e.g. " w/ ")
    # We construct these from markers to ensure coverage
    SPLIT_PATTERNS = [
        r"\s+w/\s*",  # Specific handling for w/ (slash)
        r"\s+f/\s*",  # Specific handling for f/
        r"\s+(?:feat|ft|featuring|with|and|&)\.?\s+",  # Grouped words
        r"\s*/\s*",  # Generic slash (lower priority)
    ]

    # Confidence Scores
    CONFIDENCE_HIGH = 0.95
    CONFIDENCE_MEDIUM = 0.7

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the IdentityResolver with a database session."""
        self.session = session

    async def resolve_batch(
        self, raw_artist_names: List[str]
    ) -> Dict[str, str]:
        """Resolves a batch of raw artist names to their 'clean' identities.

        Args:
            raw_artist_names: List of raw artist strings to resolve.

        Returns:
            Dictionary mapping {raw_name: cleaned_name}.
        """
        unique_names = list(set(raw_artist_names))
        results = {}

        # 1. Check existing Alias Map (Case-Insensitive)
        # Use func.lower to handle SQLite's case-sensitive IN clause for strings
        lower_unique = [n.lower() for n in unique_names]
        stmt = select(ArtistAlias).where(
            func.lower(ArtistAlias.raw_name).in_(lower_unique)
        )
        db_results = await self.session.execute(stmt)
        aliases = db_results.scalars().all()

        # alias_map: {normalized_raw_name: resolved_name or raw_name if is_null}
        alias_map = {}
        for a in aliases:
            rn_lower = a.raw_name.lower()
            if a.is_null:
                alias_map[rn_lower] = a.raw_name
            elif a.resolved_name:
                alias_map[rn_lower] = a.resolved_name

        unresolved = []
        for name in unique_names:
            n_lower = name.lower()
            if n_lower in alias_map:
                results[name] = alias_map[n_lower]
            else:
                unresolved.append(name)
        # 2. Heuristic Splitting for Unresolved Names
        # Batch check ProposedSplit for all unresolved names to avoid N+1
        split_stmt = select(ProposedSplit.raw_artist).where(
            ProposedSplit.raw_artist.in_(unresolved)
        )
        split_results = await self.session.execute(split_stmt)
        already_proposed = set(split_results.scalars().all())

        for name in unresolved:
            proposed_split = self._detect_split(name)

            if proposed_split:
                # If it's a split, and not already proposed, register it
                if name not in already_proposed:
                    await self._register_proposed_split(name, proposed_split)
                # Return the 'clean' joined name to help the matcher find existing clean tracks
                # Using semicolon as it's rare in artist names and not used in splitting logic
                results[name] = "; ".join(proposed_split)
            else:
                # No split detected, but let's at least Title Case the unresolved name for better matching
                results[name] = self._clean_artist_name(name)

        return results

    def _detect_split(self, name: str) -> Optional[List[str]]:
        """Detects if an artist string contains multiple artists using regex.

        Args:
            name: Raw artist string.

        Returns:
            List of cleaned, individual artist names if a split is found, else None.
        """
        # Exclude known single entities with split-like characters (e.g. 'AC/DC')
        KNOWN_EXCEPTIONS = ["AC/DC", "P!nk", "Panic! At The Disco"]
        if name in KNOWN_EXCEPTIONS:
            return None

        for pattern in self.SPLIT_PATTERNS:
            parts = re.split(pattern, name, flags=re.IGNORECASE)
            if len(parts) > 1:
                # Clean each part
                cleaned_parts = [
                    self._clean_artist_name(p) for p in parts if p.strip()
                ]
                # Ensure we still have at least 2 distinct artists after cleaning
                if len(set(cleaned_parts)) > 1:
                    return cleaned_parts

        return None

    def _clean_artist_name(self, name: str) -> str:
        """Cleans an individual artist name: Strip accents, Title Case, remove debris.

        Args:
            name: Raw name string.

        Returns:
            normalized name string.
        """
        # 0. Strip accents using shared helper
        name = Normalizer.strip_accents(name)

        # 1. Strip and remove leading/trailing debris like 'f/', 'ft.', or just 'f' if it's a leftover
        # Handle cases like "SLASH F" where F was left after splitting by /
        # 1. Strip and remove leading/trailing debris
        # We target specific "feature" markers that are not part of the name
        # Excludes '&' and 'and' because they can be valid name prefixes/suffixes
        debris_markers = ["feat", "ft", "featuring", "w/", "f/", "with"]

        # Build regex: Start of string or End of string markers
        # e.g., ^(feat\.?|ft\.?)\s+ OR \s+(feat\.?|ft\.?)$
        patterns = []
        for m in debris_markers:
            # Escape markers like 'w/' or 'f.'
            safe_m = re.escape(m)
            # Handle optional dot if not present in marker
            if not m.endswith("."):
                safe_m += r"\.?"

            # Add word boundary check to prevent matching 'feat' in 'feather'
            # For markers with symbols (w/), \b might not work as expected, rely on space
            if m in ["w/", "f/"]:
                patterns.append(rf"^\s*{safe_m}\s+")
                patterns.append(rf"\s+{safe_m}\s*$")
            else:
                patterns.append(rf"^\s*{safe_m}\b\s*")  # Leading
                patterns.append(rf"\s+\b{safe_m}\s*$")  # Trailing

        debris_pattern = "|".join(patterns)
        name = re.sub(debris_pattern, "", name, flags=re.IGNORECASE).strip()

        # 2. Title Case logic
        if not name:
            return ""

        words = name.split()
        title_cased = []
        for w in words:
            # Keep short acronyms or known uppercase (KORN -> Korn is fine, but GNR -> GNR)
            if (
                w.isupper()
                and len(w) <= 4
                and w.lower() not in ["and", "the", "with", "feat"]
            ):
                title_cased.append(w)
            else:
                title_cased.append(w.capitalize())

        return " ".join(title_cased)

    async def _register_proposed_split(
        self, raw_name: str, proposed_parts: List[str]
    ) -> None:
        """Registers a potential artist split in the database for user review.

        Args:
            raw_name: The original ambiguous string.
            proposed_parts: List of detected individual artists.
        """
        # Check if already exists
        stmt = select(ProposedSplit).where(ProposedSplit.raw_artist == raw_name)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            # High confidence if we found specific feat/split markers
            # High confidence if we found specific feat/split markers
            # Use the class constant for consistency
            markers = ["/", "feat", "ft", "w/", "with", "featuring"]
            has_marker = any(m in raw_name.lower() for m in markers)
            confidence = (
                self.CONFIDENCE_HIGH if has_marker else self.CONFIDENCE_MEDIUM
            )

            new_proposal = ProposedSplit(
                raw_artist=raw_name,
                proposed_artists=proposed_parts,
                status="PENDING",
                confidence=confidence,
            )
            self.session.add(new_proposal)
            logger.info(
                f"Registered heuristic split for '{raw_name}': {proposed_parts}"
            )

    async def add_alias(
        self, raw_name: str, resolved_name: str, verified: bool = True
    ) -> None:
        """Manually add or update an artist alias.

        Args:
            raw_name: Incorrect or variation name.
            resolved_name: Canonical artist name.
            verified: Whether this alias is manually verified.
        """
        stmt = select(ArtistAlias).where(ArtistAlias.raw_name == raw_name)
        result = await self.session.execute(stmt)
        alias = result.scalar_one_or_none()

        if alias:
            alias.resolved_name = resolved_name
            alias.is_verified = verified
        else:
            alias = ArtistAlias(
                raw_name=raw_name,
                resolved_name=resolved_name,
                is_verified=verified,
            )
            self.session.add(alias)
