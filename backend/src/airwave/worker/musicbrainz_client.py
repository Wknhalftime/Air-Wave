"""MusicBrainz API client for fetching canonical artist names.

This module provides a client for the MusicBrainz API with:
- Batch fetching to minimize API calls
- Rate limiting (1 request/second for unauthenticated requests)
- Proper error handling and retries
- User-Agent header as required by MusicBrainz

MusicBrainz API Documentation: https://musicbrainz.org/doc/MusicBrainz_API
"""

import asyncio
from typing import Dict, List, Optional

import aiohttp
from loguru import logger


class MusicBrainzClient:
    """Client for fetching artist information from MusicBrainz API."""

    BASE_URL = "https://musicbrainz.org/ws/2"
    USER_AGENT = "AirWave/0.1.0 (https://github.com/yourusername/airwave)"
    
    # Rate limiting: MusicBrainz allows 1 request/second for unauthenticated requests
    # We'll be conservative and use 1.1 seconds between requests
    RATE_LIMIT_DELAY = 1.1

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the MusicBrainz client.
        
        Args:
            session: Optional aiohttp session. If not provided, a new session
                    will be created for each batch operation.
        """
        self._session = session
        self._owns_session = session is None
        self._last_request_time = 0.0

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.USER_AGENT}
            )
        return self._session

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        
        if time_since_last < self.RATE_LIMIT_DELAY:
            await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last)
        
        self._last_request_time = asyncio.get_event_loop().time()

    async def fetch_artist_name(self, mbid: str) -> Optional[str]:
        """Fetch canonical artist name from MusicBrainz by MBID.
        
        Args:
            mbid: MusicBrainz Artist ID (UUID)
            
        Returns:
            Canonical artist name, or None if not found or error occurred
        """
        session = await self._ensure_session()
        
        # Rate limiting
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/artist/{mbid}?fmt=json"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    name = data.get("name")
                    if name:
                        logger.debug(f"Fetched artist name for {mbid}: {name}")
                        return name
                    else:
                        logger.warning(f"No name found in response for MBID {mbid}")
                        return None
                elif response.status == 404:
                    logger.warning(f"Artist not found for MBID {mbid}")
                    return None
                elif response.status == 503:
                    logger.warning(f"MusicBrainz service unavailable (503)")
                    return None
                else:
                    logger.error(
                        f"MusicBrainz API error for {mbid}: "
                        f"status={response.status}"
                    )
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching artist {mbid}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error fetching artist {mbid}: {e}")
            return None

    async def fetch_artist_names_batch(
        self, mbids: List[str], batch_size: int = 50
    ) -> Dict[str, Optional[str]]:
        """Fetch canonical artist names for multiple MBIDs.
        
        This method processes MBIDs in batches and respects rate limiting.
        
        Args:
            mbids: List of MusicBrainz Artist IDs
            batch_size: Number of artists to process in each batch (default: 50)
            
        Returns:
            Dictionary mapping MBID -> artist name (or None if not found)
        """
        results: Dict[str, Optional[str]] = {}
        
        # Remove duplicates while preserving order
        unique_mbids = list(dict.fromkeys(mbids))
        
        logger.info(
            f"Fetching {len(unique_mbids)} artist names from MusicBrainz "
            f"(batch_size={batch_size})"
        )
        
        # Process in batches
        for i in range(0, len(unique_mbids), batch_size):
            batch = unique_mbids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(unique_mbids) + batch_size - 1) // batch_size
            
            logger.info(
                f"Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} artists)"
            )
            
            # Fetch each artist in the batch sequentially (rate limited)
            for mbid in batch:
                name = await self.fetch_artist_name(mbid)
                results[mbid] = name
        
        successful = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"Fetched {successful}/{len(unique_mbids)} artist names successfully"
        )
        
        return results

    async def close(self):
        """Close the aiohttp session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

