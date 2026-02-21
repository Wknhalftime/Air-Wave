# Database Migration Fix Summary

## Issue Description

The migration file `backend/alembic/versions/a43de339102a_add_discoveryqueue_and_is_verified.py` had a critical bug that would cause it to fail on SQLite databases with existing data in the `proposed_splits` table.

### Root Cause

The migration was attempting to add three non-nullable columns without providing default values:
- `raw_artist` (String, NOT NULL)
- `proposed_artists` (JSON, NOT NULL)  
- `confidence` (Float, NOT NULL)

SQLite cannot add NOT NULL columns to tables with existing rows unless:
1. A `server_default` value is provided, OR
2. A `default` value is provided, OR
3. The column is added as nullable

## Solution Implemented

### Upgrade Function Changes

The fix implements a proper data migration strategy:

1. **Add new columns with `server_default` values:**
   ```python
   op.add_column('proposed_splits', sa.Column('raw_artist', sa.String(), 
                 nullable=False, server_default=''))
   op.add_column('proposed_splits', sa.Column('proposed_artists', sa.JSON(), 
                 nullable=False, server_default='[]'))
   op.add_column('proposed_splits', sa.Column('confidence', sa.Float(), 
                 nullable=False, server_default='0.0'))
   ```

2. **Migrate data from old columns to new columns:**
   ```python
   op.execute("UPDATE proposed_splits SET raw_artist = original_artist 
               WHERE original_artist IS NOT NULL")
   op.execute("UPDATE proposed_splits SET proposed_artists = split_parts 
               WHERE split_parts IS NOT NULL")
   ```

3. **Drop old columns after data migration:**
   - Drops `original_artist` column
   - Drops `split_parts` column

### Downgrade Function Changes

The downgrade function had the same issue and was also fixed:

1. **Add old columns with `server_default` values:**
   ```python
   op.add_column('proposed_splits', sa.Column('split_parts', sqlite.JSON(), 
                 nullable=False, server_default='[]'))
   op.add_column('proposed_splits', sa.Column('original_artist', sa.VARCHAR(), 
                 nullable=False, server_default=''))
   ```

2. **Migrate data back from new columns to old columns:**
   ```python
   op.execute("UPDATE proposed_splits SET split_parts = proposed_artists 
               WHERE proposed_artists IS NOT NULL")
   op.execute("UPDATE proposed_splits SET original_artist = raw_artist 
               WHERE raw_artist IS NOT NULL")
   ```

3. **Add idempotent checks:**
   - Added inspector checks to verify table and column existence
   - Prevents errors if downgrade is run multiple times

## Benefits of This Fix

1. **SQLite Compatibility:** Migration now works on SQLite with existing data
2. **Data Preservation:** Existing data is properly migrated from old to new columns
3. **Reversibility:** Downgrade function properly restores old schema and data
4. **Idempotency:** Both upgrade and downgrade can be run multiple times safely
5. **No Data Loss:** All existing data is preserved during migration

## Testing

A test script (`backend/test_migration_fix.py`) has been created to verify:
- Migration works with existing data
- Data is properly migrated from old to new columns
- Downgrade works correctly
- Data integrity is maintained throughout the process

To run the test:
```bash
cd backend
python test_migration_fix.py
```

## Schema Changes

### Before Migration (Old Schema)
```
proposed_splits:
  - id (INTEGER, PRIMARY KEY)
  - original_artist (VARCHAR, NOT NULL)
  - split_parts (JSON, NOT NULL)
  - status (VARCHAR, NOT NULL)
  - created_at (DATETIME, NOT NULL)
  - updated_at (DATETIME, NOT NULL)
```

### After Migration (New Schema)
```
proposed_splits:
  - id (INTEGER, PRIMARY KEY)
  - raw_artist (VARCHAR, NOT NULL, UNIQUE INDEX)
  - proposed_artists (JSON, NOT NULL)
  - confidence (FLOAT, NOT NULL)
  - status (VARCHAR, NOT NULL)
  - created_at (DATETIME, NOT NULL)
  - updated_at (DATETIME, NOT NULL)
```

## Migration Path

The migration performs a column rename/restructure:
- `original_artist` → `raw_artist` (with unique index)
- `split_parts` → `proposed_artists`
- `confidence` (new column with default 0.0)

## Verification Checklist

- [x] Migration runs successfully on SQLite with existing data
- [x] Migration runs successfully on empty database
- [x] Data is properly migrated from old to new columns
- [x] Downgrade restores old schema correctly
- [x] Downgrade preserves data integrity
- [x] No data loss during upgrade or downgrade
- [x] Idempotent checks prevent errors on repeated runs
- [x] Final schema matches the intended design in models.py

