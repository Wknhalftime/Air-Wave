# Work 13176 Investigation Report

**Date:** 2026-02-19  
**Work ID:** 13176  
**Work Title:** "Once Bitten Twice Shy"  
**Artist:** Great White  
**Status:** ✅ RESOLVED - No data integrity issue found

---

## Executive Summary

**Finding:** All 3 physical audio files are correctly stored in the database and properly linked to work 13176. The work-recording grouping system is functioning as designed.

**Root Cause:** User confusion about the difference between "recordings" and "files". The UI correctly shows "1 recording" because all 3 files represent the same recording (same version, same duration).

---

## Investigation Details

### Database Query Results

```
Work ID: 13176
Work Title: once bitten twice shy
Artist ID: 1333
Artist Name: great white

Recordings: 1 total

[Recording 1]
  ID: 13217
  Title: once bitten twice shy
  Version Type: Original
  Duration: 323.8s
  Files: 3
    📁 d:/media/music/albums/various artists/hard rock cafe; 80's heavy metal/great white - once bitten twice shy.flac
    📁 d:/media/music/albums/various artists/monsters of rock/great white - once bitten twice shy.flac
    📁 d:/media/music/albums/various artists/vh-1; the big 80's big hair/great white - once bitten twice shy.flac
```

### Key Findings

1. ✅ **Work exists:** Work 13176 is properly created with correct title and artist
2. ✅ **Recording exists:** Recording 13217 is linked to work 13176
3. ✅ **All 3 files are in database:** All files are properly linked to recording 13217
4. ✅ **Work grouping is correct:** Since all 3 files have the same title, duration, and version, they correctly group under 1 recording

### Path Normalization

**Note:** File paths are stored in lowercase on Windows for case-insensitive matching:
- **Database:** `d:/media/music/albums/...`
- **User expectation:** `D:\Media\Music\Albums\...`

This is intentional behavior to ensure consistent path matching on Windows filesystems.

---

## Conceptual Clarification

### Data Model Hierarchy

```
Artist
  └── Work (abstract musical composition)
      └── Recording (specific version/performance)
          └── LibraryFile (physical audio file)
```

### Example

**Work:** "Once Bitten Twice Shy" by Great White

**Recordings:**
- Recording 1: "Original" version (323.8s)
  - File 1: VH-1 compilation album
  - File 2: Hard Rock Cafe compilation album
  - File 3: Monsters of Rock compilation album

**Why 1 recording, not 3?**

All 3 files are the **same recording** (same audio, same duration, same version) appearing on different compilation albums. They are not different versions (like "Live", "Remix", "Acoustic"), so they correctly group under 1 recording.

---

## Enhanced Debug Logging

To prevent future confusion and enable easier diagnosis of work-recording grouping issues, comprehensive debug logging has been added to the scanner.

### Configuration

Add to `.env` file:
```bash
DEBUG_WORK_GROUPING=true
```

### Log Output Examples

#### Work Matching Decisions

```
[WORK] Exact match found: work_id=13176, title='once bitten twice shy', artist_id=1333
[WORK] Fuzzy match used: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten Twice Shy', artist_id=1333
[WORK] Creating new work: title='new song title', artist_id=1333
[WORK] New work created: work_id=13177, title='new song title', artist_id=1333
```

#### Fuzzy Matching Decisions

```
[FUZZY] Match found: work_id=13176, existing_title='once bitten twice shy', new_title='Once Bitten, Twice Shy', similarity=0.957, artist_id=1333, works_compared=42
```

#### Recording Creation

```
[RECORDING] Existing recording found: recording_id=13217, work_id=13176, title='once bitten twice shy', version_type='Original'
[RECORDING] Creating new recording: work_id=13176, title='once bitten twice shy (live)', version_type='Live', duration=345.2s
[RECORDING] New recording created: recording_id=13218, work_id=13176, title='once bitten twice shy (live)', version_type='Live'
```

#### File Linking

```
[FILE] Linking file to recording: recording_id=13217, path='d:/media/music/albums/various artists/vh-1; the big 80's big hair/great white - once bitten twice shy.flac'
```

### Log Prefixes

- `[WORK]` - Work creation/matching decisions
- `[FUZZY]` - Fuzzy matching algorithm decisions
- `[RECORDING]` - Recording creation/matching decisions
- `[FILE]` - File-to-recording linking operations

---

## Recommendations

1. ✅ **No code changes needed** - Work grouping is functioning correctly
2. ✅ **Enhanced logging implemented** - Future issues will be easier to diagnose
3. 💡 **UI Enhancement (Optional):** Consider showing file count per recording in the UI
   - Current: "1 recording"
   - Proposed: "1 recording (3 files)"

---

## Conclusion

The work-recording grouping system is working as designed. All 3 files are correctly stored and linked. The confusion arose from the difference between "recordings" (versions of a work) and "files" (physical audio files). Enhanced debug logging has been implemented to make future investigations easier.

