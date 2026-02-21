"""Tests for part number detection in work matching.

This test suite covers the part number detection functionality that prevents
different parts/movements of multi-part works from being incorrectly grouped together.

Key features tested:
- Part number extraction from various formats (Part, Movement, Number, Roman numerals)
- Roman numeral detection with special handling for "I" to avoid false positives
- Part comparison logic with asymmetric handling
- Integration with work matching to ensure parts are separated
"""

import pytest
from airwave.worker.scanner import FileScanner


class TestExtractPartNumber:
    """Test the _extract_part_number() static method."""

    def test_part_format_basic(self):
        """Test basic 'Part N' format detection."""
        assert FileScanner._extract_part_number("Symphony Part 1") == ("part", 1)
        assert FileScanner._extract_part_number("Symphony Part 2") == ("part", 2)
        assert FileScanner._extract_part_number("Concerto Part 10") == ("part", 10)

    def test_part_format_abbreviated(self):
        """Test abbreviated 'Pt. N' format detection."""
        assert FileScanner._extract_part_number("Symphony Pt. 1") == ("part", 1)
        assert FileScanner._extract_part_number("Symphony Pt 2") == ("part", 2)
        assert FileScanner._extract_part_number("Concerto Pt. 3") == ("part", 3)

    def test_movement_format_full(self):
        """Test 'Movement N' format detection."""
        assert FileScanner._extract_part_number("Symphony Movement 1") == ("movement", 1)
        assert FileScanner._extract_part_number("Concerto Movement 2") == ("movement", 2)
        assert FileScanner._extract_part_number("Sonata Movement 3") == ("movement", 3)

    def test_movement_format_abbreviated(self):
        """Test abbreviated movement formats."""
        assert FileScanner._extract_part_number("Symphony Mvt. 1") == ("movement", 1)
        assert FileScanner._extract_part_number("Symphony Mvt 2") == ("movement", 2)
        assert FileScanner._extract_part_number("Symphony Mov. 3") == ("movement", 3)
        assert FileScanner._extract_part_number("Symphony Mov 4") == ("movement", 4)

    def test_number_format(self):
        """Test 'No. N' and 'Number N' format detection."""
        assert FileScanner._extract_part_number("Opus No. 5") == ("number", 5)
        assert FileScanner._extract_part_number("Opus No 6") == ("number", 6)
        assert FileScanner._extract_part_number("Work Number 10") == ("number", 10)

    def test_roman_numerals_basic(self):
        """Test basic roman numeral detection (II-X)."""
        assert FileScanner._extract_part_number("Symphony II") == ("roman", 2)
        assert FileScanner._extract_part_number("Symphony III") == ("roman", 3)
        assert FileScanner._extract_part_number("Symphony IV") == ("roman", 4)
        assert FileScanner._extract_part_number("Symphony V") == ("roman", 5)
        assert FileScanner._extract_part_number("Symphony VI") == ("roman", 6)
        assert FileScanner._extract_part_number("Symphony VII") == ("roman", 7)
        assert FileScanner._extract_part_number("Symphony VIII") == ("roman", 8)
        assert FileScanner._extract_part_number("Symphony IX") == ("roman", 9)
        assert FileScanner._extract_part_number("Symphony X") == ("roman", 10)

    def test_roman_numeral_single_i_valid_cases(self):
        """Test that single 'I' is detected when NOT at the start (valid cases)."""
        # These should match - "I" is not at the beginning
        assert FileScanner._extract_part_number("Symphony I") == ("roman", 1)
        assert FileScanner._extract_part_number("Concerto I") == ("roman", 1)
        assert FileScanner._extract_part_number("Part I") == ("roman", 1)
        assert FileScanner._extract_part_number("Movement I") == ("roman", 1)
        assert FileScanner._extract_part_number("Opus I") == ("roman", 1)
        assert FileScanner._extract_part_number("The I") == ("roman", 1)  # "I" not at start

    def test_roman_numeral_single_i_invalid_cases(self):
        """Test that single 'I' is NOT detected when at the start (pronoun cases)."""
        # These should NOT match - "I" is at the beginning (likely pronoun)
        assert FileScanner._extract_part_number("I Love You") is None
        assert FileScanner._extract_part_number("I Want to Hold Your Hand") is None
        assert FileScanner._extract_part_number("I Will Always Love You") is None
        assert FileScanner._extract_part_number("I") is None  # Just "I" alone
        assert FileScanner._extract_part_number("I Am") is None

    def test_roman_numeral_single_i_edge_cases(self):
        """Test edge cases for single 'I' detection."""
        # "I" in the middle of a title (not at word boundary after first word)
        assert FileScanner._extract_part_number("When I Fall in Love") is None
        assert FileScanner._extract_part_number("If I Could Turn Back Time") is None
        
        # "I" at the end should match
        assert FileScanner._extract_part_number("Symphony I") == ("roman", 1)
        assert FileScanner._extract_part_number("Part I") == ("roman", 1)

    def test_case_insensitivity(self):
        """Test that detection is case-insensitive."""
        assert FileScanner._extract_part_number("SYMPHONY PART 1") == ("part", 1)
        assert FileScanner._extract_part_number("symphony part 1") == ("part", 1)
        assert FileScanner._extract_part_number("Symphony PART 1") == ("part", 1)
        assert FileScanner._extract_part_number("SYMPHONY II") == ("roman", 2)
        assert FileScanner._extract_part_number("symphony ii") == ("roman", 2)

    def test_no_part_number(self):
        """Test titles without part numbers return None."""
        assert FileScanner._extract_part_number("Regular Song Title") is None
        assert FileScanner._extract_part_number("Song Without Parts") is None
        assert FileScanner._extract_part_number("Just a Title") is None
        assert FileScanner._extract_part_number("The Beatles - Hey Jude") is None

    def test_part_number_with_extra_text(self):
        """Test part detection with additional text."""
        assert FileScanner._extract_part_number("Symphony Part 1 (Live)") == ("part", 1)
        assert FileScanner._extract_part_number("Concerto Movement 2 - Allegro") == ("movement", 2)
        assert FileScanner._extract_part_number("Sonata No. 5 in C Major") == ("number", 5)
        assert FileScanner._extract_part_number("Symphony II (Remastered)") == ("roman", 2)

    def test_multiple_numbers_first_match_wins(self):
        """Test that when multiple patterns exist, the first one wins."""
        # "Part" pattern comes before "Movement" in the code
        assert FileScanner._extract_part_number("Part 1 Movement 2") == ("part", 1)
        # "Movement" pattern comes before "No."
        assert FileScanner._extract_part_number("Movement 3 No. 4") == ("movement", 3)

    def test_word_boundaries(self):
        """Test that word boundaries are respected."""
        # "part" must be a complete word
        assert FileScanner._extract_part_number("Apartment 1") is None
        assert FileScanner._extract_part_number("Depart 2") is None
        # But "Part" as a word should match
        assert FileScanner._extract_part_number("Part 1") == ("part", 1)


