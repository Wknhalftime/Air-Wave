# Identity Resolution Architecture

## Executive Summary

This document proposes a **three-layer architecture** for resolving broadcast log identities to library files, replacing the current direct-binding approach with a more flexible **Policy-Based Matching** pattern.

---

## Problem Statement

### Current Architecture (Direct Binding)

```
BroadcastLog.recording_id → Recording → LibraryFile
IdentityBridge.recording_id → Recording
DiscoveryQueue.suggested_recording_id → Recording
```

**Issues identified:**

1. **Loss of flexibility**: A verified signature is permanently bound to a specific recording version
2. **Brittle to file changes**: If a LibraryFile is deleted/moved, the link breaks
3. **No policy support**: Cannot express "Station X prefers radio edits" without re-verification
4. **Conflated concerns**: Identity (what song?) and policy (which version?) are merged into one decision

### Original Plan's Proposal

The Verification Hub Redesign plan proposed changing `recording_id` to `work_id` across all tables. This was **directionally correct** but incomplete—it would lose version precision without providing a mechanism to recover it.

---

## Proposed Architecture: Three-Layer Resolution

### Layer Overview

| Layer | Concern | Question Answered | When Decided | Granularity |
|-------|---------|-------------------|--------------|-------------|
| **Identity** | What song is this? | "BEATLES\|HEY JUDE" = Work #42 | Verification time | Work |
| **Policy** | Which version should we use? | Station K-ROCK prefers Recording #102 | Configuration time | Recording |
| **Resolution** | Which file is available? | Recording #102 → `/music/beatles/hey_jude.flac` | Playback time | LibraryFile |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VERIFICATION FLOW                                │
├─────────────────────────────────────────────────────────────────────────┤
│  BroadcastLog                                                           │
│  ├── raw_artist: 'NIRVANA'                                              │
│  ├── raw_title: 'ALL APOLOGIES'                                         │
│  └── work_id: NULL (unmatched)                                          │
│              │                                                          │
│              ▼                                                          │
│  [Matcher/Discovery] → DiscoveryQueue                                   │
│              │           └── suggested_work_id: 99                      │
│              ▼                                                          │
│  [User Verifies] → IdentityBridge                                       │
│                     ├── signature: 'nirvana|all apologies'              │
│                     └── work_id: 99  ✓                                  │
│              │                                                          │
│              ▼                                                          │
│  [Backfill] → BroadcastLog.work_id = 99                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        RESOLUTION FLOW (Runtime)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Request: 'Get file for Work 99, Station K-ROCK'                        │
│              │                                                          │
│              ▼                                                          │
│  [Policy Engine]                                                        │
│  ├── Check: StationPreference(K-ROCK, Work 99) → Recording 201 (MTV)   │
│  ├── Fallback: GlobalDefault(Work 99) → Recording 200 (In Utero)       │
│  └── Emergency: Any Recording for Work 99                               │
│              │                                                          │
│              ▼                                                          │
│  [File Resolver]                                                        │
│  ├── Recording 201 → LibraryFile '/music/nirvana/mtv_unplugged.flac'   │
│  └── (or next available if file missing)                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model Changes

### Modified Tables

#### IdentityBridge (Identity Layer)

```python
class IdentityBridge(Base, TimestampMixin):
    """Maps verified signatures to Works (not Recordings)."""
    
    id: Mapped[int] = mapped_column(primary_key=True)
    log_signature: Mapped[str] = mapped_column(String, unique=True, index=True)
    reference_artist: Mapped[str] = mapped_column(String)
    reference_title: Mapped[str] = mapped_column(String)
    
    # CHANGED: Now links to Work, not Recording
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"))
    
    confidence: Mapped[float] = mapped_column(default=1.0)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    work: Mapped["Work"] = relationship()
```

#### BroadcastLog (Identity Layer)

```python
class BroadcastLog(Base, TimestampMixin):
    """An individual play-event extracted from a station log."""
    
    # ... existing fields ...
    
    # CHANGED: Now links to Work, not Recording
    work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), nullable=True, index=True
    )
    
    # DEPRECATED: Keep for migration, remove later
    # recording_id: Mapped[Optional[int]] = mapped_column(...)
```

