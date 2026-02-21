# Investigation: 10,000 Maniacs Artist Database Issues

**Date:** 2026-02-19  
**Artist IDs:** 2064 (correct "10000 maniacs"), 2065 (incorrect "000 Maniacs")

## Summary

Two related issues affect the artist "10,000 Maniacs":

1. **Duplicate artist entry** – Artist 2065 ("000 Maniacs") was created due to `split_artists()` treating the comma in "10,000" as an artist separator.
2. **Artist page display problem** – Artist 2064 shows 4 works/4 recordings in metadata but the works list is empty because works are linked via `work_artists` to 2065, not 2064.

---

## Issue 1: Root Cause of Duplicate Artist

### Root Cause

`Normalizer.split_artists()` uses `r",\s*"` as a collaboration separator. For "10,000 Maniacs":

- The string is split on the comma → `["10", "000 Maniacs"]`
- Each part is normalized: `["10", "000 maniacs"]`
- Two artists are created and linked to works: "10" and "000 maniacs" (ID 2065)

Meanwhile, the **primary artist** comes from `clean_artist("10,000 Maniacs")` → `"10000 maniacs"` (ID 2064), because `clean_artist()` removes punctuation (including commas) before matching.

### Data Flow

| Step | Source | Result |
|------|--------|--------|
| Primary artist | `meta.artist` = `clean_artist("10,000 Maniacs")` | "10000 maniacs" → Artist 2064 |
| Work.artist_id | Set from primary artist | 2064 |
| work_artists | `split_artists("10,000 Maniacs")` → ["10", "000 maniacs"] | Links to "10" and "000 maniacs" (2065), **not** 2064 |

### Code References

- `backend/src/airwave/core/normalization.py` – `split_artists()` line 344: `r",\s*"`
- `backend/src/airwave/worker/scanner.py` – `_link_multi_artists()` line 1676: calls `split_artists(raw)`

### Fix

Use a regex that does **not** split on commas used as thousands separators (between digits):

```python
# OLD
r",\s*",

# NEW - don't split when comma is between digits (e.g. "10,000")
r"(?<!\d),\s*(?!\d)",
```

This keeps "10,000 Maniacs" as one artist, while still splitting "Artist A, Artist B" or "Smith, John".

---

## Issue 2: Why Artist Page Shows No Works

### Root Cause

- **Header counts** come from `get_artist()` → `Artist.primary_works` → `Work.artist_id == 2064` → 4 works.
- **Works list** comes from `list_artist_works()` → `WorkArtist.artist_id == 2064` → 0 rows.

The works have `Work.artist_id = 2064`, but `work_artists` links them to 2065 ("000 maniacs") and possibly artist "10", not to 2064. So the header shows the correct count, but the list endpoint returns nothing.

### Code References

- `library.py:84-92` – `get_artist()` uses `Artist.primary_works` (Work.artist_id)
- `library.py:144-159` – `list_artist_works()` uses `WorkArtist.artist_id`

### Resolution

After merging artist 2065 into 2064, `work_artists` rows are updated so all works are linked to 2064, and the display bug is resolved.

---

## Issue 3: Merge Strategy

The admin API already provides an artist merge endpoint:

- **Endpoint:** `POST /api/v1/admin/artists/merge`
- **Body:** `{"source_artist_id": 2065, "target_artist_id": 2064}`

Merge behavior:

1. Repoint `Work.artist_id` from 2065 → 2064 (if any)
2. Repoint `Album.artist_id` from 2065 → 2064 (if any)
3. For each `WorkArtist` row with artist_id=2065:
   - If (work_id, 2064) already exists → delete the 2065 row
   - Otherwise → update artist_id 2065 → 2064
4. Delete artist 2065

After the merge, artist 2064 will have the correct works in both `Work.artist_id` and `work_artists`.

---

## Issue 4: Other Artists Affected

Any artist name containing a comma used as a thousands separator (e.g. "10,000 Maniacs", "1,000 Clowns") would be mis-split. The normalization fix above prevents this going forward.

A one-off audit for existing duplicates would be:

```sql
-- Artists whose names look like number fragments from comma-split
SELECT * FROM artists WHERE name ~ '^\d+$' OR name ~ '^\d+\s+\w+';
```

---

## Action Items

1. **Normalization fix** – DONE: Updated `split_artists()` to use `(?<!\d),\s*(?!\d)` so commas in numbers (e.g. "10,000") are not treated as separators.
2. **Merge artists** – Run the merge API (see below).
3. **Clear cache** – Clear or invalidate cache for artist 2064 if the backend uses caching.
4. **Test** – DONE: Added `test_split_artists_preserves_numeric_commas()`.

### Merge Command

With the backend running and admin auth configured:

```bash
curl -X POST "http://localhost:8000/api/v1/admin/artists/merge" \
  -H "Content-Type: application/json" \
  -d '{"source_artist_id": 2065, "target_artist_id": 2064}'
```

Or using PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/artists/merge" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"source_artist_id": 2065, "target_artist_id": 2064}'
```

This merges "000 Maniacs" (2065) into "10000 maniacs" (2064), repointing all WorkArtist rows so the artist page displays the 4 works correctly.