class TestPartsDiffer:
    """Test the _parts_differ() instance method."""

    @pytest.fixture
    def scanner(self, db_session):
        """Create a FileScanner instance."""
        return FileScanner(db_session)

    def test_same_part_numbers(self, scanner):
        """Test that identical part numbers return False (same work)."""
        assert scanner._parts_differ("Symphony Part 1", "Symphony Part 1") is False
        assert scanner._parts_differ("Concerto Movement 2", "Concerto Movement 2") is False
        assert scanner._parts_differ("Sonata No. 5", "Sonata No. 5") is False
        assert scanner._parts_differ("Symphony II", "Symphony II") is False

    def test_different_part_numbers(self, scanner):
        """Test that different part numbers return True (different works)."""
        assert scanner._parts_differ("Symphony Part 1", "Symphony Part 2") is True
        assert scanner._parts_differ("Concerto Movement 1", "Concerto Movement 3") is True
        assert scanner._parts_differ("Sonata No. 5", "Sonata No. 6") is True
        assert scanner._parts_differ("Symphony I", "Symphony II") is True

    def test_asymmetric_one_has_part_other_doesnt(self, scanner):
        """Test asymmetric case: one title has part, other doesn't (different works)."""
        assert scanner._parts_differ("Symphony Part 1", "Symphony") is True
        assert scanner._parts_differ("Symphony", "Symphony Part 1") is True
        assert scanner._parts_differ("Concerto Movement 2", "Concerto") is True
        assert scanner._parts_differ("Concerto", "Concerto Movement 2") is True

    def test_neither_has_part_number(self, scanner):
        """Test that titles without part numbers can match (return False)."""
        assert scanner._parts_differ("Symphony", "Symphony") is False
        assert scanner._parts_differ("Song Title", "Song Title") is False
        assert scanner._parts_differ("Regular Song", "Regular Song") is False

    def test_same_part_different_format(self, scanner):
        """Test that same part with same format matches."""
        # Same format, same number
        assert scanner._parts_differ("Symphony Part 1", "Symphony Pt. 1") is False
        assert scanner._parts_differ("Concerto Movement 1", "Concerto Mvt. 1") is False

    def test_different_part_types_same_number(self, scanner):
        """Test that different part types are treated as different works."""
        # Part vs Movement - different types, should differ
        assert scanner._parts_differ("Symphony Part 1", "Symphony Movement 1") is True
        # Movement vs Number - different types, should differ
        assert scanner._parts_differ("Symphony Movement 1", "Symphony No. 1") is True
        # Part vs Roman - different types, should differ
        assert scanner._parts_differ("Symphony Part 1", "Symphony I") is True

    def test_roman_numeral_edge_cases(self, scanner):
        """Test roman numeral comparison edge cases."""
        # Same roman numeral
        assert scanner._parts_differ("Symphony I", "Symphony I") is False
        assert scanner._parts_differ("Symphony V", "Symphony V") is False
        # Different roman numerals
        assert scanner._parts_differ("Symphony I", "Symphony V") is True
        assert scanner._parts_differ("Symphony II", "Symphony III") is True

    def test_with_additional_text(self, scanner):
        """Test part comparison with additional text in titles."""
        # Same part, different additional text - should NOT differ
        assert scanner._parts_differ("Symphony Part 1 (Live)", "Symphony Part 1 (Studio)") is False
        # Different parts, same additional text - should differ
        assert scanner._parts_differ("Symphony Part 1 (Live)", "Symphony Part 2 (Live)") is True

    def test_case_insensitive_comparison(self, scanner):
        """Test that part comparison is case-insensitive."""
        assert scanner._parts_differ("SYMPHONY PART 1", "symphony part 1") is False
        assert scanner._parts_differ("Symphony II", "symphony ii") is False


