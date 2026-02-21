# Airwave - Current Architecture (2026-02-20)

**Last Updated:** 2026-02-20  
**Status:** Production-Ready

This document provides a comprehensive overview of Airwave's current architecture, focusing on the major systems and recent improvements.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Identity Resolution Architecture (Phase 4)](#identity-resolution-architecture-phase-4)
3. [Match Tuner System](#match-tuner-system)
4. [Discovery & Verification Hub](#discovery--verification-hub)
5. [Performance Optimizations](#performance-optimizations)
6. [Data Model](#data-model)

---

## System Overview

Airwave is a broadcast log management system that:
1. **Imports** broadcast logs from radio stations
2. **Matches** raw artist/title pairs to library recordings
3. **Verifies** uncertain matches through a user-friendly UI
4. **Exports** matched data for music scheduling software

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     AIRWAVE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Import     │───▶│   Matcher    │───▶│  Discovery   │  │
│  │   Logs       │    │   Engine     │    │    Queue     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ BroadcastLog │    │   Identity   │    │ Verification │  │
│  │   (work_id)  │    │    Bridge    │    │     Hub      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │         │
│         └────────────────────┴────────────────────┘         │
│                              │                              │
│                              ▼                              │
│                      ┌──────────────┐                       │
│                      │    Export    │                       │
│                      │   (Matched)  │                       │
│                      └──────────────┘                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Identity Resolution Architecture (Phase 4)

### Three-Layer Resolution

Airwave uses a **three-layer architecture** to separate identity resolution from version selection:

| Layer | Concern | Question | Decided At | Granularity |
|-------|---------|----------|------------|-------------|
| **Identity** | What song? | "BEATLES\|HEY JUDE" = Work #42 | Verification time | Work |
| **Policy** | Which version? | Station K-ROCK prefers Recording #102 | Configuration time | Recording |
| **Resolution** | Which file? | Recording #102 → `/music/beatles/hey_jude.flac` | Playback time | LibraryFile |

### Key Changes from Phase 3

**Phase 3 (Old):**
```python
BroadcastLog.recording_id → Recording → LibraryFile
IdentityBridge.recording_id → Recording
DiscoveryQueue.suggested_recording_id → Recording
```

**Phase 4 (Current):**
```python
BroadcastLog.work_id → Work → [Recordings] → [LibraryFiles]
IdentityBridge.work_id → Work
DiscoveryQueue.suggested_work_id → Work
```

### Benefits

1. **Flexibility**: Can change preferred recording without re-verification
2. **Resilience**: If a file is deleted, can fall back to another recording
3. **Policy Support**: Can express "Station X prefers radio edits"
4. **Separation of Concerns**: Identity (what song?) vs Policy (which version?)

### Implementation Status

✅ **Fully Implemented** - All tables migrated to use `work_id`  
✅ **Matcher Updated** - Returns work_id for all match types  
✅ **Discovery Queue** - Uses `suggested_work_id`  
✅ **Verification Hub** - Works with work-level suggestions  
✅ **Export** - Resolves work_id to recording at runtime

---

## Match Tuner System

The Match Tuner is a comprehensive threshold calibration tool that allows users to fine-tune matching behavior.

### Four-Phase Implementation (All Complete)

#### Phase 1: Foundation (MVP)
- Match example cards with full score visibility
- Similarity scores (artist, title, vector)
- Category badges (Auto/Review/Reject/Identity Bridge)
- Quality warnings (truncation, length mismatch, extra text, case only)

#### Phase 2: Impact Visibility
- Real-time impact summary (auto/review/reject counts)
- Statistical sampling (1,000 logs, ±3% accuracy)
- Performance optimized to 3-5 seconds

#### Phase 3: Edge Case Highlighting
- Edge case detection (within 5% of thresholds)
- Amber warning boxes on borderline matches
- Edge case counter in header

#### Phase 4: 2D Visualization
- Interactive scatter plot (Recharts)
- Color-coded dots by category
- Threshold lines (horizontal/vertical)
- Hover tooltips and click-to-inspect
- View toggle (List ↔ 2D)

### Three-Range Filtering

The matcher categorizes matches into three ranges:

```
┌─────────────────────────────────────────────────────────────┐
│                    THREE-RANGE FILTERING                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  100% ┌──────────────────────────────────────────────────┐  │
│       │                                                  │  │
│       │         AUTO-LINK RANGE                          │  │
│       │  (Both artist AND title ≥ auto thresholds)      │  │
│       │  → Auto-link to BroadcastLog.work_id            │  │
│       │  → Bypass Discovery Queue                       │  │
│   85% ├──────────────────────────────────────────────────┤  │
│       │                                                  │  │
│       │         REVIEW RANGE                             │  │
│       │  (Both ≥ review, at least one < auto)           │  │
│       │  → Add to Discovery Queue with suggestion       │  │
│       │  → Appear in Verification Hub                   │  │
│   70% ├──────────────────────────────────────────────────┤  │
│       │                                                  │  │
│       │         REJECT RANGE                             │  │
│       │  (Either artist OR title < review)              │  │
│       │  → Don't add to Discovery Queue                 │  │
│       │  → Don't appear in Verification Hub             │  │
│    0% └──────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Thresholds (Configurable via Match Tuner UI)

| Threshold | Default | Description |
|-----------|---------|-------------|
| `MATCH_VARIANT_ARTIST_SCORE` | 0.85 | Auto-accept threshold for artist |
| `MATCH_VARIANT_TITLE_SCORE` | 0.80 | Auto-accept threshold for title |
| `MATCH_ALIAS_ARTIST_SCORE` | 0.70 | Review threshold for artist |
| `MATCH_ALIAS_TITLE_SCORE` | 0.70 | Review threshold for title |

---

## Discovery & Verification Hub

### Artist Linking (Decoupled from Song Matching)

**Key Architectural Decision:** Artist linking is **independent** of song matching.

#### Before (Incorrect - Coupled)
```python
# Only showed artists from DiscoveryQueue (unmatched songs)
stmt = select(DiscoveryQueue.raw_artist).group_by(...)
```

#### After (Correct - Decoupled)
```python
# Shows artists from ALL BroadcastLog entries
stmt = select(BroadcastLog.raw_artist).group_by(...)
```

**Benefits:**
- ✅ Proactive alias creation (before songs fail to match)
- ✅ Can normalize artist names across entire dataset
- ✅ Separation of concerns (artist identity vs song matching)
- ✅ Optional filtering by match status (all/matched/unmatched)

### Song Linking

Shows individual song matches that need verification:
- Raw artist/title → Suggested work
- Similarity scores and match reason
- Link/Reject/Promote actions

### Identity Bridge

Pre-verified permanent mappings:
- Signature (hash of raw_artist|raw_title) → work_id
- Bypasses matching for recurring logs
- Auto-links on future imports

---

## Performance Optimizations

### Rematch Batching (2026-02-20)

**Problem:** Re-matching after artist linking was 5-10x slower than initial discovery.

**Root Cause:** Processing items one-at-a-time instead of batching.

**Solution:** Refactored to use batching (same as initial discovery).

#### Before (Slow)
```python
for signature in signatures:
    item = await db.get(DiscoveryQueue, signature)
    rec_id, reason = await matcher.find_match(item.raw_artist, item.raw_title)
```

#### After (Fast)
```python
# Fetch all items at once
items = (await db.execute(select(DiscoveryQueue).where(...))).scalars().all()

# Process in batches of 500
BATCH_SIZE = 500
for i in range(0, len(items), BATCH_SIZE):
    batch_queries = [(item.raw_artist, item.raw_title) for item in batch_items]
    matches = await matcher.match_batch(batch_queries)
```

**Performance Impact:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Processing | One-at-a-time | Batches of 500 | - |
| Speed | ~10-20 items/sec | ~100-200 items/sec | **10x faster** |
| Time (1000 items) | ~50-100 sec | ~5-10 sec | **10x faster** |
| Database Queries | ~1000 | ~2-3 | **300x fewer** |
| Vector Searches | ~1000 | ~2 | **500x fewer** |

### Stratified Sampling

Match Tuner uses stratified sampling for representative examples:
- Samples 1,000 logs for comprehensive coverage
- Returns 10-15 examples per category
- Shows variety and patterns, not just outliers
- Performance: 3-5 seconds

---

## Data Model

### Core Tables

#### BroadcastLog (Identity Layer)
```python
class BroadcastLog(Base, TimestampMixin):
    id: Mapped[int]
    station_id: Mapped[int]
    played_at: Mapped[datetime]
    raw_artist: Mapped[str]
    raw_title: Mapped[str]
    work_id: Mapped[Optional[int]]  # Phase 4: Links to Work
    match_reason: Mapped[Optional[str]]
```

#### IdentityBridge (Verified Mappings)
```python
class IdentityBridge(Base, TimestampMixin):
    id: Mapped[int]
    log_signature: Mapped[str]  # Hash(raw_artist|raw_title)
    reference_artist: Mapped[str]
    reference_title: Mapped[str]
    work_id: Mapped[int]  # Phase 4: Links to Work
    is_verified: Mapped[bool]
```

#### DiscoveryQueue (Unmatched/Review Items)
```python
class DiscoveryQueue(Base, TimestampMixin):
    signature: Mapped[str]  # Primary key
    raw_artist: Mapped[str]
    raw_title: Mapped[str]
    count: Mapped[int]  # Number of occurrences
    suggested_work_id: Mapped[Optional[int]]  # Phase 4: Work suggestion
```

#### ArtistAlias (Artist Name Normalization)
```python
class ArtistAlias(Base, TimestampMixin):
    id: Mapped[int]
    raw_name: Mapped[str]  # e.g., "BEATLES"
    resolved_name: Mapped[str]  # e.g., "The Beatles"
    is_verified: Mapped[bool]
```

#### Work (Identity Layer)
```python
class Work(Base, TimestampMixin):
    id: Mapped[int]
    title: Mapped[str]
    artist_id: Mapped[int]  # Primary artist
    artists: Mapped[List[Artist]]  # Multi-artist support
    recordings: Mapped[List[Recording]]  # Multiple versions
```

#### Recording (Version Layer)
```python
class Recording(Base, TimestampMixin):
    id: Mapped[int]
    work_id: Mapped[int]
    title: Mapped[str]
    version_type: Mapped[str]  # Original, Radio Edit, Live, etc.
    library_files: Mapped[List[LibraryFile]]
```

---

## Matching Pipeline

### Match Strategies (in priority order)

1. **Identity Bridge** - Pre-verified permanent mappings (instant)
2. **Exact Match** - Normalized exact string matching
3. **High Confidence** - Fuzzy similarity above auto-accept threshold
4. **Review Confidence** - Fuzzy similarity above review threshold
5. **Vector Semantic** - ChromaDB cosine similarity search

### Match Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     MATCHING PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Raw Log: "BEATLES" - "HEY JUDE"                            │
│       │                                                      │
│       ▼                                                      │
│  1. Check Identity Bridge                                   │
│       │                                                      │
│       ├─ Found? → Return work_id (instant)                  │
│       │                                                      │
│       └─ Not found? → Continue                              │
│              │                                               │
│              ▼                                               │
│  2. Normalize: "beatles" - "hey jude"                       │
│              │                                               │
│              ▼                                               │
│  3. Exact Match (database)                                  │
│       │                                                      │
│       ├─ Found? → Return recording_id (convert to work_id)  │
│       │                                                      │
│       └─ Not found? → Continue                              │
│              │                                               │
│              ▼                                               │
│  4. Fuzzy Match (difflib)                                   │
│       │                                                      │
│       ├─ High Confidence (≥85% artist, ≥80% title)?         │
│       │   → Return recording_id (auto-accept)               │
│       │                                                      │
│       ├─ Review Confidence (≥70% both)?                     │
│       │   → Return recording_id (needs review)              │
│       │                                                      │
│       └─ Low confidence? → Continue                         │
│              │                                               │
│              ▼                                               │
│  5. Vector Search (ChromaDB)                                │
│       │                                                      │
│       ├─ Found with title guard?                            │
│       │   → Return recording_id (needs review)              │
│       │                                                      │
│       └─ Not found? → No Match                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Recent Changes & Fixes

### 2026-02-20

1. **Artist Linking Decoupling**
   - Changed from DiscoveryQueue to BroadcastLog
   - Added filter_type parameter (all/matched/unmatched)
   - Enables proactive alias creation

2. **Rematch Batching Optimization**
   - Refactored to use batching (500 items per batch)
   - 10x performance improvement
   - Reduced database queries by 300x

3. **Match Tuner Stratified Sampling Fixes**
   - Fixed inconsistent category logic
   - Fixed incorrect threshold comparisons
   - Increased sample size to 1,000 logs
   - Now shows 10-15 examples per category

4. **Phase 4 Migration Complete**
   - All tables migrated to use work_id
   - Matcher updated to return work_id
   - Discovery Queue uses suggested_work_id
   - Verification Hub works with work-level suggestions

---

## See Also

- [Identity Resolution Architecture](./planning/identity-resolution-architecture.md) - Detailed Phase 4 architecture
- [Match Tuner - All Phases Complete](./match-tuner-all-phases-complete.md) - Comprehensive Match Tuner documentation
- [Artist Linking Decoupling Fix](./artist-linking-decoupling-fix.md) - Artist linking architectural fix
- [Rematch Batching Optimization](./rematch-batching-optimization.md) - Performance optimization details
- [Library Navigation System](./PROJECT_SUMMARY.md) - Library navigation feature documentation