#### DiscoveryQueue (Identity Layer)

```python
class DiscoveryQueue(Base, TimestampMixin):
    """Aggregation layer for unmatched logs."""
    
    signature: Mapped[str] = mapped_column(String, primary_key=True)
    raw_artist: Mapped[str] = mapped_column(String)
    raw_title: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=1)
    
    # CHANGED: Suggest Works, not Recordings
    suggested_work_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("works.id"), nullable=True
    )
    
    # Relationships
    suggested_work: Mapped[Optional["Work"]] = relationship()
```

### New Tables (Policy Layer)

#### StationPreference

```python
class StationPreference(Base, TimestampMixin):
    """Station-specific recording preferences for a work."""
    
    __tablename__ = "station_preferences"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    preferred_recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"))
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Lower = higher priority
    
    # Relationships
    station: Mapped["Station"] = relationship()
    work: Mapped["Work"] = relationship()
    preferred_recording: Mapped["Recording"] = relationship()
    
    __table_args__ = (
        Index("idx_station_pref_lookup", "station_id", "work_id"),
    )
```

#### FormatPreference

```python
class FormatPreference(Base, TimestampMixin):
    """Format-based recording preferences (e.g., AC stations prefer radio edits)."""
    
    __tablename__ = "format_preferences"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    format_code: Mapped[str] = mapped_column(String, index=True)  # 'AC', 'CHR', 'ROCK'
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    preferred_recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"))
    exclude_tags: Mapped[list] = mapped_column(JSON, default=list)  # ['explicit', 'live']
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    __table_args__ = (
        Index("idx_format_pref_lookup", "format_code", "work_id"),
    )
```

#### WorkDefaultRecording

```python
class WorkDefaultRecording(Base, TimestampMixin):
    """Global default recording for a work when no other preference applies."""
    
    __tablename__ = "work_default_recordings"
    
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), primary_key=True)
    default_recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"))
    
    work: Mapped["Work"] = relationship()
    default_recording: Mapped["Recording"] = relationship()
```

---

## Resolution Service

### RecordingResolver

```python
class RecordingResolver:
    """Resolves a Work to a Recording based on context and policies."""
    
    async def resolve(
        self,
        work_id: int,
        station_id: Optional[int] = None,
        format_code: Optional[str] = None,
        db: AsyncSession = None
    ) -> Optional[Recording]:
        """
        Resolution priority:
        1. Station-specific preference
        2. Format-based preference
        3. Work default recording
        4. Any available recording for the work
        """
        
        # 1. Check station preference
        if station_id:
            pref = await self._get_station_preference(db, station_id, work_id)
            if pref and await self._has_available_file(db, pref.preferred_recording_id):
                return pref.preferred_recording
        
        # 2. Check format preference
        if format_code:
            pref = await self._get_format_preference(db, format_code, work_id)
            if pref and await self._has_available_file(db, pref.preferred_recording_id):
                return pref.preferred_recording
        
        # 3. Check work default
        default = await self._get_work_default(db, work_id)
        if default and await self._has_available_file(db, default.default_recording_id):
            return default.default_recording
        
        # 4. Fallback: any recording with available file
        return await self._get_any_available_recording(db, work_id)
    
    async def _has_available_file(self, db: AsyncSession, recording_id: int) -> bool:
        """Check if recording has at least one accessible library file."""
        stmt = select(LibraryFile).where(LibraryFile.recording_id == recording_id).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None
```

---

## Use Cases

### Use Case 1: Radio Log Matching

**Scenario**: Station WXYZ broadcasts "All Apologies" by Nirvana

```
Input:  raw_artist='NIRVANA', raw_title='ALL APOLOGIES'
        
Step 1: Generate signature → 'nirvana|all apologies'
Step 2: Lookup IdentityBridge → work_id=99 (All Apologies)
Step 3: Resolve recording → RecordingResolver.resolve(work_id=99, station_id=WXYZ)
        - No station preference → check format preference
        - WXYZ is format 'ROCK' → no format preference
        - Check work default → Recording 200 (In Utero version)
        - File exists → Return Recording 200
```

