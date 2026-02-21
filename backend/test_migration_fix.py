"""
Test script to verify the migration fix works correctly with existing data.

This script:
1. Creates a test database with the old schema
2. Inserts test data
3. Runs the migration
4. Verifies data integrity
5. Tests downgrade
"""

import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text, inspect
from alembic.config import Config
from alembic import command


def test_migration_with_existing_data():
    """Test that the migration handles existing data correctly."""
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create database URL
        db_url = f'sqlite:///{db_path}'
        engine = create_engine(db_url)
        
        print(f"Created test database: {db_path}")
        
        # Create the old schema (before migration)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE proposed_splits (
                    id INTEGER PRIMARY KEY,
                    original_artist VARCHAR NOT NULL,
                    split_parts JSON NOT NULL,
                    status VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            conn.commit()
            
            # Insert test data
            conn.execute(text("""
                INSERT INTO proposed_splits 
                (id, original_artist, split_parts, status, created_at, updated_at)
                VALUES 
                (1, 'Artist A / Artist B', '["Artist A", "Artist B"]', 'PENDING', datetime('now'), datetime('now')),
                (2, 'Artist C feat. Artist D', '["Artist C", "Artist D"]', 'APPROVED', datetime('now'), datetime('now'))
            """))
            conn.commit()
            
            print("✓ Created old schema and inserted test data")
            
            # Verify old data
            result = conn.execute(text("SELECT id, original_artist, split_parts, status FROM proposed_splits"))
            rows = result.fetchall()
            print(f"✓ Old data: {len(rows)} rows")
            for row in rows:
                print(f"  - ID {row[0]}: {row[1]} -> {row[2]} ({row[3]})")
        
        # Now run the migration
        print("\n--- Running Migration ---")
        
        # Configure Alembic - use absolute path for script_location
        _script_dir = Path(__file__).resolve().parent
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', str(_script_dir / 'alembic'))
        alembic_cfg.set_main_option('sqlalchemy.url', db_url)
        
        # Run upgrade to the specific revision
        try:
            command.upgrade(alembic_cfg, 'a43de339102a')
            print("✓ Migration upgrade completed")
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            raise
        
        # Verify new schema and data
        with engine.connect() as conn:
            inspector = inspect(engine)
            columns = {col['name'] for col in inspector.get_columns('proposed_splits')}
            
            print(f"\n✓ New schema columns: {columns}")
            
            # Check that new columns exist
            assert 'raw_artist' in columns, "raw_artist column missing"
            assert 'proposed_artists' in columns, "proposed_artists column missing"
            assert 'confidence' in columns, "confidence column missing"
            
            # Check that old columns are gone
            assert 'original_artist' not in columns, "original_artist column should be dropped"
            assert 'split_parts' not in columns, "split_parts column should be dropped"
            
            print("✓ Schema migration successful")
            
            # Verify data was migrated
            result = conn.execute(text("SELECT id, raw_artist, proposed_artists, confidence, status FROM proposed_splits"))
            rows = result.fetchall()
            print(f"\n✓ Migrated data: {len(rows)} rows")
            for row in rows:
                print(f"  - ID {row[0]}: {row[1]} -> {row[2]} (confidence: {row[3]}, status: {row[4]})")
            
            # Verify data integrity
            assert len(rows) == 2, "Should have 2 rows"
            assert rows[0][1] == 'Artist A / Artist B', "Data migration failed for row 1"
            assert rows[1][1] == 'Artist C feat. Artist D', "Data migration failed for row 2"
            
            print("✓ Data integrity verified")
        
        # Test downgrade
        print("\n--- Testing Downgrade ---")
        try:
            command.downgrade(alembic_cfg, '-1')
            print("✓ Migration downgrade completed")
        except Exception as e:
            print(f"✗ Downgrade failed: {e}")
            raise
        
        # Verify downgrade restored old schema
        with engine.connect() as conn:
            inspector = inspect(engine)
            columns = {col['name'] for col in inspector.get_columns('proposed_splits')}
            
            print(f"\n✓ Downgraded schema columns: {columns}")
            
            # Check that old columns are back
            assert 'original_artist' in columns, "original_artist column missing after downgrade"
            assert 'split_parts' in columns, "split_parts column missing after downgrade"
            
            # Check that new columns are gone
            assert 'raw_artist' not in columns, "raw_artist column should be dropped after downgrade"
            assert 'proposed_artists' not in columns, "proposed_artists column should be dropped after downgrade"
            assert 'confidence' not in columns, "confidence column should be dropped after downgrade"
            
            print("✓ Downgrade schema verified")
            
            # Verify data was migrated back
            result = conn.execute(text("SELECT id, original_artist, split_parts, status FROM proposed_splits"))
            rows = result.fetchall()
            print(f"\n✓ Downgraded data: {len(rows)} rows")
            for row in rows:
                print(f"  - ID {row[0]}: {row[1]} -> {row[2]} ({row[3]})")
            
            assert len(rows) == 2, "Should have 2 rows after downgrade"
            print("✓ Downgrade data integrity verified")
        
        print("\n" + "="*50)
        print("✓ ALL TESTS PASSED!")
        print("="*50)

    finally:
        # Ensure engine releases the DB file before cleanup (required on Windows)
        engine.dispose()
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
                print(f"\nCleaned up test database: {db_path}")
            except PermissionError:
                pass  # Ignore if file still locked


if __name__ == '__main__':
    test_migration_with_existing_data()

