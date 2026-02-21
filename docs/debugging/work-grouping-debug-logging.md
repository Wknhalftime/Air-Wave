# Work-Recording Grouping Debug Logging Guide

This guide explains how to use the enhanced debug logging for work-recording grouping to diagnose issues with how files are grouped into works and recordings.

---

## Quick Start

### Enable Debug Logging

Add to your `.env` file:

```bash
DEBUG_WORK_GROUPING=true
```

Or set as environment variable:

```bash
# Linux/Mac
export DEBUG_WORK_GROUPING=true

# Windows PowerShell
$env:DEBUG_WORK_GROUPING="true"

# Windows CMD
set DEBUG_WORK_GROUPING=true
```

### Run Scanner

```bash
poetry run airwave scan /path/to/music
```

---

## Log Output Reference

### Work Matching Logs

#### Exact Match Found
```
[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
```
**Meaning:** An existing work with the exact same title and artist was found. The file will be grouped under this work.

#### Fuzzy Match Used
```
[WORK] Fuzzy match used: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten Twice Shy', artist_id=1333
```
**Meaning:** No exact match found, but a similar work was found using fuzzy matching (85% similarity threshold). The file will be grouped under the existing work.

#### New Work Created
```
[WORK] Creating new work: title='new song title', artist_id=1333
[WORK] New work created: work_id=13177, title='new song title', artist_id=1333
```
**Meaning:** No exact or fuzzy match found. A new work was created.

#### Race Condition Resolved
```
[WORK] Race condition resolved: work_id=13176, title='once bitten twice shy', artist_id=1333
```
**Meaning:** Another thread created the work while this thread was trying to create it. The existing work was retrieved.

---

### Fuzzy Matching Logs

#### Fuzzy Match Found
```
[FUZZY] Match found: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten, Twice Shy', similarity=0.957, artist_id=1333, works_compared=42
```

**Fields:**
- `work_id`: ID of the matched work
- `existing_title`: Title of the existing work in database
- `new_title`: Title from the file being scanned
- `similarity`: Similarity score (0.0 to 1.0, threshold is 0.85)
- `artist_id`: Artist ID
- `works_compared`: Number of works compared during fuzzy matching

**Meaning:** Fuzzy matching algorithm found a similar work. Shows the similarity score and how many works were compared.

---

### Recording Matching Logs

#### Existing Recording Found
```
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten twice shy', version_type='Original'
```
**Meaning:** An existing recording with the same title and work was found. The file will be linked to this recording.

#### New Recording Created
```
[RECORDING] Creating new recording: work_id=13176, title='once bitten twice shy (live)', version_type='Live', duration=345.2s
[RECORDING] New recording created: recording_id=13218, work_id=13176, title='once bitten twice shy (live)', version_type='Live'
```
**Meaning:** No existing recording found. A new recording was created under the work.

#### Race Condition Resolved
```
[RECORDING] Race condition resolved: recording_id=13217, work_id=13176, title='once bitten twice shy'
```
**Meaning:** Another thread created the recording while this thread was trying to create it. The existing recording was retrieved.

---

### File Linking Logs

#### File Linked to Recording
```
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/albums/various artists/vh-1; the big 80's big hair/great white - once bitten twice shy.flac'
```
**Meaning:** A physical audio file is being linked to a recording.

---

## Common Scenarios

### Scenario 1: Multiple Files Grouped Under Same Recording

**Expected Logs:**
```
[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten twice shy', version_type='Original'
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/.../file1.flac'

[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten twice shy', version_type='Original'
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/.../file2.flac'
```

**Interpretation:** Both files have the same title and version, so they correctly group under the same recording.

---

### Scenario 2: Different Versions Create Separate Recordings

**Expected Logs:**
```
[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten twice shy', version_type='Original'
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/.../original.flac'

[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
[RECORDING] Creating new recording: work_id=13176, title='once bitten twice shy (live)', version_type='Live', duration=345.2s
[RECORDING] New recording created: recording_id=13218, work_id=13176, title='once bitten twice shy (live)', version_type='Live'
[FILE] Linking file to recording: recording_id=13218, path='d:/media/music/.../live.flac'
```

**Interpretation:** The live version creates a separate recording under the same work.

---

### Scenario 3: Fuzzy Matching Groups Similar Titles

**Expected Logs:**
```
[WORK] Fuzzy match used: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten, Twice Shy', artist_id=1333
[FUZZY] Match found: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten, Twice Shy', similarity=0.957, artist_id=1333, works_compared=42
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten, twice shy', version_type='Original'
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/.../file.flac'
```

**Interpretation:** The file has slightly different punctuation/capitalization, but fuzzy matching (95.7% similarity) groups it under the existing work.

---

## Troubleshooting

### Issue: Files Not Grouping Together

**Check logs for:**
1. Are they matching the same work? Look for `work_id` values
2. Are they matching the same recording? Look for `recording_id` values
3. Is fuzzy matching being used? Look for `[FUZZY]` logs
4. What are the similarity scores? Should be >= 0.85

### Issue: Too Many Works Created

**Check logs for:**
1. Are fuzzy matches being found? If not, titles may be too different
2. What are the similarity scores? May need to adjust `WORK_FUZZY_MATCH_THRESHOLD`
3. Is the artist catalog too large? Check `works_compared` - if > 500, fuzzy matching is skipped

### Issue: Files Grouped Incorrectly

**Check logs for:**
1. What similarity score caused the fuzzy match? May be too low
2. Are part numbers being detected? Look for different part numbers in titles
3. Are version types being extracted correctly? Check `version_type` values

---

## Configuration Options

### `DEBUG_WORK_GROUPING`
- **Type:** Boolean
- **Default:** `false`
- **Description:** Enable verbose logging for work-recording grouping

### `WORK_FUZZY_MATCH_THRESHOLD`
- **Type:** Float (0.0 to 1.0)
- **Default:** `0.85`
- **Description:** Minimum similarity score for fuzzy matching (85%)

### `WORK_FUZZY_MATCH_MAX_WORKS`
- **Type:** Integer
- **Default:** `500`
- **Description:** Maximum number of works to compare for fuzzy matching. If an artist has more works than this, fuzzy matching is skipped for performance.

---

## Performance Impact

**Debug logging has minimal performance impact:**
- Logs are only written when `DEBUG_WORK_GROUPING=true`
- No additional database queries are performed
- String formatting is only done when logging is enabled

**Recommendation:** Enable debug logging only when diagnosing issues, not in production.