### Use Case 2: Station Preference Override

**Scenario**: Station K-ROCK prefers the MTV Unplugged version

```
Configuration:
  StationPreference(station_id=K-ROCK, work_id=99, preferred_recording_id=201)

Resolution:
  RecordingResolver.resolve(work_id=99, station_id=K-ROCK)
  → Recording 201 (MTV Unplugged version)
```

### Use Case 3: File Deletion Resilience

**Scenario**: The preferred file is deleted

```
State:
  - Work 99 has Recording 200 (In Utero) and Recording 201 (MTV Unplugged)
  - Recording 200's LibraryFile is deleted
  
Resolution:
  RecordingResolver.resolve(work_id=99, station_id=WXYZ)
  → Checks Recording 200 → no file available
  → Falls back to Recording 201 → file exists
  → Returns Recording 201
```

### Use Case 4: Format-Based Filtering

**Scenario**: AC stations must avoid explicit content

```
Configuration:
  FormatPreference(format_code='AC', work_id=99, exclude_tags=['explicit'])
  
Resolution for AC station:
  - Skip explicit recordings automatically
  - Return radio edit or clean version
```

---

## Migration Strategy

### Phase 1: Add New Columns (Non-Breaking)

```sql
-- Add work_id to existing tables (nullable)
ALTER TABLE identity_bridge ADD COLUMN work_id INTEGER REFERENCES works(id);
ALTER TABLE broadcast_logs ADD COLUMN work_id INTEGER REFERENCES works(id);
ALTER TABLE discovery_queue ADD COLUMN suggested_work_id INTEGER REFERENCES works(id);

-- Create new policy tables
CREATE TABLE station_preferences (...);
CREATE TABLE format_preferences (...);
CREATE TABLE work_default_recordings (...);
```

### Phase 2: Backfill Data

```python
# Backfill work_id from recording_id
async def backfill_work_ids(db: AsyncSession):
    # IdentityBridge
    await db.execute("""
        UPDATE identity_bridge ib
        SET work_id = (SELECT work_id FROM recordings r WHERE r.id = ib.recording_id)
        WHERE work_id IS NULL AND recording_id IS NOT NULL
    """)
    
    # BroadcastLog
    await db.execute("""
        UPDATE broadcast_logs bl
        SET work_id = (SELECT work_id FROM recordings r WHERE r.id = bl.recording_id)
        WHERE work_id IS NULL AND recording_id IS NOT NULL
    """)
    
    # DiscoveryQueue
    await db.execute("""
        UPDATE discovery_queue dq
        SET suggested_work_id = (SELECT work_id FROM recordings r WHERE r.id = dq.suggested_recording_id)
        WHERE suggested_work_id IS NULL AND suggested_recording_id IS NOT NULL
    """)
```

### Phase 3: Update Application Code

1. Modify `IdentityBridge` to use `work_id` instead of `recording_id`
2. Update `Matcher` to suggest `work_id` in `DiscoveryQueue`
3. Implement `RecordingResolver` service
4. Update API endpoints to use resolution flow

### Phase 4: Deprecate Old Columns

```sql
-- After validation period
ALTER TABLE identity_bridge DROP COLUMN recording_id;
ALTER TABLE broadcast_logs DROP COLUMN recording_id;
ALTER TABLE discovery_queue DROP COLUMN suggested_recording_id;
```

---

## Testing Strategy

### Overview

This architecture introduces significant changes to core data models and business logic. A comprehensive testing strategy is **critical** to ensure:
- Data integrity during migration
- Correct resolution behavior across all use cases
- Performance meets production requirements
- Safe rollback capability at each phase

### Unit Tests

#### RecordingResolver Tests

**File**: `backend/tests/services/test_recording_resolver.py`

