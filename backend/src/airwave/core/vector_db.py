"""Vector database module for semantic track matching using ChromaDB.

This module provides a singleton ChromaDB client for performing semantic
similarity searches on music tracks using sentence transformer embeddings.
The vector database enables fuzzy matching when exact string matching fails.

Typical usage example:
    vector_db = VectorDB()
    vector_db.add_track(123, "The Beatles", "Hey Jude")
    matches = vector_db.search("Beatles", "Hey Jude", limit=5)
"""

import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from airwave.core.config import settings
from chromadb.utils import embedding_functions
from loguru import logger


class VectorDB:
    """Singleton vector database for semantic track matching.

    This class manages a persistent ChromaDB instance for storing and searching
    music track embeddings. It uses the all-MiniLM-L6-v2 sentence transformer
    model to generate 384-dimensional embeddings and performs cosine similarity
    searches for fuzzy matching.

    The singleton pattern ensures only one ChromaDB connection exists across
    the application lifecycle, preventing resource leaks and connection overhead.

    Attributes:
        client: ChromaDB persistent client instance.
        ef: Sentence transformer embedding function.
        collection: ChromaDB collection for track embeddings.
        persist_path: File system path for ChromaDB storage.
    """

    _instance: Optional["VectorDB"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "VectorDB":
        """Ensures only one instance of VectorDB exists (Singleton pattern).

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The singleton VectorDB instance.
        """
        if not cls._instance:
            cls._instance = super(VectorDB, cls).__new__(cls)
        return cls._instance

    def __init__(self, persist_path: Optional[str] = None) -> None:
        """Initializes the vector database client and embedding model.

        Creates a persistent ChromaDB client with the all-MiniLM-L6-v2 embedding
        function. The collection uses cosine distance for semantic similarity.

        Args:
            persist_path: File system path to store ChromaDB data.
                Defaults to settings.DATA_DIR / "chroma". If the directory
                doesn't exist, it will be created automatically.

        Note:
            This method is idempotent - subsequent calls on the singleton
            instance will not re-initialize the client.
        """
        if hasattr(self, "client"):  # Prevent re-initialization in Singleton
            return

        self.persist_path = persist_path or str(settings.DATA_DIR / "chroma")

        # Ensure directory exists
        os.makedirs(self.persist_path, exist_ok=True)

        logger.info(f"Initializing ChromaDB at {self.persist_path}")
        self.client = chromadb.PersistentClient(path=self.persist_path)

        # Use a lightweight model for embeddings (384 dimensions)
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        self.collection = self.client.get_or_create_collection(
            name="tracks",
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},  # Semantic distance metric
        )
        # Serialize ChromaDB writes to avoid "Database is locked" under parallel load
        self._write_lock = threading.Lock()

    def add_track(self, track_id: int, artist: str, title: str) -> None:
        """Adds a single track to the vector index.

        This is a convenience wrapper around add_tracks() for single insertions.

        Args:
            track_id: Database ID of the recording (primary key).
            artist: Normalized artist name (should be pre-cleaned).
            title: Normalized track title (should be pre-cleaned).

        Example:
            vector_db.add_track(123, "beatles", "hey jude")
        """
        self.add_tracks([(track_id, artist, title)])

    def add_tracks(self, tracks: List[Tuple[int, str, str]]) -> None:
        """Adds multiple tracks to the vector index in bulk.

        Performs upsert operation - existing tracks with the same ID will be
        updated with new embeddings. This is the preferred method for indexing
        as it's significantly faster than individual insertions.

        Args:
            tracks: List of tuples containing (recording_id, artist, title).
                Artist and title should be normalized before indexing.

        Note:
            Empty list is a no-op. The document format is "artist - title"
            which matches the query format used in search methods.

        Example:
            tracks = [(1, "beatles", "hey jude"), (2, "queen", "bohemian rhapsody")]
            vector_db.add_tracks(tracks)
        """
        if not tracks:
            return

        # Deduplicate by recording_id (ChromaDB requires unique IDs per batch).
        # Keep last occurrence so most recent metadata wins.
        seen: Dict[int, Tuple[int, str, str]] = {}
        for t in tracks:
            seen[t[0]] = t
        tracks = list(seen.values())

        ids = [str(t[0]) for t in tracks]
        documents = [f"{t[1]} - {t[2]}" for t in tracks]
        metadatas = [{"artist": t[1], "title": t[2]} for t in tracks]

        with self._write_lock:
            self.collection.upsert(
                ids=ids, documents=documents, metadatas=metadatas
            )

    def search(
        self,
        artist: str,
        title: str,
        limit: int = 1,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[int, float]]:
        """Searches for tracks semantically similar to the provided artist/title.

        Uses cosine similarity on sentence transformer embeddings to find
        the most similar tracks in the index. Lower distance indicates
        higher similarity.

        Args:
            artist: Raw or normalized artist name from broadcast log.
            title: Raw or normalized track title from broadcast log.
            limit: Maximum number of matches to return. Defaults to 1.
            where: Optional ChromaDB metadata filter dictionary.
                Example: {"artist": "beatles"} to filter by artist.

        Returns:
            List of (track_id, distance) tuples sorted by similarity.
            Distance is cosine distance (0.0 = identical, 2.0 = opposite).
            Empty list if no matches found.

        Example:
            matches = vector_db.search("Beatles", "Hey Jude", limit=5)
            for track_id, distance in matches:
                print(f"Track {track_id}: distance={distance:.3f}")
        """
        query_text = f"{artist} - {title}"

        results = self.collection.query(
            query_texts=[query_text], n_results=limit, where=where
        )

        matches = []
        if (
            results["ids"]
            and len(results["ids"]) > 0
            and results["distances"]
            and len(results["distances"]) > 0
        ):
            for i in range(len(results["ids"][0])):
                track_id = int(results["ids"][0][i])
                distance = results["distances"][0][i]
                matches.append((track_id, distance))

        return matches

    def search_batch(
        self, queries: List[Tuple[str, str]], limit: int = 1
    ) -> List[List[Tuple[int, float]]]:
        """Performs bulk semantic searches for a list of queries.

        Optimized for batch processing - significantly faster than calling
        search() in a loop. Automatically chunks queries to avoid SQLite
        variable limits (500 queries per batch).

        Args:
            queries: List of (artist, title) tuples to search for.
            limit: Maximum matches to return per query. Defaults to 1.

        Returns:
            List of result lists, where each inner list contains
            (track_id, distance) tuples for the corresponding input query.
            The outer list has the same length and order as the input queries.
            Empty inner lists indicate no matches for that query.

        Example:
            queries = [("Beatles", "Hey Jude"), ("Queen", "Bohemian Rhapsody")]
            results = vector_db.search_batch(queries, limit=3)
            for i, matches in enumerate(results):
                print(f"Query {i}: {len(matches)} matches")
        """
        if not queries:
            return []

        # Batching to avoid SQLite/OS variable limits
        batch_size = 500
        all_matches: List[List[Tuple[int, float]]] = []

        for i in range(0, len(queries), batch_size):
            chunk = queries[i : i + batch_size]
            query_texts = [f"{q[0]} - {q[1]}" for q in chunk]

            results = self.collection.query(
                query_texts=query_texts, n_results=limit
            )

            # Chroma returns nested lists for batch queries
            if (
                results["ids"]
                and len(results["ids"]) > 0
                and results["distances"]
                and len(results["distances"]) > 0
            ):
                for j in range(len(query_texts)):
                    row_matches = []
                    ids = results["ids"][j]
                    dists = results["distances"][j]

                    for k in range(len(ids)):
                        track_id = int(ids[k])
                        dist = dists[k]
                        row_matches.append((track_id, dist))

                    all_matches.append(row_matches)

        return all_matches
