# Library Navigation User Guide

This guide explains how to navigate your music library using the three-level hierarchy: **Artist → Work → Recording**.

## Overview

Airwave organizes your music collection in a hierarchical structure:

```
Artists (e.g., "Queen")
  └── Works (e.g., "Bohemian Rhapsody")
      └── Recordings (e.g., "Studio Version", "Live at Wembley")
```

This structure allows you to:
- Browse all artists in your library
- View all songs/compositions by a specific artist
- See all versions (studio, live, remixes) of a specific song

---

## Navigating the Library

### 1. Library Page

The main library page shows all artists in your collection as a grid of cards.

**Features:**
- **Artist Cards:** Display artist name, avatar (first letter), work count, and recording count
- **Search:** Filter artists by name (coming soon)
- **Sorting:** Sort by name, work count, or recording count (coming soon)

**How to Use:**
1. Navigate to the Library page from the main menu
2. Browse the artist grid
3. Click on any artist card to view their works

---

### 2. Artist Detail Page

The artist detail page shows all works by a specific artist.

**Features:**
- **Breadcrumb Navigation:** Library → Artist Name
- **Artist Header:** Shows artist name, avatar, work count, and recording count
- **Work Grid:** Displays all works as cards (3 columns)
- **Pagination:** Navigate through pages of works (24 per page)

**Work Card Information:**
- Work title
- All artist names (for collaborations)
- Number of recordings
- Total duration across all recordings
- Year of first recording (if available)

**How to Use:**
1. Click on an artist card from the Library page
2. Browse the work grid
3. Use pagination controls to view more works
4. Click on any work card to view its recordings

**Example:**

```
Library → Queen

Queen
Work Count: 156 | Recording Count: 423

┌─────────────────────┬─────────────────────┬─────────────────────┐
│ Bohemian Rhapsody   │ We Will Rock You    │ Under Pressure      │
│ Queen               │ Queen               │ Queen, David Bowie  │
│ 5 recordings        │ 3 recordings        │ 3 recordings        │
│ 29m 30s | 1975      │ 6m 12s | 1977       │ 12m 24s | 1981      │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

---

### 3. Work Detail Page

The work detail page shows all recordings of a specific work.

**Features:**
- **Breadcrumb Navigation:** Library → Artist Name → Work Title
- **Work Header:** Shows work title, artist names, and recording count
- **Filter Controls:** Filter recordings by status and source
- **Recording Table:** Displays all recordings with details
- **Pagination:** Navigate through pages of recordings (100 per page)

**Recording Table Columns:**
- **Title:** Recording title (may include version info)
- **Artist:** Artist name for display
- **Duration:** Recording length in minutes:seconds
- **Version:** Version type (Studio, Live, Remix, etc.)
- **Status:** Matched (✓) or Unmatched (-)
- **Source:** Library (file icon) or Metadata (database icon)

**Filter Options:**

**Status Filter:**
- **All:** Show all recordings
- **Matched:** Show only verified/matched recordings
- **Unmatched:** Show only unverified recordings

**Source Filter:**
- **All:** Show all recordings
- **Library:** Show only recordings with library files
- **Metadata:** Show only metadata-only recordings (no files)

**How to Use:**
1. Click on a work card from the Artist Detail page
2. Use the filter dropdowns to narrow down recordings
3. Click "Clear filters" to reset all filters
4. Use pagination controls to view more recordings
5. Click on a recording to play it (coming soon)

**Example:**

```
Library → Queen → Bohemian Rhapsody

Bohemian Rhapsody
by Queen
5 recordings

Filters: [Status: All ▼] [Source: All ▼] [Clear filters]

┌──────────────────────────────────┬────────┬──────────┬─────────┬────────┬────────┐
│ Title                            │ Artist │ Duration │ Version │ Status │ Source │
├──────────────────────────────────┼────────┼──────────┼─────────┼────────┼────────┤
│ Bohemian Rhapsody                │ Queen  │ 5:54     │ Studio  │   ✓    │   📁   │
│ Bohemian Rhapsody (Live)         │ Queen  │ 6:00     │ Live    │   ✓    │   📁   │
│ Bohemian Rhapsody (Remastered)   │ Queen  │ 5:55     │ Studio  │   ✓    │   📁   │
│ Bohemian Rhapsody (Live Wembley) │ Queen  │ 6:12     │ Live    │   ✓    │   💾   │
│ Bohemian Rhapsody (Remix)        │ Queen  │ 5:50     │ Remix   │   -    │   💾   │
└──────────────────────────────────┴────────┴──────────┴─────────┴────────┴────────┘

Page 1 | Showing 1-5 of 5 recordings
```

---

## Understanding Recording Status

### Matched (Verified)
- The recording has been matched to a MusicBrainz entry
- Metadata is verified and accurate
- Indicated by a green checkmark (✓)

### Unmatched (Unverified)
- The recording has not been matched to MusicBrainz
- Metadata may be incomplete or inaccurate
- Indicated by a gray dash (-)

---

## Understanding Recording Sources

### Library Files
- The recording has an associated audio file in your library
- You can play this recording
- Indicated by a folder icon (📁)

### Metadata Only
- The recording exists in the MusicBrainz database but not in your library
- You cannot play this recording (no file)
- Indicated by a database icon (💾)
- Useful for discovering missing recordings

---

## Common Use Cases

### Finding All Versions of a Song

1. Navigate to the artist (e.g., "Queen")
2. Find the work (e.g., "Bohemian Rhapsody")
3. Click on the work card
4. View all recordings (studio, live, remixes, etc.)

### Finding Missing Recordings

1. Navigate to a work detail page
2. Set **Source** filter to "Metadata"
3. View recordings that exist in MusicBrainz but not in your library
4. Use this list to find and add missing recordings

### Viewing Only Your Library Files

1. Navigate to a work detail page
2. Set **Source** filter to "Library"
3. View only recordings you have files for

### Finding Unverified Recordings

1. Navigate to a work detail page
2. Set **Status** filter to "Unmatched"
3. View recordings that need manual verification
4. Use this to improve metadata quality

---

## Tips and Tricks

### Multi-Artist Works

Collaborative works (e.g., "Under Pressure" by Queen and David Bowie) appear on all participating artists' pages:
- Navigate to "Queen" → see "Under Pressure" (Queen, David Bowie)
- Navigate to "David Bowie" → see "Under Pressure" (Queen, David Bowie)

### Pagination

- Artist detail pages show 24 works per page (3 columns × 8 rows)
- Work detail pages show 100 recordings per page
- Use Previous/Next buttons to navigate
- Page numbers are displayed in the center

### Performance

- All pages use caching for fast loading
- First load may be slower, subsequent loads are instant
- Cache refreshes automatically every few minutes

---

## Keyboard Shortcuts (Coming Soon)

- `←` / `→` - Navigate between pages
- `/` - Focus search box
- `Esc` - Clear filters
- `Enter` - Play selected recording

---

## See Also

- [API Documentation](../api/library-navigation.md) - For developers
- [Architecture](../architecture/caching.md) - How caching works
- [FAQ](../faq.md) - Frequently asked questions

