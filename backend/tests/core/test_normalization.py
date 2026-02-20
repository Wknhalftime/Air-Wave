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
        ("Florence + The Machine", "florence plus the machine"),
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


def test_split_artists_preserves_numeric_commas():
    """Commas in numbers (e.g. 10,000) must NOT split - they are thousands separators."""
    # 10,000 Maniacs should remain a single artist
    assert Normalizer.split_artists("10,000 Maniacs") == ["10000 maniacs"]
    assert Normalizer.split_artists("1,000 Clowns") == ["1000 clowns"]
    # Regular comma separators should still split
    assert Normalizer.split_artists("Artist A, Artist B") == ["artist a", "artist b"]


def test_split_artists_removes_duet_and_vs():
    """Collaboration keywords (duet, vs) must be used as separators and removed from results."""
    # "2pac duet" with nothing after -> single artist "2pac"
    assert Normalizer.split_artists("2pac duet") == ["2pac"]
    assert Normalizer.split_artists("2Pac Duet") == ["2pac"]
    # "Artist A duet Artist B" -> split and remove keyword
    assert Normalizer.split_artists("2pac duet Dr. Dre") == ["2pac", "dr dre"]
    # "Artist A vs Artist B"
    assert Normalizer.split_artists("Artist A vs Artist B") == ["artist a", "artist b"]
    assert Normalizer.split_artists("Artist A vs. Artist B") == ["artist a", "artist b"]


def test_clean_artist_removes_collaboration_keywords():
    """clean_artist must strip trailing collaboration keywords (duet, feat., vs, etc.)."""
    assert Normalizer.clean_artist("2pac duet") == "2pac"
    assert Normalizer.clean_artist("2Pac Duet") == "2pac"
    assert Normalizer.clean_artist("Artist feat. Someone") == "artist"
    assert Normalizer.clean_artist("Artist ft. X") == "artist"
    assert Normalizer.clean_artist("Artist vs Other") == "artist"
    # Word boundaries: "Feature" in band names should NOT be removed
    assert Normalizer.clean_artist("Feature Artist") == "feature artist"
    # "Little Feat" is a band name - feat without period must NOT be stripped
    assert Normalizer.clean_artist("Little Feat") == "little feat"


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
    assert Normalizer.clean("Song FEAT. Artist") == "song"
    assert Normalizer.clean("Song Title") == "song title"
    # No space after ft. (optional space in regex)
    assert Normalizer.clean("Song ft.Someone") == "song"


def test_clean_preserves_titles_with_common_words():
    """Test that clean() does NOT remove common words that appear in legitimate titles.

    Regression test for bug where 'with', 'f', etc. were being removed from titles.
    These words appear in many legitimate song titles and should be preserved.

    Bug examples:
    - "All Within My Hands" was truncated to "all" (matched "with" in "within")
    - "Fight Fire with Fire" was truncated to "fight" (matched "f" in "fire")
    - "The Four Horsemen" was truncated to "the" (matched "f" in "four")
    """
    # Test cases from the bug report
    assert Normalizer.clean("All Within My Hands") == "all within my hands"
    assert Normalizer.clean("Fight Fire with Fire") == "fight fire with fire"
    assert Normalizer.clean("The Four Horsemen") == "the four horsemen"
    assert Normalizer.clean("The Frayed Ends of Sanity") == "the frayed ends of sanity"

    # Other common titles with "with"
    assert Normalizer.clean("With or Without You") == "with or without you"
    assert Normalizer.clean("Dancing with Myself") == "dancing with myself"
    assert Normalizer.clean("Killing Me Softly with His Song") == "killing me softly with his song"

    # Titles starting with "f" should not be truncated
    assert Normalizer.clean("Fire and Rain") == "fire and rain"
    assert Normalizer.clean("Forever Young") == "forever young"
    assert Normalizer.clean("Fortunate Son") == "fortunate son"


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


def test_extract_version_type_enhanced_delimiter_based_extraction():
    """Test extraction of mix/remix descriptors within parentheses/brackets.

    Strategy 1.5 prioritizes delimiter-based extraction, which is more accurate
    than embedded pattern matching for multi-word titles.
    """
    # Parentheses with "the X mix" patterns
    clean, version = Normalizer.extract_version_type_enhanced("larger than life (the video mix)")
    assert clean == "larger than life"
    assert version == "Video"

    clean, version = Normalizer.extract_version_type_enhanced("all i have to give (the conversation mix)")
    assert clean == "all i have to give"
    assert version == "Remix"

    # Square brackets
    clean, version = Normalizer.extract_version_type_enhanced("larger than life [the video mix]")
    assert clean == "larger than life"
    assert version == "Video"

    # Named remixes in parentheses
    clean, version = Normalizer.extract_version_type_enhanced("all i have to give (davidson ospina radio mix)")
    assert clean == "all i have to give"
    assert version == "Radio"

    # Simple mix types in parentheses
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall (radio mix)")
    assert clean == "wonderwall"
    assert version == "Radio"

    clean, version = Normalizer.extract_version_type_enhanced("wonderwall (club mix)")
    assert clean == "wonderwall"
    assert version == "Remix"

    # Edit patterns in parentheses
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall (radio edit)")
    assert clean == "wonderwall"
    assert version == "Radio"


def test_extract_version_type_enhanced_embedded_remix_patterns():
    """Test extraction of embedded remix/mix descriptors without delimiters.

    Note: These patterns work best with single-word titles. For multi-word titles,
    delimiter-based extraction (parentheses/brackets) is more accurate.
    """
    # Simple mix types at end (single word titles work best)
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall radio mix")
    assert clean == "wonderwall"
    assert version == "Radio"

    clean, version = Normalizer.extract_version_type_enhanced("wonderwall video mix")
    assert clean == "wonderwall"
    assert version == "Video"

    clean, version = Normalizer.extract_version_type_enhanced("wonderwall club mix")
    assert clean == "wonderwall"
    assert version == "Remix"

    # Edit patterns
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall radio edit")
    assert clean == "wonderwall"
    assert version == "Radio"

    # Version patterns
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall radio version")
    assert clean == "wonderwall"
    assert version == "Radio"

    # Other mix types
    clean, version = Normalizer.extract_version_type_enhanced("wonderwall instrumental mix")
    assert clean == "wonderwall"
    assert version == "Instrumental"

    clean, version = Normalizer.extract_version_type_enhanced("wonderwall acoustic mix")
    assert clean == "wonderwall"
    assert version == "Acoustic"

    clean, version = Normalizer.extract_version_type_enhanced("wonderwall extended mix")
    assert clean == "wonderwall"
    assert version == "Extended"

    # Named remixes with capitalized names (e.g., "Davidson Ospina Radio Mix")
    # Note: These require capitalization to distinguish from common words
    clean, version = Normalizer.extract_version_type_enhanced("Song Davidson Ospina Radio Mix")
    assert clean == "Song"
    assert version == "Radio"

    clean, version = Normalizer.extract_version_type_enhanced("Song Tiesto Club Mix")
    assert clean == "Song"
    assert version == "Remix"


def test_extract_version_type_enhanced_embedded_patterns_not_in_middle():
    """Test that embedded patterns only match at the end of the title."""
    # Pattern in middle should NOT be extracted
    clean, version = Normalizer.extract_version_type_enhanced("radio mix song")
    assert clean == "radio mix song"
    assert version == "Original"

    # Pattern at end should be extracted
    clean, version = Normalizer.extract_version_type_enhanced("song radio mix")
    assert clean == "song"
    assert version == "Radio"
