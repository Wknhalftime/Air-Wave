# Airwave - Changelog

All notable changes, fixes, and improvements to the Airwave project.

---

## [2026-02-20] - Recent Improvements

### Added

#### Artist Linking Decoupling
- **Changed data source** from `DiscoveryQueue` to `BroadcastLog` for artist linking
- **Added filter_type parameter** to `/artist-queue` endpoint (all/matched/unmatched)
- **Enables proactive alias creation** - can create aliases before songs fail to match
- **Separation of concerns** - artist identity is now independent of song matching

**Impact:**
- Users can normalize artist names across entire dataset
- No longer limited to unmatched songs only
- Better data quality and consistency

**Files Changed:**
- `backend/src/airwave/api/routers/discovery.py`

**Documentation:**
- `docs/artist-linking-decoupling-fix.md`

---

#### Rematch Batching Optimization
- **Refactored `rematch_items_for_artist`** to use batching instead of one-at-a-time processing
- **Batch size: 500 items** (same as initial discovery)
- **10x performance improvement** - from ~50-100 sec to ~5-10 sec for 1000 items
- **300x fewer database queries** - from ~1000 to ~2-3
- **500x fewer vector searches** - from ~1000 to ~2

**Impact:**
- Re-matching after artist linking is now as fast as initial discovery
- Better user experience when linking artists
- Reduced database and vector search load

**Files Changed:**
- `backend/src/airwave/api/routers/discovery.py`

**Documentation:**
- `docs/rematch-batching-optimization.md`

---

### Fixed

#### Match Tuner Stratified Sampling Fixes
- **Fixed inconsistent category logic** between first pass and stratified sampling
- **Fixed incorrect threshold comparison** - was using artist_auto for both artist and title
- **Fixed too restrictive "near" ranges** - now includes ALL matches in each category
- **Increased sample size** from 500 to 1,000 logs for better coverage

**Impact:**
- Match Tuner now shows 10-15 examples per category (auto/review/reject)
- Examples are representative of the entire range, not just edge cases
- Users can see concrete examples of what each threshold setting means

**Files Changed:**
- `backend/src/airwave/api/routers/admin.py`

**Documentation:**
- `docs/match-tuner-stratified-sampling-fixes.md`

---

## [2026-02-19] - Match Tuner UX Improvements

### Added

#### Phase 4: 2D Visualization
- **Interactive scatter plot** using Recharts
- **Color-coded dots** by category (blue/green/yellow/red)
- **Threshold lines** (horizontal for artist, vertical for title)
- **Hover tooltips** with match details
- **Click-to-inspect** functionality
- **View toggle** between List View and 2D View

**Impact:**
- Advanced users can visualize the 2D decision space
- Understand how artist/title thresholds interact
- See clustering patterns and outliers

**Files Changed:**
- `frontend/src/components/admin/MatchScatterPlot.tsx` (new)
- `frontend/src/pages/admin/MatchTuner.tsx`

**Documentation:**
- `docs/phase4-2d-visualization-complete.md`

---

#### Phase 3: Edge Case Highlighting
- **Edge case detection** - matches within 5% of any threshold boundary
- **Amber warning boxes** on edge case matches
- **Edge case counter** in header
- **Helper text** explaining edge case significance

**Impact:**
- Users can see which matches are at risk of changing category
- Helps avoid accidentally excluding good matches
- Better informed threshold decisions

**Files Changed:**
- `backend/src/airwave/api/routers/admin.py`
- `frontend/src/components/admin/ExampleMatches.tsx`

**Documentation:**
- `docs/phase3-edge-case-highlighting-complete.md`

---

#### Phase 2: Impact Visibility
- **Impact summary cards** showing auto/review/reject counts
- **Real-time updates** when thresholds change
- **Statistical sampling** (1,000 logs) for ±3% accuracy
- **Performance optimized** to 3-5 seconds

**Impact:**
- Users know exactly how many matches will be affected
- Can make informed decisions about threshold changes
- Fast enough for real-time feedback

