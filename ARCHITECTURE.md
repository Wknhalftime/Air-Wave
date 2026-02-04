# Airwave Architecture Documentation

## Overview
Airwave is a Radio Broadcast Archiving & Analytics System that solves the "Double Imperfect" data problem: matching messy radio broadcast logs with inconsistent local music library metadata.

## System Architecture

### Technology Stack
- **Backend**: Python 3.13, FastAPI, SQLAlchemy (Async), SQLite/DuckDB
- **Frontend**: React, TypeScript, Vite, TailwindCSS
- **AI/ML**: ChromaDB, Sentence Transformers (all-MiniLM-L6-v2)
- **Audio Processing**: Mutagen (metadata), AcoustID (fingerprinting)

---

## Core Modules

### 1. **Core Layer** (`airwave/core/`)
Foundation modules providing shared infrastructure.

#### `models.py` - Database Schema
Defines the complete data model hierarchy:
- **Artist** → **Work** → **Recording** → **LibraryFile** (Music Library)
- **Station** → **BroadcastLog** (Radio Logs)
- **IdentityBridge** (Permanent log-to-recording mappings)
- **ImportBatch** (Import tracking)
- **ArtistAlias**, **ProposedSplit** (Identity resolution)

#### `vector_db.py` - Semantic Search Engine
- Singleton ChromaDB client for vector embeddings
- Uses `all-MiniLM-L6-v2` sentence transformer model
- Provides batch search capabilities for fuzzy matching
- Cosine similarity distance metric

#### `normalization.py` - Text Processing
- `clean()`: Basic text normalization (unicode, accents, punctuation)
- `clean_artist()`: Aggressive artist name normalization (articles, separators)
- `split_artists()`: Collaboration/feature detection
- `extract_version_type()`: Parse version tags (Live, Remix, etc.)
- `generate_signature()`: MD5 hash for identity bridge

#### `db.py` - Database Management
- Async SQLAlchemy engine configuration
- Session factory and dependency injection
- Database initialization and backup utilities
- SQLite pragma optimizations (WAL mode, foreign keys)

#### `config.py` - Configuration
- Pydantic Settings for environment variables
- Matching threshold configurations
- Path management (DATA_DIR, DB_PATH)

#### `task_store.py` - Progress Tracking
- Thread-safe in-memory task progress store
- Real-time progress updates for long-running operations
- SSE (Server-Sent Events) compatible

#### `utils.py` - Utilities
- Date parsing (`parse_flexible_date`)
- Station name inference from filenames

---

### 2. **Worker Layer** (`airwave/worker/`)
Background processing services for data ingestion and matching.

#### `importer.py` - CSV Import Engine
- **CSVImporter**: Processes broadcast log CSV files
- Uses DuckDB for ultra-fast CSV parsing (100k+ rows/sec)
- Chunked processing to avoid SQLite variable limits
- Automatic station detection and batch tracking

#### `scanner.py` - Audio File Scanner
- **FileScanner**: Recursively scans directories for audio files
- Extracts metadata using Mutagen (MP3, FLAC, M4A, WAV, OGG)
- Thread pool executor for blocking I/O operations
- Creates/updates Artist → Work → Recording → LibraryFile hierarchy
- Handles multi-artist collaborations and album associations

#### `matcher.py` - Intelligent Matching Engine
Multi-strategy matching system with confidence scoring:

**Matching Strategies** (in order):
1. **Identity Bridge** (Exact): Pre-verified log-to-recording mappings
2. **Exact Match**: Normalized artist + title exact match
3. **Variant Match**: High fuzzy similarity (85% artist, 80% title)
4. **Vector Semantic**: ChromaDB cosine similarity search
5. **Alias Match**: Lower threshold for manual review (70%)

**Key Methods**:
- `match_batch()`: Bulk matching with deduplication
- `scan_and_promote()`: Create library recordings from unique logs
- `link_orphaned_logs()`: Auto-link logs via identity bridge

