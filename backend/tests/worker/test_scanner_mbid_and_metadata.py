"""Unit tests for scanner MBID parsing, tag extraction, and LibraryMetadata.

This test suite covers:
- _parse_mbid_list(): Parse MusicBrainz IDs from raw tag values
- _extract_mbid_from_tags(): Extract MBIDs from Vorbis/FLAC and ID3 tags
- LibraryMetadata: Metadata container with normalization and version parsing
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from airwave.worker.scanner import (
    LibraryMetadata,
    _extract_mbid_from_tags,
    _parse_mbid_list,
)


# Valid UUID for MusicBrainz (8-4-4-4-12 hex)
VALID_MBID = "a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432"


class TestParseMbidList:
    """Test _parse_mbid_list() - parse raw MBID tag value to list of valid UUIDs."""

    def test_empty_or_none_returns_empty(self):
        """Empty and None inputs return empty list."""
        assert _parse_mbid_list(None) == []
        assert _parse_mbid_list("") == []
        assert _parse_mbid_list("   ") == []

    def test_single_valid_uuid(self):
        """Single valid UUID is returned."""
        assert _parse_mbid_list(VALID_MBID) == [VALID_MBID]

    def test_comma_separated_valid_uuids(self):
        """Comma-separated valid UUIDs are all returned."""
        mbid2 = "b4dc34gd-bde4-5df1-9g47-2f6bb7b29543".replace("g", "0")
        raw = f"{VALID_MBID}, {mbid2}"
        result = _parse_mbid_list(raw)
        assert len(result) == 2
        assert VALID_MBID in result
        assert mbid2 in result

    def test_invalid_uuids_filtered_out(self):
        """Invalid UUIDs are filtered out, valid ones kept."""
        mbid2 = "b4dc34fd-bde4-5df1-9f47-2f6bb7b29543"
        raw = f"{VALID_MBID}, not-a-uuid, {mbid2}, xyz, 12345"
        result = _parse_mbid_list(raw)
        assert result == [VALID_MBID, mbid2]

    def test_uppercase_hex_accepted(self):
        """Uppercase hex in UUID is accepted (MusicBrainz may use uppercase)."""
        upper = "A3CB23FC-ACD3-4CE0-8F36-1E5AA6A18432"
        assert _parse_mbid_list(upper) == [upper]

    def test_whitespace_stripped(self):
        """Whitespace around each UUID is stripped."""
        raw = f"  {VALID_MBID}  ,  {VALID_MBID}  "
        result = _parse_mbid_list(raw)
        assert result == [VALID_MBID, VALID_MBID]

    def test_malformed_uuid_rejected(self):
        """Malformed UUIDs (wrong length, wrong segments) are rejected."""
        assert _parse_mbid_list("12345678-1234-1234-1234-123456789012") != []
        assert _parse_mbid_list("12345678-1234-1234-1234") == []
        assert _parse_mbid_list("gggggggg-gggg-gggg-gggg-gggggggggggg") == []
        assert _parse_mbid_list("12345678-1234-1234-1234-12345678901") == []


class TestExtractMbidFromTags:
    """Test _extract_mbid_from_tags() - extract MBIDs from Mutagen tag objects."""

    def test_none_tags_returns_none_tuple(self):
        """None tags return (None, None)."""
        assert _extract_mbid_from_tags(None) == (None, None)

    def test_vorbis_flac_artist_and_album_artist(self):
        """Vorbis/FLAC tags: MUSICBRAINZ_ARTISTID and MUSICBRAINZ_ALBUMARTISTID."""
        tags = {
            "MUSICBRAINZ_ARTISTID": [VALID_MBID],
            "MUSICBRAINZ_ALBUMARTISTID": ["b4dc34fd-bde4-5df1-9f47-2f6bb7b29543"],
        }
        mock = MagicMock()
        mock.get.side_effect = lambda k, d=None: tags.get(k, d)
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw == VALID_MBID
        assert album_raw == "b4dc34fd-bde4-5df1-9f47-2f6bb7b29543"

    def test_vorbis_empty_values_return_none(self):
        """Vorbis tags with empty values return None."""
        tags = {
            "MUSICBRAINZ_ARTISTID": [""],
            "MUSICBRAINZ_ALBUMARTISTID": [""],
        }
        mock = MagicMock()
        mock.get.side_effect = lambda k, d=None: tags.get(k, d)
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw is None
        assert album_raw is None

    def test_vorbis_missing_keys_default_empty(self):
        """Vorbis tags with missing keys use default empty."""
        mock = MagicMock()
        mock.get.return_value = [""]
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw is None
        assert album_raw is None

    def test_id3_txxx_musicbrainz_artist_id(self):
        """ID3 TXXX frames: MusicBrainz Artist Id and Album Artist Id."""
        frame_artist = MagicMock(desc="MusicBrainz Artist Id", text=[VALID_MBID])
        frame_album = MagicMock(
            desc="MusicBrainz Album Artist Id",
            text=["b4dc34fd-bde4-5df1-9f47-2f6bb7b29543"],
        )
        mock = MagicMock()
        mock.get = MagicMock(return_value=None)
        mock.getall = MagicMock(return_value=[frame_artist, frame_album])
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw == VALID_MBID
        assert album_raw == "b4dc34fd-bde4-5df1-9f47-2f6bb7b29543"

    def test_id3_txxx_overrides_vorbis_if_present(self):
        """ID3 TXXX can override Vorbis values (TXXX processed after Vorbis)."""
        tags = {"MUSICBRAINZ_ARTISTID": ["vorbis-mbid"], "MUSICBRAINZ_ALBUMARTISTID": [""]}
        frame = MagicMock(desc="MusicBrainz Artist Id", text=[VALID_MBID])
        mock = MagicMock()
        mock.get.side_effect = lambda k, d=None: tags.get(k, d)
        mock.getall = MagicMock(return_value=[frame])
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw == VALID_MBID  # TXXX overrides
        assert album_raw is None

    def test_id3_txxx_empty_text_skipped(self):
        """ID3 TXXX frames with empty text are skipped."""
        frame = MagicMock(desc="MusicBrainz Artist Id", text=[""])
        mock = MagicMock()
        mock.get = MagicMock(return_value=None)
        mock.getall = MagicMock(return_value=[frame])
        artist_raw, album_raw = _extract_mbid_from_tags(mock)
        assert artist_raw is None
        assert album_raw is None


class TestLibraryMetadata:
    """Test LibraryMetadata - sanitized metadata container with normalization."""

    def test_basic_initialization(self):
        """Basic artist and title are normalized."""
        meta = LibraryMetadata("The Beatles", "Hey Jude")
        assert meta.raw_artist == "The Beatles"
        assert meta.raw_title == "Hey Jude"
        assert meta.artist == "beatles"
        assert meta.title == "hey jude"
        assert meta.version_type == "Original"
        assert meta.work_title == meta.title
        assert meta.album_artist == meta.artist
        assert meta.album_title is None
        assert meta.duration is None
        assert meta.isrc is None
        assert meta.release_date is None
        assert meta.artist_mbids == []
        assert meta.album_artist_mbids == []

    def test_version_parsing_live(self):
        """Version type (Live) is extracted from title."""
        meta = LibraryMetadata("Artist", "Song (Live)")
        assert meta.version_type == "Live"
        assert meta.title == "song"
        assert meta.work_title == "song"

    def test_version_parsing_remix(self):
        """Version type (Remix) is extracted from title."""
        meta = LibraryMetadata("Artist", "Song [Remix]")
        assert meta.version_type == "Remix"
        assert meta.title == "song"

    def test_album_artist_defaults_to_artist(self):
        """Album artist defaults to track artist when not provided."""
        meta = LibraryMetadata("Artist A", "Title")
        assert meta.album_artist == meta.artist == "artist a"

    def test_album_artist_explicit(self):
        """Explicit album artist is used when provided."""
        meta = LibraryMetadata(
            "Artist A", "Title", album_artist="Various Artists", album_title="Compilation"
        )
        assert meta.album_artist == "various artists"
        assert meta.album_title == "compilation"

    def test_optional_fields(self):
        """Duration, ISRC, release_date, and MBIDs are stored."""
        release = datetime(2023, 5, 15)
        mbids = ["a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432"]
        meta = LibraryMetadata(
            "Artist",
            "Title",
            duration=180.5,
            isrc="USRC12345678",
            release_date=release,
            artist_mbids=mbids,
            album_artist_mbids=mbids,
        )
        assert meta.duration == 180.5
        assert meta.isrc == "USRC12345678"
        assert meta.release_date == release
        assert meta.artist_mbids == mbids
        assert meta.album_artist_mbids == mbids

    def test_empty_artist_defaults_to_unknown(self):
        """Empty or None artist becomes 'Unknown Artist'."""
        meta = LibraryMetadata("", "Title")
        assert meta.artist == "unknown artist"

    def test_empty_title_defaults_to_untitled(self):
        """Empty or None title becomes 'Untitled' after version extraction."""
        meta = LibraryMetadata("Artist", "")
        assert meta.title == "untitled"

    def test_mbids_default_to_empty_list(self):
        """None MBIDs become empty lists."""
        meta = LibraryMetadata("Artist", "Title", artist_mbids=None, album_artist_mbids=None)
        assert meta.artist_mbids == []
        assert meta.album_artist_mbids == []

    def test_artist_normalization(self):
        """Artist names are normalized (The prefix, accents, etc.)."""
        meta = LibraryMetadata("The Offspring", "Song")
        assert meta.artist == "offspring"

        meta2 = LibraryMetadata("Beyoncé", "Song")
        assert meta2.artist == "beyonce"