```python
class TestRecordingResolver:
    """Tests for the RecordingResolver service."""

    async def test_resolve_with_station_preference(self, db_session):
        """Use Case 2: Station preference takes highest priority."""
        # Setup: Work with 2 recordings, station prefers Recording B
        # Assert: resolve() returns Recording B

    async def test_resolve_with_format_preference(self, db_session):
        """Use Case 4: Format preference used when no station preference."""
        # Setup: Work with 2 recordings, format 'AC' prefers Recording A
        # Assert: resolve() returns Recording A

    async def test_resolve_with_work_default(self, db_session):
        """Use Case 1: Work default used when no other preferences."""
        # Setup: Work with default recording set
        # Assert: resolve() returns default recording

    async def test_resolve_fallback_to_any_recording(self, db_session):
        """Fallback: Returns any available recording when no preferences."""
        # Setup: Work with 2 recordings, no preferences set
        # Assert: resolve() returns one of the recordings

    async def test_resolve_skips_unavailable_files(self, db_session):
        """Use Case 3: Skips recordings without available files."""
        # Setup: Preferred recording has no files, fallback has files
        # Assert: resolve() returns fallback recording

    async def test_resolve_returns_none_when_no_recordings(self, db_session):
        """Edge case: Returns None when work has no recordings."""
        # Setup: Work with no recordings
        # Assert: resolve() returns None

    async def test_resolve_priority_order(self, db_session):
        """Verify resolution priority: station > format > default > any."""
        # Setup: All preferences configured
        # Assert: Station preference wins

    async def test_has_available_file_checks_existence(self, db_session):
        """Verify _has_available_file() correctly checks file existence."""
        # Setup: Recording with and without files
        # Assert: Returns True/False correctly
```

#### Model Tests

**File**: `backend/tests/models/test_policy_models.py`

```python
class TestStationPreference:
    """Tests for StationPreference model."""

    async def test_station_preference_creation(self, db_session):
        """Can create station preference with all fields."""

    async def test_station_preference_index_lookup(self, db_session):
        """Index on (station_id, work_id) enables fast lookups."""
        # Verify query plan uses index

    async def test_station_preference_priority_ordering(self, db_session):
        """Multiple preferences ordered by priority field."""


class TestFormatPreference:
    """Tests for FormatPreference model."""

    async def test_format_preference_exclude_tags_json(self, db_session):
        """exclude_tags stored as JSON array."""
        # Setup: Create preference with exclude_tags=['explicit', 'live']
        # Assert: Can query and retrieve tags correctly

    async def test_format_preference_index_lookup(self, db_session):
        """Index on (format_code, work_id) enables fast lookups."""


class TestWorkDefaultRecording:
    """Tests for WorkDefaultRecording model."""

    async def test_work_default_one_per_work(self, db_session):
        """Primary key on work_id ensures one default per work."""
        # Setup: Try to create two defaults for same work
        # Assert: Second insert fails with integrity error
```

### Integration Tests

#### End-to-End Resolution Tests

**File**: `backend/tests/integration/test_resolution_flow.py`

```python
class TestResolutionFlow:
    """End-to-end tests for the complete resolution flow."""

    async def test_full_resolution_with_station_preference(self, db_session):
        """Use Case 2: Complete flow from work_id to file with station preference."""
        # Setup: Create work, recordings, files, station preference
        # Execute: RecordingResolver.resolve(work_id, station_id)
        # Assert: Returns correct recording with accessible file

    async def test_full_resolution_with_file_deletion(self, db_session):
        """Use Case 3: Graceful fallback when preferred file deleted."""
        # Setup: Work with 2 recordings, delete preferred file
        # Execute: resolve()
        # Assert: Returns fallback recording

    async def test_full_resolution_with_format_filtering(self, db_session):
        """Use Case 4: Format-based filtering excludes explicit content."""
        # Setup: Work with explicit and clean recordings
        # Execute: resolve(format_code='AC')
        # Assert: Returns clean recording, skips explicit

    async def test_broadcast_log_to_file_resolution(self, db_session):
        """Complete flow: BroadcastLog → IdentityBridge → Work → Recording → File."""
        # Setup: BroadcastLog with work_id, preferences configured
        # Execute: Full resolution pipeline
        # Assert: Correct file returned
```

### Migration Testing

#### Phase 1: Add New Columns (Non-Breaking)

**File**: `backend/tests/alembic/test_migration_identity_resolution_phase1.py`

