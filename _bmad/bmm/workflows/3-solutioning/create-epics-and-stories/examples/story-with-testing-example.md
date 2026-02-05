# Story with Testing Requirements - Example

This document provides a complete example of a story following the updated template with testing requirements.

---

## Example 1: UI Component Story

### Story 3.1: Focus Deck UI Interaction

As a radio station manager,
I want to navigate through unmatched broadcast logs using keyboard shortcuts,
So that I can quickly review and verify matches without using the mouse.

**Acceptance Criteria:**

**Given** I am viewing the Verification page with unmatched logs in the queue
**When** I press the right arrow key
**Then** the next card should be displayed with a smooth animation
**And** the card index should increment by 1

**Given** I am viewing the first card in the deck
**When** I press the left arrow key
**Then** the card should remain on the first card
**And** no error should occur

**Given** I am viewing any card in the deck
**When** I press the Space key
**Then** the card should flip to show the match details
**And** the flip animation should complete smoothly

**Testing Requirements:**

- **Unit Tests**:
  - Test keyboard event handlers (ArrowLeft, ArrowRight, Space)
  - Test card state management (currentIndex updates correctly)
  - Test edge cases (first card, last card, empty queue)
  - Test flip state toggle logic
  - Mock React Query hooks for queue data

- **Integration Tests**:
  - Test React Query integration for fetching queue items
  - Test state persistence across navigation
  - Test Zustand store updates when navigating cards
  - Verify correct API calls when loading queue data

- **E2E Tests**:
  - Test complete keyboard navigation workflow (navigate through 5 cards)
  - Test card flip animation with Space key
  - Test focus management (keyboard focus stays on interactive elements)
  - Test navigation boundaries (can't go before first or after last)
  - Verify smooth animations and transitions

- **Manual Testing**:
  - Visual verification of card animations (smooth, no jank)
  - Accessibility testing (keyboard-only navigation works)
  - Screen reader testing (announces card changes)
  - Cross-browser testing (Chrome, Firefox, Safari)
  - Responsive design verification (works on different screen sizes)

---

## Example 2: Backend API Story

### Story 2.3: Search Endpoint with Hybrid Vector Search

As a radio station manager,
I want to search for recordings using partial artist or title matches,
So that I can quickly find tracks even with typos or incomplete information.

**Acceptance Criteria:**

**Given** I search for "elton john don't"
**When** the search endpoint is called
**Then** I should receive "Don't Go Breaking My Heart" in the results
**And** the results should include both exact and semantic matches

**Given** I search with a trailing space "LIMP BIZKIT "
**When** the search endpoint is called
**Then** the trailing space should be trimmed
**And** results should match "LIMP BIZKIT" without the space

**Testing Requirements:**

- **Unit Tests**:
  - Test query normalization (Normalizer.clean)
  - Test ILIKE pattern generation
  - Test vector search fallback logic (triggers when < 5 results)
  - Test result deduplication (no duplicate IDs)
  - Test Bronze filtering logic (include_bronze parameter)
  - Mock VectorDB and database session

- **Integration Tests**:
  - Test complete search flow with real database
  - Test ILIKE search returns correct results
  - Test vector search integration with ChromaDB
  - Test hybrid search merges results correctly
  - Test pagination and limit parameters
  - Verify SQL queries are optimized (no N+1 queries)

- **E2E Tests**:
  - Test search API endpoint with various queries
  - Test search with special characters (apostrophes, ampersands)
  - Test search with trailing/leading spaces
  - Test search with Bronze filtering enabled/disabled
  - Verify response format matches SearchResponse schema

- **Manual Testing**:
  - Performance testing with large datasets (10k+ recordings)
  - Load testing (concurrent search requests)
  - Verify ChromaDB index is populated correctly

---

## Example 3: Database Schema Story

### Story 1.2: Create DiscoveryQueue Aggregation Table

As a system,
I want to aggregate unmatched broadcast logs by normalized signature,
So that duplicate logs are grouped together for efficient verification.

**Acceptance Criteria:**

**Given** multiple broadcast logs with the same normalized artist and title
**When** the aggregation process runs
**Then** a single DiscoveryQueue entry should be created
**And** all matching logs should reference the same queue entry

**Given** a broadcast log is matched to a recording
**When** the match is saved
**Then** the DiscoveryQueue entry should be marked as resolved
**And** the entry should no longer appear in the verification queue

**Testing Requirements:**

- **Unit Tests**:
  - Not applicable (schema-only story)

- **Integration Tests**:
  - Test table creation with correct schema
  - Test foreign key constraints (references BroadcastLog, Recording)
  - Test indexes are created (normalized_artist, normalized_title)
  - Test aggregation query groups logs correctly
  - Test cascade delete behavior
  - Verify unique constraints work as expected

- **E2E Tests**:
  - Not applicable (database-only story)

- **Manual Testing**:
  - Verify migration runs successfully
  - Check database schema matches SQLAlchemy models
  - Verify indexes improve query performance (EXPLAIN ANALYZE)
  - Test rollback migration works correctly

---

## Testing Decision Matrix Reference

| Story Type | Unit Tests | Integration Tests | E2E Tests | Manual Tests |
|------------|-----------|-------------------|-----------|--------------|
| **Backend API** | ✅ Required | ✅ Required | ⚠️ Optional | ❌ Not needed |
| **Database Schema** | ⚠️ Optional | ✅ Required | ❌ Not needed | ⚠️ Verification |
| **UI Component** | ✅ Required | ⚠️ Optional | ✅ Required | ⚠️ Visual check |
| **Business Logic** | ✅ Required | ✅ Required | ⚠️ Optional | ❌ Not needed |
| **Configuration** | ❌ Not needed | ❌ Not needed | ❌ Not needed | ✅ Required |
| **Documentation** | ❌ Not needed | ❌ Not needed | ❌ Not needed | ⚠️ Review only |

