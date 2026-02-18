"""Tests for the normalization module."""

from airwave.core.normalization import Normalizer


def test_clean_artist_removes_year_and_truncation():
    """AC2: clean_artist() removes year brackets and truncation markers."""
    assert Normalizer.clean_artist("Band (2019)") == "band"
    assert Normalizer.clean_artist("Artist Name [...]") == "artist name"
    assert Normalizer.clean_artist("The Band (2020)") == "band"


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


def test_remove_year_brackets():
    """Test year bracket removal helper."""
    assert Normalizer.remove_year_brackets("Song Title (2018)") == "Song Title"
    assert Normalizer.remove_year_brackets("Song [1999]") == "Song"
    assert Normalizer.remove_year_brackets("Song (2023 Remaster)") == "Song"
    assert Normalizer.remove_year_brackets("Song [1999 Remaster]") == "Song"
    assert Normalizer.remove_year_brackets("Song (Live)") == "Song (Live)"
    assert Normalizer.remove_year_brackets("") == ""


def test_remove_truncation_markers():
    """Test truncation marker removal helper."""
    assert Normalizer.remove_truncation_markers("Long Song Title (...)") == "Long Song Title"
    assert Normalizer.remove_truncation_markers("Artist Name [...]") == "Artist Name"
    assert Normalizer.remove_truncation_markers("Song\u2026") == "Song"
    assert Normalizer.remove_truncation_markers("Song...") == "Song"
    assert Normalizer.remove_truncation_markers("Song Title") == "Song Title"
    assert Normalizer.remove_truncation_markers("") == ""


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


# --- Task 5: Comprehensive tests for enhanced normalization ---


def test_clean_removes_year_brackets():
    """Test that clean() removes year brackets from titles."""
    assert Normalizer.clean("Song Title (2018)") == "song title"
    assert Normalizer.clean("Song [1999 Remaster]") == "song"
    assert Normalizer.clean("Song (2023 Deluxe)") == "song"


def test_clean_removes_truncation_markers():
    """Test that clean() removes truncation markers."""
    assert Normalizer.clean("Long Song Title (...)") == "long song title"
    assert Normalizer.clean("Artist Name [...]") == "artist name"
    assert Normalizer.clean("Song\u2026") == "song"


def test_clean_normalizes_smart_quotes():
    """Test that clean() normalizes smart quotes before punctuation removal."""
    # Straight apostrophe: "Song's" -> "songs"
    assert Normalizer.clean("Song's Title") == "songs title"
    # Smart double quotes (U+201C, U+201D)
    assert Normalizer.clean("Artist \u201cName\u201d Here") == "artist name here"


def test_clean_removes_feat_suffix():
    """Test that clean() removes feat. suffix and everything after."""
    assert Normalizer.clean("Song Title feat. Artist B") == "song title"
    assert Normalizer.clean("Song ft. Someone") == "song"
    assert Normalizer.clean("Song featuring Artist") == "song"
    assert Normalizer.clean("Song with Guest") == "song"
    assert Normalizer.clean("Song FEAT. Artist") == "song"
    assert Normalizer.clean("Song Title") == "song title"
    # No space after ft. (optional space in regex)
    assert Normalizer.clean("Song ft.Someone") == "song"


def test_extract_version_type_enhanced():
    """Test enhanced VERSION_REGEX for Deluxe, Bonus, year, part numbers."""
    assert Normalizer.extract_version_type("Song (Deluxe Edition)") == ("Song", "Deluxe")
    assert Normalizer.extract_version_type("Song [Bonus Track]") == ("Song", "Bonus")
    assert Normalizer.extract_version_type("Song (2018)") == ("Song", "2018")
    assert Normalizer.extract_version_type("Song (Pt. 1)") == ("Song", "Pt. 1")
    assert Normalizer.extract_version_type("Song [Part 2]") == ("Song", "Part 2")
    # Backward compatibility
    assert Normalizer.extract_version_type("Song Title (Live)") == ("Song Title", "Live")
    assert Normalizer.extract_version_type("Song Title [Remix]") == ("Song Title", "Remix")