```python
async def test_phase1_schema_changes(db_session):
    """Verify Phase 1 adds columns without breaking existing queries."""
    inspector = inspect(db_session.bind)

    # Verify new columns exist
    identity_bridge_cols = [c['name'] for c in inspector.get_columns('identity_bridge')]
    assert 'work_id' in identity_bridge_cols

    broadcast_log_cols = [c['name'] for c in inspector.get_columns('broadcast_logs')]
    assert 'work_id' in broadcast_log_cols

    discovery_queue_cols = [c['name'] for c in inspector.get_columns('discovery_queue')]
    assert 'suggested_work_id' in discovery_queue_cols

    # Verify new tables exist
    tables = inspector.get_table_names()
    assert 'station_preferences' in tables
    assert 'format_preferences' in tables
    assert 'work_default_recordings' in tables

async def test_phase1_backward_compatibility(db_session):
    """Existing queries using recording_id still work."""
    # Execute: Old-style query using recording_id
    # Assert: No errors, returns correct data

async def test_phase1_new_columns_nullable(db_session):
    """New work_id columns are nullable (non-breaking)."""
    # Insert: New row without work_id
    # Assert: Insert succeeds
```

#### Phase 2: Backfill Data

**File**: `backend/tests/alembic/test_migration_identity_resolution_phase2.py`

```python
async def test_phase2_backfill_identity_bridge(db_session):
    """Backfill correctly populates work_id from recording relationships."""
    # Setup: IdentityBridge entries with recording_id
    # Execute: Backfill script
    # Assert: work_id = recording.work_id for all rows

async def test_phase2_backfill_broadcast_logs(db_session):
    """Backfill correctly populates work_id in broadcast_logs."""
    # Setup: BroadcastLog entries with recording_id
    # Execute: Backfill script
    # Assert: work_id matches recording.work_id

async def test_phase2_backfill_discovery_queue(db_session):
    """Backfill correctly populates suggested_work_id."""
    # Setup: DiscoveryQueue entries with suggested_recording_id
    # Execute: Backfill script
    # Assert: suggested_work_id matches recording.work_id

async def test_phase2_backfill_handles_nulls(db_session):
    """Backfill handles rows with NULL recording_id gracefully."""
    # Setup: Rows with NULL recording_id
    # Execute: Backfill script
    # Assert: work_id remains NULL, no errors

async def test_phase2_backfill_idempotency(db_session):
    """Running backfill twice produces same result."""
    # Execute: Backfill script twice
    # Assert: Data unchanged on second run

async def test_phase2_data_integrity_validation(db_session):
    """Validation queries confirm 100% data integrity."""
    # Query: Find mismatches between work_id and recording.work_id
    # Assert: Zero mismatches found

    # Query: Count rows with recording_id but no work_id
    # Assert: Zero rows found

async def test_phase2_no_data_loss(db_session):
    """Row counts unchanged after backfill."""
    # Setup: Count rows before backfill
    # Execute: Backfill script
    # Assert: Row counts identical
```

#### Phase 3: Update Application Code

**File**: `backend/tests/integration/test_migration_identity_resolution_phase3.py`

```python
async def test_phase3_api_endpoints_use_work_id(async_client, db_session):
    """API endpoints accept and return work_id."""
    # POST /discovery/link with work_id
    # Assert: Creates IdentityBridge with work_id

async def test_phase3_matcher_suggests_work_id(db_session):
    """Matcher populates suggested_work_id in DiscoveryQueue."""
    # Execute: Matcher.run_discovery()
    # Assert: DiscoveryQueue entries have suggested_work_id

async def test_phase3_resolution_service_works(db_session):
    """RecordingResolver service returns correct recordings."""
    # Execute: All 4 use cases
    # Assert: Correct recordings returned

async def test_phase3_no_regression(async_client, db_session):
    """Existing functionality still works."""
    # Execute: All existing API tests
    # Assert: All pass
```

#### Phase 4: Deprecate Old Columns

**File**: `backend/tests/alembic/test_migration_identity_resolution_phase4.py`

