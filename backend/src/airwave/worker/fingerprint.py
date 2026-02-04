import os
from typing import Optional, Tuple

import acoustid
from loguru import logger

from airwave.core.config import settings


class Fingerprinter:
    """Handles audio fingerprinting and metadata lookup via AcoustID.

    Wraps the `acoustid` library and manages the `fpcalc` binary dependency.
    """

    def __init__(self) -> None:
        """Initializes the fingerprinter and locates the fpcalc binary."""
        self.api_key = settings.ACOUSTID_API_KEY

        # Locate fpcalc relative to the project root
        # Expected location: /backend/bin/fpcalc.exe
        self.fpcalc_path = settings.BASE_DIR / "bin" / "fpcalc.exe"

        if not self.fpcalc_path.exists():
            logger.warning(
                f"fpcalc not found at {self.fpcalc_path}. Fingerprinting disabled."
            )
            self.fpcalc_running = False
        else:
            self.fpcalc_running = True
            # Set environment variable for pyacoustid
            os.environ["FPCALC"] = str(self.fpcalc_path)

    def fingerprint_file(self, path: str) -> Optional[Tuple[float, str]]:
        """Generates a fingerprint for a given audio file.

        Args:
            path: Absolute path to the audio file.

        Returns:
            A tuple of (duration, fingerprint_string) or None if generation fails.
        """
        if not self.fpcalc_running:
            return None

        try:
            duration, fingerprint = acoustid.fingerprint_file(path)
            # fingerprint is bytes, decode to string
            return duration, fingerprint.decode("utf-8")
        except Exception:
            # Log exception but don't crash the worker
            logger.exception(f"Fingerprint generation failed for {path}")
            return None

    def lookup(self, path: str) -> Optional[Tuple[str, str]]:
        """Identifies a track's Artist and Title using AcoustID service.

        Args:
            path: Absolute path to the audio file.

        Returns:
            A tuple of (Artist, Title) or None if not identified.
        """
        if not self.api_key or not self.fpcalc_running:
            return None

        try:
            # fingerprint_file returns duration and fingerprint bytes
            duration, fingerprint = acoustid.fingerprint_file(path)

            # Perform API Lookup
            results = acoustid.lookup(self.api_key, fingerprint, duration)

            if results["results"]:
                # Get best result
                best_match = results["results"][0]
                if best_match.get("recordings"):
                    recording = best_match["recordings"][0]

                    title = recording.get("title")
                    # Artists is a list of dictionaries
                    artists = recording.get("artists", [])
                    artist_name = (
                        artists[0].get("name") if artists else "Unknown"
                    )

                    if title and artist_name:
                        return artist_name, title

            return None

        except acoustid.WebServiceError:
            logger.exception("AcoustID API Error")
            return None
        except Exception:
            logger.exception(f"Lookup failed for {path}")
            return None
