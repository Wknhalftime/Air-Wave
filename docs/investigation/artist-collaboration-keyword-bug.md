# Investigation: Artist Collaboration Keywords Not Removed

**Date:** 2026-02-19  
**Example:** Artist ID 9 ("2pac") vs Artist ID 2202 ("2pac duet") — duplicates

## Summary

Collaboration keywords like "duet", "feat.", "ft.", "vs." were not in the separator list for `split_artists()` and were not stripped by `clean_artist()`. This caused artist names such as "2pac duet" to be stored instead of "2pac", creating duplicate artist records.

## Root Cause

1. **split_artists()** — "duet" and "vs" were missing from the separators list. For "2pac duet", the string was not split, so "duet" remained in the result.

2. **clean_artist()** — No step removed collaboration keyword suffixes. Unlike `clean()` (which strips "feat." and similar from titles), `clean_artist()` did not strip these from artist names.

## Fix Applied

### 1. clean_artist()

Added step 5 to strip collaboration keyword suffixes and anything after them:

```python
text = re.sub(
    r"\s+\b(duet|feat\.?|ft\.?|f\.?|featuring|vs\.?)\b\s*.*$",
    "",
    text,
    flags=re.IGNORECASE,
)
```

Word boundaries (`\b`) prevent partial matches (e.g. "feature" in "Feature Artist").

### 2. split_artists()

Added separators:

- `r"\s+duet\s+with\s+"` — "Artist A duet with Artist B"
- `r"\s+duet\s+"` — "2pac duet" or "Artist A duet Artist B"
- `r"\s+vs\.?\s+"` — "Artist A vs Artist B"

## Finding Affected Artists

Run this SQL against the database to find artist names containing collaboration keywords:

```sql
SELECT id, name FROM artists
WHERE name LIKE '%duet%'
   OR name LIKE '% feat%'
   OR name LIKE '% ft%'
   OR name LIKE '% feat. %'
   OR name LIKE '% ft. %'
   OR name LIKE '%featuring%'
   OR name ILIKE '% vs %'
   OR name ILIKE '% vs. %'
   OR name LIKE '% and %'  -- may include false positives (e.g. "Simon and Garfunkel")
ORDER BY name;
```

To find duplicates that can be merged (same base name with/without keyword):

```sql
-- Example: find "2pac duet" when "2pac" exists
WITH normalized AS (
  SELECT id, name,
    TRIM(REGEXP_REPLACE(
      REGEXP_REPLACE(LOWER(name), '\s+(duet|feat\.?|ft\.?|featuring|vs\.?)\s*.*$', '', 'i'),
      '^\s*(the|a|an)\s+', '', 'i'
    )) AS base_name
  FROM artists
)
SELECT n1.id, n1.name, n2.id AS canonical_id, n2.name AS canonical_name
FROM normalized n1
JOIN normalized n2 ON n1.base_name = n2.name AND n1.id != n2.id
WHERE n1.name != n1.base_name;
```

(SQLite does not support `REGEXP_REPLACE` by default; use a script or manual review for SQLite.)

## Merging Duplicates

Use the admin merge endpoint:

```bash
# Merge "2pac duet" (2202) into "2pac" (9)
curl -X POST "http://localhost:8000/api/v1/admin/artists/merge" \
  -H "Content-Type: application/json" \
  -d '{"source_artist_id": 2202, "target_artist_id": 9}'
```

## Re-scan Consideration

A full re-scan will create new artists with corrected names. Existing records with bad names will remain until merged. Options:

1. **Manual merge** — Run the query above, then merge each duplicate pair.
2. **Migration script** — Batch-update artist names and merge duplicates (more complex).
3. **Accept existing data** — Fix applied for future scans; manually fix only critical duplicates.