**Files Changed:**
- `backend/src/airwave/api/routers/admin.py`
- `frontend/src/components/admin/ExampleMatches.tsx`

**Documentation:**
- `docs/phase2-example-matches-complete.md`

---

#### Phase 1: Foundation (MVP)
- **Match example cards** with full score visibility
- **Similarity scores** (artist, title, vector)
- **Category badges** (Auto/Review/Reject/Identity Bridge)
- **Quality warnings** (truncation, length mismatch, extra text, case only)

**Impact:**
- Users can see concrete examples of what each threshold setting means
- No more "blind slider" experience
- Quality warnings help identify problematic matches

**Files Changed:**
- `backend/src/airwave/api/routers/admin.py`
- `frontend/src/components/admin/ExampleMatches.tsx`

**Documentation:**
- `docs/phase1-frontend-ux-complete.md`

---

#### Phase 0: Backend Foundation
- **Stratified sampling** for representative examples
- **Three-range filtering** (auto/review/reject)
- **Match impact analysis** endpoint
- **Quality heuristics** for match warnings

**Impact:**
- Backend infrastructure for Match Tuner UX
- Efficient sampling and categorization
- Foundation for all subsequent phases

**Files Changed:**
- `backend/src/airwave/api/routers/admin.py`

**Documentation:**
- `docs/phase0-backend-foundation-complete.md`

---

## [2026-02-18] - Phase 4 Migration & Fixes

### Changed

#### Phase 4: Identity Resolution Architecture
- **Migrated all tables** from `recording_id` to `work_id`
- **Three-layer resolution** - Identity (Work) → Policy (Recording) → Resolution (LibraryFile)
- **Separation of concerns** - identity vs version selection
- **Flexibility** - can change preferred recording without re-verification

**Impact:**
- More flexible and resilient matching system
- Can express station preferences (e.g., "prefer radio edits")
- Better handling of file changes and deletions

**Files Changed:**
- `backend/src/airwave/core/models.py`
- `backend/src/airwave/worker/matcher.py`
- `backend/src/airwave/api/routers/discovery.py`
- Database migration

**Documentation:**
- `docs/planning/identity-resolution-architecture.md`

---

### Fixed

#### Three-Range Filtering Implementation
- **Fixed Match Tuner threshold settings** - matcher now uses correct settings
- **Implemented three-range filtering** - auto-accept, review, reject
- **Added Review Confidence match type** - for matches between review and auto thresholds
- **Auto-linking for high confidence matches** - bypasses Discovery Queue

**Impact:**
- Match Tuner is now functional - adjusting sliders affects matching behavior
- Discovery Queue only contains items that need review
- High confidence matches are auto-linked (no manual review needed)

**Files Changed:**
- `backend/src/airwave/worker/matcher.py`

**Documentation:**
- `docs/implementation-three-range-filtering.md`
- `docs/critical-match-tuner-not-working.md` (describes the bug)

---

#### Phase 4 Matcher Issues
- **Fixed `rematch_items_for_artist`** - updated to use `suggested_work_id` instead of `suggested_recording_id`
- **Optimized Match Tuner performance** - reduced default limit from 20 to 10, limited candidates to 5
- **Fixed Phase 3 remnants** - all code updated to Phase 4 schema

**Impact:**
- Re-matching after artist linking works correctly
- Match Tuner page loads in under 2 seconds (was 4.3 seconds)
- No more AttributeError when linking artists

**Files Changed:**
- `backend/src/airwave/api/routers/discovery.py`
- `backend/src/airwave/api/routers/admin.py`
- `frontend/src/pages/admin/MatchTuner.tsx`

**Documentation:**
- `docs/fixes-phase4-matcher-issues.md`
- `docs/analysis-phase4-matcher-issues.md` (describes the issues)

---

## See Also

- [Current Architecture](./CURRENT-ARCHITECTURE.md) - Comprehensive overview of current system
- [Match Tuner - All Phases Complete](./match-tuner-all-phases-complete.md) - Complete Match Tuner documentation
- [Identity Resolution Architecture](./planning/identity-resolution-architecture.md) - Phase 4 architecture details

