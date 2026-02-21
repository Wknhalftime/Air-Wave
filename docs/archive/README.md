# Archive - Historical Documentation

This directory contains historical documentation that describes bugs, issues, and investigations that have been **resolved** and are no longer relevant to the current codebase.

These documents are kept for historical reference but should **not** be used to understand the current system.

---

## Archived Documents

### `critical-match-tuner-not-working.md`
**Status:** ✅ FIXED  
**Date:** 2026-02-18  
**Description:** Describes a bug where Match Tuner was not functional because the matcher was using hardcoded thresholds instead of the configurable settings.

**Resolution:** Fixed in `implementation-three-range-filtering.md` - matcher now uses correct threshold settings.

**See:** `docs/CHANGELOG.md` for details on the fix.

---

### `analysis-phase4-matcher-issues.md`
**Status:** ✅ FIXED
**Date:** 2026-02-18
**Description:** Analysis of issues found after Phase 4 migration, including AttributeError in `rematch_items_for_artist` and performance issues in Match Tuner.

**Resolution:** Fixed in `fixes-phase4-matcher-issues.md` - updated to use Phase 4 schema and optimized performance.

**See:** `docs/CHANGELOG.md` for details on the fixes.

---

### `fixes-phase4-matcher-issues.md`
**Status:** ✅ IMPLEMENTED
**Date:** 2026-02-18
**Description:** Documents fixes for Phase 4 matcher issues, including updating `rematch_items_for_artist` to use `suggested_work_id` and optimizing Match Tuner performance.

**Resolution:** All fixes have been implemented and are now part of the current codebase.

**See:** `docs/CHANGELOG.md` for summary of changes.

---

### `bugfix-verification-filter-phase4-migration.md`
**Status:** ✅ FIXED
**Date:** 2026-02-18
**Description:** Documents a specific bug fix for verification filter after Phase 4 migration.

**Resolution:** Bug has been fixed and is now part of the current codebase.

**See:** `docs/CHANGELOG.md` for details.

---

### `implementation-three-range-filtering.md`
**Status:** ✅ IMPLEMENTED
**Date:** 2026-02-18
**Description:** Documents the implementation of three-range filtering (auto/review/reject) for the Discovery Queue.

**Resolution:** Three-range filtering is now fully implemented and documented in `docs/CURRENT-ARCHITECTURE.md`.

**See:** `docs/CURRENT-ARCHITECTURE.md` for current implementation details.

---

### `match-tuner-stratified-sampling-fixes.md`
**Status:** ✅ FIXED
**Date:** 2026-02-19
**Description:** Documents fixes for stratified sampling bugs in Match Tuner, including inconsistent category logic and incorrect threshold comparisons.

**Resolution:** All fixes have been implemented and stratified sampling now works correctly.

**See:** `docs/CHANGELOG.md` for summary of fixes.

---

## For Current Information

Please refer to:
- **`docs/CURRENT-ARCHITECTURE.md`** - Comprehensive overview of current system architecture
- **`docs/CHANGELOG.md`** - All changes, fixes, and improvements
- **`docs/match-tuner-all-phases-complete.md`** - Complete Match Tuner documentation

---

## Why Archive?

These documents are archived rather than deleted because:
1. **Historical context** - Shows how problems were identified and solved
2. **Learning resource** - Demonstrates debugging and problem-solving process
3. **Audit trail** - Provides evidence of issues and their resolutions
4. **Reference** - May be useful if similar issues arise in the future

However, they should **not** be used to understand the current system, as they describe problems that no longer exist.

