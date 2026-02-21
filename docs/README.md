# Airwave Documentation

**Last Updated:** 2026-02-20

This directory contains comprehensive documentation for the Airwave broadcast log management system.

---

## 🚀 Quick Start for AI Agents

If you're an AI agent trying to understand this codebase, start here:

1. **[CURRENT-ARCHITECTURE.md](./CURRENT-ARCHITECTURE.md)** - Comprehensive overview of the current system
2. **[CHANGELOG.md](./CHANGELOG.md)** - Recent changes, fixes, and improvements
3. **[Match Tuner - All Phases Complete](./match-tuner-all-phases-complete.md)** - Complete Match Tuner documentation

---

## 📚 Documentation Index

### Core Architecture

#### **[CURRENT-ARCHITECTURE.md](./CURRENT-ARCHITECTURE.md)** ⭐ START HERE
Comprehensive overview of Airwave's current architecture, including:
- System overview and core components
- Phase 4 Identity Resolution Architecture (work_id vs recording_id)
- Match Tuner system (all 4 phases)
- Discovery & Verification Hub
- Performance optimizations
- Data model and matching pipeline

**When to use:** Understanding the overall system, architecture decisions, and current implementation.

---

#### **[CHANGELOG.md](./CHANGELOG.md)** ⭐ RECENT CHANGES
Chronological list of all changes, fixes, and improvements:
- 2026-02-20: Artist Linking Decoupling, Rematch Batching Optimization
- 2026-02-19: Match Tuner UX Improvements (Phases 1-4)
- 2026-02-18: Phase 4 Migration & Fixes

**When to use:** Understanding what changed recently, why it changed, and what problems were solved.

---

### Feature Documentation

#### **[match-tuner-all-phases-complete.md](./match-tuner-all-phases-complete.md)** ⭐ MATCH TUNER
Complete documentation for the Match Tuner system:
- All 4 phases (Foundation, Impact, Edge Cases, 2D Visualization)
- Three-range filtering (auto/review/reject)
- Stratified sampling
- Quality heuristics
- Implementation details

**When to use:** Understanding Match Tuner functionality, thresholds, and how matching works.

---

#### **[artist-linking-decoupling-fix.md](./artist-linking-decoupling-fix.md)**
Documents the architectural fix for Artist Linking:
- Why it was coupled to DiscoveryQueue (wrong)
- How it was decoupled to query BroadcastLog (correct)
- Benefits of the new approach

**When to use:** Understanding artist linking and why it's independent of song matching.

---

#### **[rematch-batching-optimization.md](./rematch-batching-optimization.md)**
Documents the 10x performance improvement for rematch:
- Why rematch was slow (one-at-a-time processing)
- How batching was implemented (500 items per batch)
- Performance impact (10x faster, 300x fewer queries)

**When to use:** Understanding rematch performance and batching strategy.

---

#### **[PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md)**
Documents the Library Navigation System:
- Artist/Work/Recording/LibraryFile hierarchy
- Navigation UI components
- Separate from Match Tuner work

**When to use:** Understanding library navigation features.

---

### Planning & Architecture

#### **[planning/identity-resolution-architecture.md](./planning/identity-resolution-architecture.md)**
Detailed Phase 4 architecture document:
- Three-layer resolution (Identity → Policy → Resolution)
- Migration plan from Phase 3 to Phase 4
- Design decisions and rationale

**When to use:** Deep dive into Phase 4 architecture and design decisions.

---

#### **[planning/verification-hub-redesign-review.md](./planning/verification-hub-redesign-review.md)**
Design document for Verification Hub redesign.

**When to use:** Understanding Verification Hub design decisions.

---

### Phase-Specific Documentation

These documents describe individual phases of Match Tuner implementation:

- **[phase0-backend-foundation-complete.md](./phase0-backend-foundation-complete.md)** - Backend infrastructure
- **[phase1-frontend-ux-complete.md](./phase1-frontend-ux-complete.md)** - Match example cards
- **[phase2-example-matches-complete.md](./phase2-example-matches-complete.md)** - Impact visibility
- **[phase3-edge-case-highlighting-complete.md](./phase3-edge-case-highlighting-complete.md)** - Edge case detection
- **[phase4-2d-visualization-complete.md](./phase4-2d-visualization-complete.md)** - Scatter plot visualization

**When to use:** Understanding specific phase implementation details. For comprehensive overview, use `match-tuner-all-phases-complete.md` instead.

---

### Supporting Documentation

#### **[match-tuner-stratified-sampling.md](./match-tuner-stratified-sampling.md)**
Describes the stratified sampling approach for Match Tuner examples.

**When to use:** Understanding how Match Tuner selects representative examples.

---

#### **[match-tuner-ux-implementation-complete.md](./match-tuner-ux-implementation-complete.md)**
Summary of Match Tuner UX implementation.

**When to use:** High-level overview of Match Tuner UX work.

---

### Archive

#### **[archive/](./archive/)**
Historical documentation describing bugs and issues that have been **resolved**.

**⚠️ DO NOT USE FOR CURRENT SYSTEM UNDERSTANDING**

These documents are kept for historical reference only. See `archive/README.md` for details.

---

## 🎯 Common Tasks

### "I need to understand the current system"
→ Start with **[CURRENT-ARCHITECTURE.md](./CURRENT-ARCHITECTURE.md)**

### "What changed recently?"
→ Read **[CHANGELOG.md](./CHANGELOG.md)**

### "How does Match Tuner work?"
→ Read **[match-tuner-all-phases-complete.md](./match-tuner-all-phases-complete.md)**

### "Why is artist linking independent of song matching?"
→ Read **[artist-linking-decoupling-fix.md](./artist-linking-decoupling-fix.md)**

### "How does Phase 4 Identity Resolution work?"
→ Read **[planning/identity-resolution-architecture.md](./planning/identity-resolution-architecture.md)**

### "Why was rematch slow and how was it fixed?"
→ Read **[rematch-batching-optimization.md](./rematch-batching-optimization.md)**

---

## 📝 Documentation Principles

1. **Agent-Friendly** - Documentation is optimized for AI agents to quickly understand the system
2. **Current First** - Focus on current implementation, not historical bugs
3. **Comprehensive** - Include architecture, design decisions, and implementation details
4. **Consolidated** - Avoid redundancy, consolidate related information
5. **Archived** - Historical bug reports are archived, not deleted

---

## 🔄 Maintenance

This documentation is actively maintained. When making significant changes:

1. Update **CURRENT-ARCHITECTURE.md** if architecture changes
2. Add entry to **CHANGELOG.md** with date and description
3. Update feature-specific docs if functionality changes
4. Archive outdated bug reports to **archive/** directory

---

## 📞 Questions?

If you're an AI agent and can't find what you need:
1. Check **CURRENT-ARCHITECTURE.md** first
2. Search **CHANGELOG.md** for recent changes
3. Look for feature-specific documentation
4. Ask the user for clarification

