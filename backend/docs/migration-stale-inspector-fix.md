# Migration Fix: Stale Inspector Bug in proposed_splits Data Migration

## Issue Summary

**File**: `backend/alembic/versions/a43de339102a_add_discoveryqueue_and_is_verified.py`  
**Lines**: 214, 216 (upgrade), 254, 256 (downgrade)  
**Severity**: **CRITICAL** - Data loss bug

### Problem Description

The migration had a logic error where it checked if newly added columns existed using a stale `Inspector` instance that was created before the columns were added. This caused the data migration UPDATE statements to never execute, resulting in data loss when upgrading existing databases.

### Root Cause

```python
# Inspector created at the beginning of the migration
inspector = Inspector.from_engine(conn)  # Line 27

# ... later in the code ...

# Add new columns
op.add_column('proposed_splits', sa.Column('raw_artist', ...))  # Line 207
op.add_column('proposed_splits', sa.Column('proposed_artists', ...))  # Line 209

# BUG: Check if newly added columns exist using STALE inspector
if 'original_artist' in proposed_splits_columns and 'raw_artist' in {col['name'] for col in inspector.get_columns('proposed_splits')}:
    op.execute("UPDATE proposed_splits SET raw_artist = original_artist ...")  # Line 215
```

**The Problem**: The `inspector` was created before the columns were added, so `inspector.get_columns()` returns a snapshot of the schema from before the migration. The newly added columns will never be found, so the UPDATE statements never execute.

### Impact

- **Existing databases**: Data from `original_artist` and `split_parts` columns would NOT be migrated to `raw_artist` and `proposed_artists` columns
- **Fresh installations**: No impact (no data to migrate)
- **Data loss**: Yes - existing data would be lost when old columns are dropped

## Fix Applied

### Changes Made

**Upgrade function (lines 213-218)**:
```python
# BEFORE (BUGGY):
if 'original_artist' in proposed_splits_columns and 'raw_artist' in {col['name'] for col in inspector.get_columns('proposed_splits')}:
    op.execute("UPDATE proposed_splits SET raw_artist = original_artist WHERE original_artist IS NOT NULL")

# AFTER (FIXED):
# Migrate data from old columns to new columns (only if old columns exist)
# Note: We just added the new columns above, so they definitely exist now
if 'original_artist' in proposed_splits_columns:
    op.execute("UPDATE proposed_splits SET raw_artist = original_artist WHERE original_artist IS NOT NULL")
```

**Downgrade function (lines 254-259)**:
```python
# BEFORE (BUGGY):
if 'proposed_artists' in proposed_splits_columns and 'split_parts' in {col['name'] for col in inspector.get_columns('proposed_splits')}:
    op.execute("UPDATE proposed_splits SET split_parts = proposed_artists WHERE proposed_artists IS NOT NULL")

# AFTER (FIXED):
# Migrate data from new columns back to old columns (only if new columns exist)
# Note: We just added the old columns above, so they definitely exist now
if 'proposed_artists' in proposed_splits_columns:
    op.execute("UPDATE proposed_splits SET split_parts = proposed_artists WHERE proposed_artists IS NOT NULL")
```

### Rationale

Since we just added the new columns ourselves in the previous lines, we **know** they exist. We only need to check if the OLD columns exist (to determine if there's data to migrate). The redundant check for newly added columns was not only unnecessary but also incorrect due to the stale inspector.

## Testing

### Test Coverage

Created comprehensive tests in `backend/tests/alembic/test_migration_proposed_splits.py`:

1. **`test_migration_proposed_splits_data_migration_upgrade`**:
   - Starts with old schema (original_artist, split_parts)
   - Inserts test data
   - Runs upgrade migration
   - Verifies new schema (raw_artist, proposed_artists, confidence)
   - **Verifies data was migrated correctly** ✅

2. **`test_migration_proposed_splits_data_migration_downgrade`**:
   - Starts with new schema (raw_artist, proposed_artists, confidence)
   - Inserts test data
   - Runs downgrade migration
   - Verifies old schema (original_artist, split_parts)
   - **Verifies data was migrated back correctly** ✅

### Test Results

```
tests/alembic/test_migration_proposed_splits.py::test_migration_proposed_splits_data_migration_upgrade PASSED
tests/alembic/test_migration_proposed_splits.py::test_migration_proposed_splits_data_migration_downgrade PASSED

2 passed, 11 warnings in 0.26s
```

## Verification Checklist

- [x] Bug identified and root cause understood
- [x] Fix applied to both upgrade() and downgrade() functions
- [x] Comprehensive tests added
- [x] Tests pass for both upgrade and downgrade scenarios
- [x] Data migration verified to work correctly
- [x] No data loss during upgrade or downgrade
- [x] Fresh database installations still work (no old columns to migrate)
- [x] Existing database upgrades now work correctly (data is migrated)

## Related Files

- **Migration file**: `backend/alembic/versions/a43de339102a_add_discoveryqueue_and_is_verified.py`
- **Test file**: `backend/tests/alembic/test_migration_proposed_splits.py`
- **Model file**: `backend/src/airwave/core/models.py` (ProposedSplit model)

## Lessons Learned

1. **Inspector snapshots are immutable**: Once created, an Inspector instance provides a snapshot of the schema at that point in time. It does NOT reflect subsequent schema changes.

2. **Avoid redundant checks**: If you just added a column, you don't need to check if it exists. Only check for columns that might or might not exist (e.g., old columns in an upgrade scenario).

3. **Test data migrations**: Always test migrations with actual data to ensure data is preserved during schema changes.

4. **Idempotent migrations**: While idempotency is important, be careful not to introduce bugs when adding existence checks.