#### `identity_resolver.py` - Artist Identity Resolution
- Resolves artist aliases (e.g., "GnR" → "Guns N' Roses")
- Detects collaborations ("A feat. B")
- Proposes artist splits for manual review
- Batch resolution for performance

#### `fingerprint.py` - Audio Fingerprinting
- AcoustID integration for audio fingerprinting
- Identifies tracks from audio analysis
- Fallback for metadata-less files

#### `main.py` - CLI Worker Interface
Command-line interface for all worker operations:
- `init-db`: Initialize database schema
- `import <file>`: Import CSV broadcast logs
- `scan`: Populate library from unique logs
- `sync-files <path>`: Scan audio directory
- `reindex`: Rebuild vector search index
- `debug-match`: Test matching logic

---

### 3. **API Layer** (`airwave/api/`)
FastAPI REST API with async endpoints.

#### `main.py` - Application Entry Point
- FastAPI app initialization
- CORS middleware for frontend
- Router registration
- Lifespan context for startup/shutdown

#### Routers (`api/routers/`)

**`system.py`** - System Health
- `/health`: Database connectivity check
- `/config`: Public configuration

**`library.py`** - Music Library
- `/recordings`: List/search recordings
- `/artists`: Artist management
- `/albums`: Album browsing

**`history.py`** - Broadcast Logs
- `/logs`: Query broadcast history
- Date-based filtering
- Station-specific views

**`admin.py`** - Administrative Operations
- `/import`: Upload CSV files
- `/scan`: Trigger library scan
- `/sync-files`: Sync audio directory
- `/settings`: System settings management
- `/progress/{task_id}`: SSE progress streaming
- `/match-explain`: Diagnostic matching tool

**`analytics.py`** - Statistics
- `/dashboard`: High-level metrics
- `/top-artists`: Most played artists
- `/top-tracks`: Most played recordings

**`search.py`** - Universal Search
- Unified search across recordings and logs
- Type filtering (track/log/all)

**`identity.py`** - Identity Management
- `/bridges`: Manage identity bridges
- `/aliases`: Artist alias management
- `/proposed-splits`: Review collaboration splits

---

## Data Flow

### Import Workflow
```
CSV File → CSVImporter (DuckDB) → BroadcastLog records → Matcher → IdentityBridge
```

### Library Scan Workflow
```
Audio Directory → FileScanner (Mutagen) → Artist/Work/Recording/LibraryFile → VectorDB Index
```

### Matching Workflow
```
Raw Log → Normalizer → Identity Bridge Check → Exact Match → Fuzzy Match → Vector Search → Result
```

---

## Key Design Patterns

1. **Identity-First Architecture**: Permanent mappings via IdentityBridge prevent re-matching
2. **Batch Processing**: All operations optimized for bulk processing
3. **Lazy Vector Indexing**: ChromaDB only used when exact/fuzzy matching fails
4. **Normalization Pipeline**: Consistent text processing across all modules
5. **Async-First**: All I/O operations use async/await
6. **Progress Tracking**: Real-time feedback for long operations

---

## Performance Optimizations

- **DuckDB CSV Import**: 100x faster than pandas/csv module
- **Batch Vector Search**: Reduces ChromaDB query overhead
- **SQLite WAL Mode**: Concurrent reads during writes
- **Thread Pool Executors**: Parallel metadata extraction
- **Deduplication**: Avoid redundant matching operations
- **Composite Indexes**: Optimized time-range queries

---

## Configuration

Key settings in `core/config.py`:
- `MATCH_VARIANT_ARTIST_SCORE`: 0.85 (High confidence threshold)
- `MATCH_VARIANT_TITLE_SCORE`: 0.80
- `MATCH_ALIAS_ARTIST_SCORE`: 0.70 (Review threshold)
- `MATCH_VECTOR_STRONG_DIST`: 0.15 (Cosine distance)

---

## Future Enhancements

- **Time Machine Playback**: Simulate historical broadcasts
- **Gap-Aware Player**: Skip missing assets intelligently
- **MusicBrainz Integration**: Enhanced metadata enrichment
- **Multi-Station Sync**: Parallel import from multiple sources

