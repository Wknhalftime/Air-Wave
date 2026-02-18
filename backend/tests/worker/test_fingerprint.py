"""Tests for airwave.worker.fingerprint."""

from pathlib import Path
from unittest.mock import patch

import pytest

from airwave.worker.fingerprint import Fingerprinter


class TestFingerprinterInit:
    """Tests for Fingerprinter initialization."""

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=False)
    def test_fpcalc_missing_disables_fingerprinting(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "test-key"
        mock_settings.BASE_DIR = Path("/project")
        f = Fingerprinter()
        assert f.fpcalc_running is False

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_fpcalc_present_enables_fingerprinting(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "test-key"
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        assert f.fpcalc_running is True


class TestFingerprintFile:
    """Tests for fingerprint_file."""

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=False)
    def test_returns_none_when_disabled(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        f = Fingerprinter()
        assert f.fingerprint_file("/path/to/file.mp3") is None

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_returns_duration_and_fingerprint_on_success(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        with patch("airwave.worker.fingerprint.acoustid.fingerprint_file") as m:
            m.return_value = (120.5, b"fingerprint_string")
            result = f.fingerprint_file("/music/song.mp3")
        assert result == (120.5, "fingerprint_string")

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_returns_none_on_exception(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        with patch("airwave.worker.fingerprint.acoustid.fingerprint_file") as m:
            m.side_effect = OSError("file not found")
            result = f.fingerprint_file("/bad/path.mp3")
        assert result is None


class TestLookup:
    """Tests for lookup."""

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=False)
    def test_returns_none_when_disabled(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        f = Fingerprinter()
        assert f.lookup("/path/to/file.mp3") is None

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_returns_none_when_no_api_key(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = ""
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        assert f.lookup("/path/to/file.mp3") is None

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_returns_artist_title_on_success(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        with patch("airwave.worker.fingerprint.acoustid.fingerprint_file") as m_fp:
            m_fp.return_value = (180.0, b"fpdata")
            with patch("airwave.worker.fingerprint.acoustid.lookup") as m_lookup:
                m_lookup.return_value = {
                    "results": [
                        {
                            "recordings": [
                                {
                                    "title": "Song Title",
                                    "artists": [{"name": "Artist Name"}],
                                }
                            ]
                        }
                    ]
                }
                result = f.lookup("/music/song.mp3")
        assert result == ("Artist Name", "Song Title")

    @patch("airwave.worker.fingerprint.settings")
    @patch.object(Path, "exists", return_value=True)
    def test_returns_none_when_no_results(self, mock_exists, mock_settings):
        mock_settings.ACOUSTID_API_KEY = "key"
        mock_settings.BASE_DIR = Path("/project")
        with patch.dict("os.environ", {}, clear=False):
            f = Fingerprinter()
        with patch("airwave.worker.fingerprint.acoustid.fingerprint_file") as m_fp:
            m_fp.return_value = (180.0, b"fpdata")
            with patch("airwave.worker.fingerprint.acoustid.lookup") as m_lookup:
                m_lookup.return_value = {"results": []}
                result = f.lookup("/music/song.mp3")
        assert result is None
