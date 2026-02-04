"""Comprehensive tests for the VectorDB module.

This test suite covers:
- Singleton pattern verification
- Single track indexing
- Batch track indexing
- Single search
- Batch search with chunking
- Distance threshold behavior
- Persistence across instances
- Empty query handling
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from airwave.core.vector_db import VectorDB


class TestVectorDBSingleton:
    """Test VectorDB singleton pattern."""

    def test_singleton_pattern(self):
        """Test that VectorDB returns the same instance."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb1 = VectorDB(persist_path=temp_dir)
            vdb2 = VectorDB(persist_path=temp_dir)

            # Should be the same instance
            assert vdb1 is vdb2
            assert id(vdb1) == id(vdb2)
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_singleton_prevents_reinitialization(self):
        """Test that singleton prevents re-initialization."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            original_client = vdb.client

            # Try to initialize again
            vdb2 = VectorDB(persist_path="/different/path")

            # Should still have the same client
            assert vdb2.client is original_client
            assert vdb2.persist_path == temp_dir  # Original path preserved
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorDBIndexing:
    """Test track indexing operations."""

    def test_add_single_track(self):
        """Test adding a single track to the index."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(1, "the beatles", "hey jude")

            # Verify track was added
            count = vdb.collection.count()
            assert count == 1

            # Verify we can retrieve it
            result = vdb.collection.get(ids=["1"])
            assert len(result["ids"]) == 1
            assert result["metadatas"][0]["artist"] == "the beatles"
            assert result["metadatas"][0]["title"] == "hey jude"
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_tracks_batch(self):
        """Test adding multiple tracks in batch."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            tracks = [
                (1, "the beatles", "hey jude"),
                (2, "queen", "bohemian rhapsody"),
                (3, "led zeppelin", "stairway to heaven"),
                (4, "pink floyd", "comfortably numb"),
                (5, "the rolling stones", "paint it black"),
            ]

            vdb.add_tracks(tracks)

            # Verify all tracks were added
            count = vdb.collection.count()
            assert count == 5
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_tracks_empty_list(self):
        """Test that adding empty list is a no-op."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_tracks([])

            # Should not crash and count should be 0
            count = vdb.collection.count()
            assert count == 0
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_tracks_upsert_behavior(self):
        """Test that adding same track ID updates the entry."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            # Add track
            vdb.add_track(1, "nirvana", "smells like teen spirit")
            assert vdb.collection.count() == 1

            # Update same track ID with different data
            vdb.add_track(1, "nirvana", "lithium")

            # Should still have only 1 track (upsert)
            assert vdb.collection.count() == 1

            # Verify it was updated
            result = vdb.collection.get(ids=["1"])
            assert result["metadatas"][0]["title"] == "lithium"
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorDBSearch:
    """Test search operations."""

    def test_search_single_exact_match(self):
        """Test searching for an exact match."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(1, "radiohead", "creep")

            # Search for exact match
            matches = vdb.search("radiohead", "creep", limit=1)

            assert len(matches) == 1
            track_id, distance = matches[0]
            assert track_id == 1
            assert distance < 0.01  # Should be very close to 0 for exact match
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_fuzzy_match(self):
        """Test searching with slight variations."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(1, "guns n roses", "sweet child o mine")

            # Search with variations
            matches = vdb.search("gnr", "sweet child", limit=1)

            assert len(matches) == 1
            track_id, distance = matches[0]
            assert track_id == 1
            assert distance < 0.5  # Should still be reasonably close
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_returns_top_n(self):
        """Test that search returns correct number of results."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            # Add multiple tracks
            tracks = [
                (1, "metallica", "enter sandman"),
                (2, "metallica", "nothing else matters"),
                (3, "metallica", "master of puppets"),
            ]
            vdb.add_tracks(tracks)

            # Search for metallica songs
            matches = vdb.search("metallica", "sandman", limit=3)

            assert len(matches) <= 3
            assert len(matches) > 0
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_no_matches(self):
        """Test search when no tracks are indexed."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            # Search empty index
            matches = vdb.search("nonexistent", "track", limit=1)

            assert matches == []
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorDBBatchSearch:
    """Test batch search operations."""

    def test_search_batch_multiple_queries(self):
        """Test batch searching with multiple queries."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            # Add tracks
            tracks = [
                (1, "the beatles", "hey jude"),
                (2, "queen", "bohemian rhapsody"),
                (3, "led zeppelin", "stairway to heaven"),
            ]
            vdb.add_tracks(tracks)

            # Batch search
            queries = [
                ("the beatles", "hey jude"),
                ("queen", "bohemian rhapsody"),
            ]
            results = vdb.search_batch(queries, limit=1)

            assert len(results) == 2
            assert len(results[0]) == 1  # First query results
            assert len(results[1]) == 1  # Second query results
            assert results[0][0][0] == 1  # Beatles track
            assert results[1][0][0] == 2  # Queen track
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_batch_empty_queries(self):
        """Test batch search with empty query list."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            results = vdb.search_batch([], limit=1)

            assert results == []
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_batch_chunking(self):
        """Test that batch search handles large query sets with chunking."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)

            # Add a track
            vdb.add_track(1, "test artist", "test song")

            # Create 600 queries (exceeds 500 chunk size)
            queries = [("test artist", "test song") for _ in range(600)]

            results = vdb.search_batch(queries, limit=1)

            # Should return results for all 600 queries
            assert len(results) == 600
            # All should find the same track
            for result in results:
                assert len(result) == 1
                assert result[0][0] == 1
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorDBPersistence:
    """Test persistence across instances."""

    def test_persistence_across_instances(self):
        """Test that data persists when creating new instance."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            # Create first instance and add data
            vdb1 = VectorDB(persist_path=temp_dir)
            vdb1.add_track(1, "foo fighters", "everlong")

            # Reset singleton
            VectorDB._instance = None

            # Create new instance with same path
            vdb2 = VectorDB(persist_path=temp_dir)

            # Data should persist
            count = vdb2.collection.count()
            assert count == 1

            # Should be able to search
            matches = vdb2.search("foo fighters", "everlong", limit=1)
            assert len(matches) == 1
            assert matches[0][0] == 1
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVectorDBDistanceThreshold:
    """Test distance threshold behavior."""

    def test_distance_increases_with_dissimilarity(self):
        """Test that distance increases as queries become less similar."""
        # Reset singleton for test
        VectorDB._instance = None

        temp_dir = tempfile.mkdtemp()
        try:
            vdb = VectorDB(persist_path=temp_dir)
            vdb.add_track(1, "nirvana", "smells like teen spirit")

            # Exact match
            exact_matches = vdb.search("nirvana", "smells like teen spirit", limit=1)
            exact_distance = exact_matches[0][1]

            # Similar match
            similar_matches = vdb.search("nirvana", "smells like", limit=1)
            similar_distance = similar_matches[0][1]

            # Very different match
            different_matches = vdb.search("completely", "different song", limit=1)
            different_distance = different_matches[0][1]

            # Distances should increase
            assert exact_distance < similar_distance
            assert similar_distance < different_distance
        finally:
            VectorDB._instance = None
            shutil.rmtree(temp_dir, ignore_errors=True)
