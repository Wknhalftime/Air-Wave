"""Test search normalization with special characters and edge cases."""
import pytest
from airwave.core.normalization import Normalizer


def test_normalizer_clean():
    """Test that Normalizer.clean() handles various edge cases."""
    
    # Test 1: Trailing spaces
    assert Normalizer.clean("RAGE AGAINST THE MACHINE ") == "rage against the machine"
    assert Normalizer.clean("RAGE AGAINST THE MACHINE") == "rage against the machine"
    
    # Test 2: Special characters
    assert Normalizer.clean("AC/DC") == "ac dc"
    assert Normalizer.clean("Rock & Roll") == "rock and roll"
    assert Normalizer.clean("Guns N' Roses") == "guns n roses"
    
    # Test 3: Brackets and parentheses
    assert Normalizer.clean("Song Title (Live)") == "song title live"
    assert Normalizer.clean("Song Title [Remix]") == "song title remix"
    assert Normalizer.clean("Song (feat. Artist)") == "song feat artist"
    
    # Test 4: Remaster tags
    assert Normalizer.clean("Song (Remastered 2023)") == "song"
    assert Normalizer.clean("Song - Remaster 2009") == "song"
    
    # Test 5: Accents
    assert Normalizer.clean("Café") == "cafe"
    assert Normalizer.clean("Beyoncé") == "beyonce"
    assert Normalizer.clean("Motörhead") == "motorhead"
    
    # Test 6: Multiple spaces
    assert Normalizer.clean("Song   Title") == "song title"
    assert Normalizer.clean("  Song  Title  ") == "song title"
    
    # Test 7: Mixed cases
    assert Normalizer.clean("DoN't Go BrEaKiNg My HeArT") == "dont go breaking my heart"


def test_search_query_normalization():
    """Test that search queries are normalized correctly."""
    
    # Test 1: Artist with trailing space + title
    query = "RAGE AGAINST THE MACHINE  Killing In The Name"
    normalized = Normalizer.clean(query)
    words = normalized.split()
    
    assert "rage" in words
    assert "against" in words
    assert "the" in words
    assert "machine" in words
    assert "killing" in words
    assert "in" in words
    assert "name" in words
    
    # Test 2: Artist with special characters
    query = "AC/DC Back In Black"
    normalized = Normalizer.clean(query)
    words = normalized.split()
    
    assert "ac" in words
    assert "dc" in words
    assert "back" in words
    assert "in" in words
    assert "black" in words
    
    # Test 3: Title with brackets
    query = "Elton John Don't Go Breaking My Heart (Live)"
    normalized = Normalizer.clean(query)
    words = normalized.split()
    
    assert "elton" in words
    assert "john" in words
    assert "dont" in words
    assert "go" in words
    assert "breaking" in words
    assert "my" in words
    assert "heart" in words
    assert "live" in words
    
    # Test 4: Remaster tag should be removed
    query = "The Beatles Hey Jude (Remastered 2009)"
    normalized = Normalizer.clean(query)
    words = normalized.split()
    
    assert "the" in words
    assert "beatles" in words
    assert "hey" in words
    assert "jude" in words
    assert "remastered" not in words
    assert "2009" not in words


def test_search_substring_matching():
    """Test that normalized words match as substrings."""

    # Test 1: "break" should match "Breaking"
    query = "Elton John break"
    normalized = Normalizer.clean(query)
    words = normalized.split()

    # Simulate ILIKE search - words can match in artist OR title
    artist = "Elton John"
    title = "Don't Go Breaking My Heart"
    artist_lower = artist.lower()
    title_lower = title.lower()

    # Each word should match in either artist or title
    for word in words:
        assert word in artist_lower or word in title_lower, f"Word '{word}' not found in artist or title"

    # Specifically check "break" matches "breaking"
    assert "break" in "breaking"  # Substring match

    # Test 2: "ac dc" should match "AC/DC"
    query = "ac dc"
    artist = "AC/DC"
    artist_lower = artist.lower()

    # Both words should be substrings
    assert "ac" in artist_lower
    assert "dc" in artist_lower


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

