# Airwave Developer Guide

## Quick Start

### Prerequisites
- Python 3.13+
- Node.js 20+
- Poetry (Python package manager)

### Setup
```bash
# Backend
cd backend
poetry install
poetry run uvicorn airwave.api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Access Points
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Admin Panel: http://localhost:5173/admin

---

## Common Development Tasks

### 1. Import Broadcast Logs
```bash
cd backend
poetry run python -m airwave.worker.main import data/sample_logs.csv
```

### 2. Scan Audio Library
```bash
poetry run python -m airwave.worker.main sync-files /path/to/music
```

### 3. Rebuild Vector Index
```bash
poetry run python -m airwave.worker.main reindex
```

### 4. Test Matching Logic
```bash
poetry run python -m airwave.worker.main debug-match "The Beatles" "Hey Jude"
```

### 5. Initialize/Reset Database
```bash
poetry run python -m airwave.worker.main init-db
```

---

## Code Style Guide

### Python (Google Style)
- **Line Length**: 80 characters (strict)
- **Docstrings**: Google format with Args, Returns, Examples
- **Type Hints**: Required for all function signatures
- **Imports**: Sorted with isort (part of ruff)

### Example Function
```python
async def match_batch(
    self, queries: List[Tuple[str, str]], explain: bool = False
) -> Dict[Tuple[str, str], Any]:
    """Efficiently matches a batch of raw artist/title pairs to recordings.

    This is the primary matching method that implements the full matching
    pipeline. It deduplicates queries, checks identity bridges, performs
    exact and fuzzy matching, and falls back to vector semantic search.

    Args:
        queries: List of (raw_artist, raw_title) tuples to match.
        explain: If True, returns detailed diagnostic information.

    Returns:
        Dictionary mapping (raw_artist, raw_title) to match results.

    Example:
        results = await matcher.match_batch([("Beatles", "Hey Jude")])
        recording_id, reason = results[("Beatles", "Hey Jude")]
    """
    # Implementation...
```

---

## Testing

### Run Tests
```bash
cd backend
poetry run pytest
```

### Run with Coverage
```bash
poetry run pytest --cov=airwave --cov-report=html
```

### Test Specific Module
```bash
poetry run pytest tests/test_matcher.py -v
```

---

## Database Migrations

### Create Migration
```bash
cd backend
poetry run alembic revision --autogenerate -m "Description"
```

### Apply Migrations
```bash
poetry run alembic upgrade head
```

### Rollback
```bash
poetry run alembic downgrade -1
```

---

## Adding New Features

### 1. Add New API Endpoint

**Step 1**: Create router function in `api/routers/`
```python
@router.get("/new-endpoint")
async def new_endpoint(db: AsyncSession = Depends(get_db)):
    """Endpoint description.
    
    Returns:
        Response data.
    """
    # Implementation
    return {"data": "result"}
```

**Step 2**: Register router in `api/main.py` (if new router file)
```python
from airwave.api.routers import new_router
app.include_router(new_router.router, prefix="/api/v1/new", tags=["New"])
```

### 2. Add New Database Model

**Step 1**: Define model in `core/models.py`
```python
class NewModel(Base, TimestampMixin):
    """Model description.
    
    Attributes:
        id: Primary key.
        name: Model name.
    """
    __tablename__ = "new_models"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
```

**Step 2**: Create migration
```bash
poetry run alembic revision --autogenerate -m "Add NewModel"
poetry run alembic upgrade head
```

### 3. Add New Worker Command

**Step 1**: Add function in `worker/main.py`
```python
async def run_new_task(arg: str) -> None:
    """New task description.
    
    Args:
        arg: Task argument.
    """
    # Implementation
    logger.info(f"Running new task with {arg}")
```

**Step 2**: Register command in `main()` function
```python
new_parser = subparsers.add_parser("new-task", help="New task description")
new_parser.add_argument("arg", help="Argument description")

# In command handler
elif args.command == "new-task":
    asyncio.run(run_new_task(args.arg))
```

---

## Performance Tips

### 1. Use Batch Operations
```python
# Good: Batch processing
results = await matcher.match_batch(queries)

# Bad: Loop with individual queries
for query in queries:
    result = await matcher.find_match(*query)
```

### 2. Leverage Vector DB Efficiently
```python
# Good: Bulk indexing
vector_db.add_tracks([(1, "artist1", "title1"), (2, "artist2", "title2")])

# Bad: Individual insertions
for track in tracks:
    vector_db.add_track(track.id, track.artist, track.title)
```

### 3. Use Async Properly
```python
# Good: Concurrent operations
results = await asyncio.gather(
    session.execute(stmt1),
    session.execute(stmt2),
)

# Bad: Sequential awaits
result1 = await session.execute(stmt1)
result2 = await session.execute(stmt2)
```

---

## Debugging

### Enable Debug Logging
```python
# In core/logger.py or set LOG_LEVEL=DEBUG
settings.LOG_LEVEL = "DEBUG"
```

### Use Match Explain Mode
```python
results = await matcher.match_batch(queries, explain=True)
for query, info in results.items():
    print(f"Match: {info['match']}")
    print(f"Candidates: {info['candidates']}")
```

### Check Database State
```bash
sqlite3 backend/data/airwave.db
.tables
SELECT * FROM recordings LIMIT 10;
```

---

## Common Issues

### Issue: "Database is locked"
**Solution**: Ensure only one writer at a time, or increase timeout in `db.py`

### Issue: "ChromaDB not found"
**Solution**: Run `poetry install` to install all dependencies

### Issue: "Import fails silently"
**Solution**: Check logs in `backend/logs/` directory

### Issue: "No matches found"
**Solution**: Run `reindex` command to rebuild vector database

