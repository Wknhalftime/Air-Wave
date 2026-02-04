"""Tests for the normalization module."""

from airwave.core.normalization import Normalizer


def test_clean_artist_cases():
    """Test clean_artist against known edge cases."""
    cases = [
        ("zhané", "zhane"),
        ("zhane", "zhane"),
        ("yo‐yo", "yoyo"),  # contains \u2010 (hyphen)
        ("yoyo", "yoyo"),
        ("Beyoncé", "beyonce"),
        ("10,000 Maniacs", "10000 maniacs"),
        ("The Beatles", "beatles"),
        ("A Tribe Called Quest", "tribe called quest"),
        ("AC/DC", "ac dc"),
        ("Simon & Garfunkel", "simon and garfunkel"),
        ("The Offspring", "offspring"),
        ("A Perfect Circle", "perfect circle"),
        ("Panic! At The Disco", "panic at the disco"),
        ("R.E.M.", "rem"),
        ("Jay-Z", "jayz"),
        ("Florence + The Machine", "florence and the machine"),
    ]

    for input_str, expected in cases:
        assert Normalizer.clean_artist(input_str) == expected


def test_clean_basic():
    """Test basic text cleaning."""
    assert Normalizer.clean("  Hello   World  ") == "hello world"
    assert Normalizer.clean("Café") == "cafe"
    assert Normalizer.clean("Live at Wembley") == "live at wembley"
    assert Normalizer.clean("Song Title (Remastered)") == "song title"
    # Basic clean preserves "the", unlike clean_artist
    assert Normalizer.clean("The End") == "the end"
    assert Normalizer.clean("A Hard Day's Night") == "a hard days night"


def test_extract_version_type():
    """Test version extraction."""
    # Logic: extract_version_type returns (clean_title, version_type)
    # Note: It strips the version tag from title.
    
    assert Normalizer.extract_version_type("Song Title (Live)") == ("Song Title", "Live")
    assert Normalizer.extract_version_type("Song Title [Remix]") == ("Song Title", "Remix")
    assert Normalizer.extract_version_type("Song Title") == ("Song Title", "Original")


def test_split_artists():
    """Test artist splitting logic."""
    assert Normalizer.split_artists("Artist A & Artist B") == ["artist a", "artist b"]
    assert Normalizer.split_artists("Artist A feat. Artist B") == ["artist a", "artist b"]
    assert Normalizer.split_artists("Artist A / Artist B") == ["artist a", "artist b"]