# --- Tests for extract_version_type_enhanced() ---


def test_extract_version_type_enhanced_multiple_tags():
    """Test extraction of multiple version tags."""
    clean, version = Normalizer.extract_version_type_enhanced("Song (Live) (Radio Edit)")
    assert clean == "Song"
    assert "Live" in version
    assert "Radio" in version or "Edit" in version


def test_extract_version_type_enhanced_dash_separated():
    """Test extraction of dash-separated versions."""
    assert Normalizer.extract_version_type_enhanced("Song - Live Version") == ("Song", "Live")
    assert Normalizer.extract_version_type_enhanced("Song - Radio Edit") == ("Song", "Radio")
    assert Normalizer.extract_version_type_enhanced("Song - Acoustic Mix") == ("Song", "Acoustic")


def test_extract_version_type_enhanced_part_numbers_not_extracted():
    """Test that part numbers are NOT extracted as versions (negative pattern)."""
    # Part numbers should remain in title
    clean, version = Normalizer.extract_version_type_enhanced("Song (Part 1)")
    assert "Part 1" in clean or "part 1" in clean.lower()
    assert version == "Original"

    clean, version = Normalizer.extract_version_type_enhanced("Symphony (Pt. 2)")
    assert "Pt. 2" in clean or "pt. 2" in clean.lower()
    assert version == "Original"


def test_extract_version_type_enhanced_subtitles_not_extracted():
    """Test that subtitles starting with 'The' are NOT extracted (negative pattern)."""
    # Subtitles should remain in title
    clean, version = Normalizer.extract_version_type_enhanced("Song (The Ballad)")
    assert "The Ballad" in clean or "the ballad" in clean.lower()
    assert version == "Original"

    clean, version = Normalizer.extract_version_type_enhanced("Song (The Final Chapter)")
    assert "The Final Chapter" in clean or "the final chapter" in clean.lower()
    assert version == "Original"


def test_extract_version_type_enhanced_album_context():
    """Test album context for live detection."""
    # With live album context
    clean, version = Normalizer.extract_version_type_enhanced(
        "Song Title", album_title="Live at Wembley"
    )
    assert clean == "Song Title"
    assert version == "Live"

    # Album context only used if no version already extracted
    clean, version = Normalizer.extract_version_type_enhanced(
        "Song (Remix)", album_title="Live at Wembley"
    )
    assert clean == "Song"
    assert version == "Remix"  # Should NOT add "Live"


def test_extract_version_type_enhanced_ambiguous_parentheses():
    """Test handling of ambiguous parentheses with version keywords."""
    # Short phrases with version keywords should be extracted
    clean, version = Normalizer.extract_version_type_enhanced("Song (Radio Edit)")
    assert clean == "Song"
    assert "Radio" in version or "Edit" in version

    # Longer phrases without version keywords should remain
    clean, version = Normalizer.extract_version_type_enhanced("Song (From the Album)")
    assert "From the Album" in clean or "from the album" in clean.lower()
    assert version == "Original"


def test_extract_version_type_enhanced_deduplication():
    """Test that duplicate version tags are deduplicated."""
    clean, version = Normalizer.extract_version_type_enhanced("Song (Live) - Live Version")
    assert clean == "Song"
    # Should only have "Live" once
    assert version.lower().count("live") == 1


def test_extract_version_type_enhanced_backward_compatibility():
    """Test backward compatibility with original extract_version_type()."""
    # Basic cases should work the same
    assert Normalizer.extract_version_type_enhanced("Song (Live)") == ("Song", "Live")
    assert Normalizer.extract_version_type_enhanced("Song [Remix]") == ("Song", "Remix")
    assert Normalizer.extract_version_type_enhanced("Song Title") == ("Song Title", "Original")
    assert Normalizer.extract_version_type_enhanced("") == ("", "Original")