```python
async def test_phase4_old_columns_dropped(db_session):
    """Old recording_id columns removed from tables."""
    inspector = inspect(db_session.bind)

    identity_bridge_cols = [c['name'] for c in inspector.get_columns('identity_bridge')]
    assert 'recording_id' not in identity_bridge_cols

    broadcast_log_cols = [c['name'] for c in inspector.get_columns('broadcast_logs')]
    assert 'recording_id' not in broadcast_log_cols

    discovery_queue_cols = [c['name'] for c in inspector.get_columns('discovery_queue')]
    assert 'suggested_recording_id' not in discovery_queue_cols

async def test_phase4_no_code_references_old_columns(db_session):
    """No application code references dropped columns."""
    # This is a static analysis test - run before migration
    # Grep codebase for 'recording_id' references
    # Assert: Only in migration files and tests

async def test_phase4_all_queries_work(async_client, db_session):
    """All API endpoints work after column drop."""
    # Execute: Full API test suite
    # Assert: All tests pass
```

### Performance Tests

**File**: `backend/tests/performance/test_resolution_performance.py`

```python
class TestResolutionPerformance:
    """Performance benchmarks for resolution service."""

    async def test_resolution_speed_single_work(self, db_session, benchmark):
        """Single work resolution completes in <100ms."""
        # Setup: Work with preferences
        # Benchmark: RecordingResolver.resolve()
        # Assert: p95 < 100ms

    async def test_resolution_speed_batch_100_works(self, db_session, benchmark):
        """Batch resolution of 100 works completes in <2s."""
        # Setup: 100 works with various preferences
        # Benchmark: Batch resolution
        # Assert: Total time < 2s (20ms per work)

    async def test_policy_lookup_uses_index(self, db_session):
        """Policy lookups use database indexes."""
        # Execute: EXPLAIN query for station preference lookup
        # Assert: Query plan shows index usage

    async def test_backfill_performance_100k_logs(self, db_session, benchmark):
        """Backfill of 100k broadcast logs completes in <5 minutes."""
        # Setup: 100k BroadcastLog entries
        # Benchmark: Phase 2 backfill script
        # Assert: Completion time < 300s

    async def test_resolution_with_1000_preferences(self, db_session):
        """Resolution remains fast with large preference tables."""
        # Setup: 1000 station preferences
        # Benchmark: Resolution
        # Assert: Performance unchanged
```

### Edge Case Tests

**File**: `backend/tests/edge_cases/test_resolution_edge_cases.py`

```python
class TestResolutionEdgeCases:
    """Edge cases and error handling."""

    async def test_work_with_no_recordings(self, db_session):
        """Gracefully handles work with no recordings."""
        # Setup: Work with no recordings
        # Execute: resolve()
        # Assert: Returns None, no errors

    async def test_work_with_all_files_deleted(self, db_session):
        """Handles case where all recording files are deleted."""
        # Setup: Work with recordings but no files
        # Execute: resolve()
        # Assert: Returns None or logs warning

    async def test_station_preference_for_nonexistent_recording(self, db_session):
        """Handles invalid station preference gracefully."""
        # Setup: Station preference points to deleted recording
        # Execute: resolve()
        # Assert: Falls back to next priority level

    async def test_circular_preference_prevention(self, db_session):
        """Prevents infinite loops in preference resolution."""
        # Setup: Circular preference chain (if possible)
        # Execute: resolve()
        # Assert: Terminates with fallback

    async def test_concurrent_preference_updates(self, db_session):
        """Handles concurrent preference updates safely."""
        # Setup: Multiple threads updating same preference
        # Execute: Concurrent updates
        # Assert: No race conditions, data consistent

    async def test_orphaned_recordings_without_work(self, db_session):
        """Migration handles recordings without work_id."""
        # Setup: Recording with work_id = NULL
        # Execute: Backfill
        # Assert: Handled gracefully, logged as warning

    async def test_format_preference_with_empty_exclude_tags(self, db_session):
        """Format preference works with empty exclude_tags."""
        # Setup: FormatPreference with exclude_tags=[]
        # Execute: resolve()
        # Assert: No filtering applied

    async def test_multiple_station_preferences_same_work(self, db_session):
        """Multiple preferences for same work ordered by priority."""
        # Setup: 3 preferences with different priorities
        # Execute: resolve()
        # Assert: Lowest priority number wins
```

### Migration Validation Checklist

#### Pre-Migration Validation