class TestPartDetectionIntegration:
    """Integration tests for part detection in work matching."""

    @pytest.mark.asyncio
    async def test_different_parts_create_separate_works(self, db_session):
        """Test that different parts create separate works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create works with different parts
        work1 = await scanner._upsert_work("Symphony Part 1", artist.id)
        work2 = await scanner._upsert_work("Symphony Part 2", artist.id)
        await db_session.commit()

        # Should be different works
        assert work1.id != work2.id
        assert work1.title == "Symphony Part 1"
        assert work2.title == "Symphony Part 2"

    @pytest.mark.asyncio
    async def test_same_part_reuses_work(self, db_session):
        """Test that same part reuses existing work."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create work with part
        work1 = await scanner._upsert_work("Symphony Part 1", artist.id)
        work2 = await scanner._upsert_work("Symphony Part 1", artist.id)
        await db_session.commit()

        # Should be the same work
        assert work1.id == work2.id

    @pytest.mark.asyncio
    async def test_asymmetric_part_creates_separate_works(self, db_session):
        """Test that asymmetric part cases create separate works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create work without part
        work1 = await scanner._upsert_work("Symphony", artist.id)
        # Try to create work with part
        work2 = await scanner._upsert_work("Symphony Part 1", artist.id)
        await db_session.commit()

        # Should be different works
        assert work1.id != work2.id
        assert work1.title == "Symphony"
        assert work2.title == "Symphony Part 1"

    @pytest.mark.asyncio
    async def test_roman_numerals_create_separate_works(self, db_session):
        """Test that different roman numerals create separate works."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create works with roman numerals
        work1 = await scanner._upsert_work("Symphony I", artist.id)
        work2 = await scanner._upsert_work("Symphony II", artist.id)
        work3 = await scanner._upsert_work("Symphony III", artist.id)
        await db_session.commit()

        # Should all be different works
        assert work1.id != work2.id
        assert work2.id != work3.id
        assert work1.id != work3.id

    @pytest.mark.asyncio
    async def test_fuzzy_matching_respects_parts(self, db_session):
        """Test that fuzzy matching doesn't match different parts."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create work with Part 1
        work1 = await scanner._upsert_work("Symphony Part 1", artist.id)
        await db_session.commit()

        # Try to find similar work with Part 2 (should not match)
        similar = await scanner._find_similar_work("Symphony Part 2", artist.id)
        assert similar is None  # Should not find Part 1 when looking for Part 2

    @pytest.mark.asyncio
    async def test_fuzzy_matching_allows_same_parts(self, db_session):
        """Test that fuzzy matching works for same parts with minor differences."""
        scanner = FileScanner(db_session)
        artist = await scanner._upsert_artist("Test Artist")

        # Create work with Part 1
        work1 = await scanner._upsert_work("Symphony Part 1", artist.id)
        await db_session.commit()

        # Try to find similar work with Part 1 (extra space)
        similar = await scanner._find_similar_work("Symphony Part 1 ", artist.id)
        assert similar is not None
        assert similar.id == work1.id  # Should match (same part, fuzzy match)