**Run before each phase in production:**

```sql
-- Verify data counts
SELECT 'identity_bridge' as table_name, COUNT(*) as row_count FROM identity_bridge
UNION ALL
SELECT 'broadcast_logs', COUNT(*) FROM broadcast_logs
UNION ALL
SELECT 'discovery_queue', COUNT(*) FROM discovery_queue;

-- Verify recording → work relationships exist
SELECT COUNT(*) as orphaned_recordings
FROM recordings
WHERE work_id IS NULL;

-- Verify no duplicate signatures
SELECT log_signature, COUNT(*) as count
FROM identity_bridge
GROUP BY log_signature
HAVING COUNT(*) > 1;
```

#### Phase 1 Validation

```sql
-- Verify new columns exist and are nullable
SELECT column_name, is_nullable, data_type
FROM information_schema.columns
WHERE table_name = 'identity_bridge' AND column_name = 'work_id';

-- Verify new tables created
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('station_preferences', 'format_preferences', 'work_default_recordings');

-- Verify indexes created
SELECT indexname
FROM pg_indexes
WHERE tablename = 'station_preferences';
```

#### Phase 2 Validation

```sql
-- Verify 100% backfill for identity_bridge
SELECT
    COUNT(*) as total_rows,
    COUNT(work_id) as rows_with_work_id,
    COUNT(*) - COUNT(work_id) as rows_missing_work_id
FROM identity_bridge
WHERE recording_id IS NOT NULL;
-- Assert: rows_missing_work_id = 0

-- Verify work_id matches recording.work_id
SELECT COUNT(*) as mismatches
FROM identity_bridge ib
JOIN recordings r ON ib.recording_id = r.id
WHERE ib.work_id != r.work_id;
-- Assert: mismatches = 0

-- Verify broadcast_logs backfill
SELECT
    COUNT(*) as total_with_recording,
    COUNT(work_id) as rows_with_work_id
FROM broadcast_logs
WHERE recording_id IS NOT NULL;
-- Assert: total_with_recording = rows_with_work_id

-- Verify discovery_queue backfill
SELECT
    COUNT(*) as total_with_suggestion,
    COUNT(suggested_work_id) as rows_with_work_id
FROM discovery_queue
WHERE suggested_recording_id IS NOT NULL;
-- Assert: total_with_suggestion = rows_with_work_id
```

#### Phase 3 Validation

```sql
-- Verify new IdentityBridge entries use work_id
SELECT COUNT(*) as new_entries_without_work_id
FROM identity_bridge
WHERE created_at > NOW() - INTERVAL '1 day'
AND work_id IS NULL;
-- Assert: new_entries_without_work_id = 0

-- Verify resolution service is being used
-- (Check application logs for RecordingResolver calls)

-- Verify no new entries using old recording_id pattern
-- (Application-level check)
```

#### Phase 4 Validation

```sql
-- Verify old columns dropped
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'identity_bridge' AND column_name = 'recording_id';
-- Assert: No rows returned

-- Verify database size reduction
SELECT pg_size_pretty(pg_total_relation_size('identity_bridge')) as table_size;
-- Compare to pre-Phase 4 size
```

### Acceptance Criteria

#### Phase 1 Complete When:

- [ ] All schema changes deployed to production
- [ ] Zero downtime during deployment
- [ ] All existing tests still pass (100% pass rate)
- [ ] New columns are nullable and indexed
- [ ] New tables created with correct schema
- [ ] Backward compatibility verified (old queries work)
- [ ] Database backup created and verified

#### Phase 2 Complete When:

- [ ] Backfill script completes successfully
- [ ] 100% of eligible rows have work_id populated
- [ ] Data validation queries show 0 mismatches
- [ ] Data validation queries show 0 orphaned entries
- [ ] Row counts unchanged (no data loss)
- [ ] Idempotency verified (can run backfill again safely)
- [ ] Backfill audit log shows success
- [ ] Performance impact measured and acceptable

#### Phase 3 Complete When:

- [ ] All 4 use cases pass E2E tests
- [ ] RecordingResolver service deployed and functional
- [ ] API endpoints accept work_id in requests
- [ ] API endpoints return work_id in responses
- [ ] Matcher populates suggested_work_id
- [ ] API response times <200ms (p95)
- [ ] Zero resolution failures in production for 48 hours
- [ ] All existing tests still pass
- [ ] No regression in existing functionality

#### Phase 4 Complete When:

- [ ] Old columns dropped from all tables
- [ ] No application code references old columns
- [ ] All tests pass after column drop
- [ ] Database size reduced (old columns removed)
- [ ] Documentation updated to reflect new schema
- [ ] API documentation updated
- [ ] Zero errors in production for 1 week
- [ ] Rollback plan tested and documented (even though columns are dropped)

### Rollback Procedures

#### Phase 1 Rollback

```sql
-- Drop new columns
ALTER TABLE identity_bridge DROP COLUMN work_id;
ALTER TABLE broadcast_logs DROP COLUMN work_id;
ALTER TABLE discovery_queue DROP COLUMN suggested_work_id;

-- Drop new tables
DROP TABLE station_preferences;
DROP TABLE format_preferences;
DROP TABLE work_default_recordings;
```

**Risk**: Low - No data loss, columns were nullable and unused

#### Phase 2 Rollback

```sql
-- Clear backfilled data
UPDATE identity_bridge SET work_id = NULL;
UPDATE broadcast_logs SET work_id = NULL;
UPDATE discovery_queue SET suggested_work_id = NULL;
```

**Risk**: Low - Original recording_id data still intact

#### Phase 3 Rollback

**Application-level rollback:**
1. Redeploy previous application version
2. Old code uses recording_id (still present)
3. New work_id data remains but is unused

**Risk**: Medium - Requires application redeployment

**Validation after rollback:**
- Verify old API endpoints work
- Verify matcher uses recording_id
- Monitor for errors

#### Phase 4 Rollback

**⚠️ CRITICAL: Phase 4 is NOT easily reversible!**

**Before Phase 4, ensure:**
- [ ] Phase 3 stable for at least 2 weeks
- [ ] Zero production issues
- [ ] All stakeholders approve
- [ ] Full database backup created
- [ ] Rollback plan tested in staging

**Emergency rollback (if absolutely necessary):**
1. Restore from database backup (DATA LOSS for recent changes)
2. Redeploy Phase 3 application version
3. Re-run Phase 2 backfill for any new data

**Risk**: High - Potential data loss, significant downtime

**Mitigation**: Do NOT proceed to Phase 4 until Phase 3 is rock-solid

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Verification scope** | Per-recording (narrow) | Per-work (broad) |
| **Policy flexibility** | None | Station/format/global |
| **File resilience** | Breaks on deletion | Falls back gracefully |
| **Re-verification needed** | For any preference change | Never for preferences |
| **Version precision** | Fixed at verification | Dynamic at resolution |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data migration errors | Medium | High | Validate backfill, keep old columns during transition |
| Performance of resolution | Low | Medium | Index policy tables, cache frequent lookups |
| Policy conflicts | Low | Low | Priority field resolves conflicts deterministically |
| Breaking existing integrations | Medium | Medium | Phased rollout, maintain backward compatibility |

---

## Open Questions

1. **Should we auto-populate WorkDefaultRecording?** When a work is created with a single recording, should that become the default automatically?

2. **How do we handle the UI for setting preferences?** New admin screens needed for station/format preference management?

3. **What's the scope for Phase 1?** Should we implement the full policy engine, or just change to work_id and add the policy layer later?

---

## Appendix: Schema Responsibility Summary

| Entity | Responsibility | Links To |
|--------|----------------|----------|
| **Work** | The abstract composition (the "idea") | Artists |
| **Recording** | A specific performance/version (the "performance") | Work, LibraryFiles |
| **LibraryFile** | The physical audio file (the "bitstream") | Recording |
| **IdentityBridge** | Maps signatures to songs | Work |
| **StationPreference** | Station-specific version preferences | Station, Work, Recording |
| **FormatPreference** | Format-based version rules | Work, Recording |
| **WorkDefaultRecording** | Global fallback version | Work, Recording |
| **RecordingResolver** | Runtime resolution logic | (Service, not table) |
