# Match Tuner: Enhanced Stratified Sampling with Quality Analysis

## Problem Statement

The original Match Tuner UX lacked critical information for making informed threshold decisions:

1. **No context for threshold values** - Users couldn't see what "66%" actually means in practice
2. **Random examples unhelpful** - Examples didn't show matches near threshold boundaries
3. **Blind decision-making** - No way to see what would be auto-linked vs reviewed vs rejected at specific thresholds
4. **Single data points misleading** - Showing 2-3 examples per category doesn't reveal patterns vs outliers
5. **Can't assess trade-offs** - No way to see both good AND bad matches at similar similarity scores
6. **No quality indicators** - Can't identify potentially problematic matches (truncation, length mismatch, etc.)

## Solution: Enhanced Stratified Sampling with Quality Analysis

Implemented stratified sampling with:
- **10-15 examples per category** (instead of 2-3) to show variety and patterns
- **Quality warning flags** to highlight potentially problematic matches
- **Collapsible category sections** to manage UI complexity
- **Prominent similarity scores** to understand what percentages mean in practice

---

## Backend Changes

### Modified Endpoint: `GET /api/v1/admin/match-samples`

**New Parameter**:
- `stratified` (boolean, default: false) - Enable stratified sampling

**Behavior When `stratified=true`**:
1. Samples 500 random unmatched logs (increased from 200)
2. Runs matching on all samples
3. Categorizes matches based on similarity scores and thresholds
4. Analyzes match quality using heuristics:
   - **Truncation Risk**: Match is <60% length of original
   - **Length Mismatch**: Significant difference in length (>30 chars)
   - **Extra Text**: Match contains "feat.", "remix", "(", etc.
   - **Case Only**: Only difference is capitalization
5. Selects 10-15 examples from each category (increased from 2-3):
   - **Near Auto Threshold**: Matches just above auto-link threshold (auto to auto+10%)
   - **In Review Range**: Matches between review and auto thresholds
   - **Near Review Threshold**: Matches just below review threshold (review-10% to review)
   - **Identity Bridge**: Pre-verified mappings (up to 10)
6. Returns stratified samples with quality warnings

**Performance**:
- Sample size: 500 logs (increased from 200)
- Expected time: 10-15 seconds (vs. 1-2 seconds for random sampling)
- Returns 30-50 examples total (vs. 8-11 previously)
- Provides much more valuable information for decision-making

---

## Frontend Changes

### Updated Component: `ExampleMatches.tsx`

**New Props**:
- `thresholds` - Current threshold settings to show context

**New Features**:
- **Collapsible category sections** - Each category can be expanded/collapsed independently
- **Quality warning badges** - Orange badges highlight potentially problematic matches
- **10-15 examples per category** - Shows variety and patterns, not just outliers
- **Prominent similarity scores** - Bold, large font for easy scanning

**New Display**:
- Grouped by category with collapsible headers
- Each group shows:
  - Category name, icon, and count
  - Threshold range explanation
  - Expand/collapse chevron
- Each example shows:
  - Broadcast data (raw artist/title)
  - Best match candidate
  - **Prominent similarity scores** (Artist: X%, Title: Y%) in bold
  - Match type
  - **Quality warning badges** (if any):
    - ⚠️ Truncation Risk
    - ⚠️ Length Mismatch
    - ℹ️ Extra Text
    - ℹ️ Case Only

**Visual Hierarchy**:
```
┌─────────────────────────────────────────────────────────────┐
│  Example Matches (9)                    [Refresh] [▼ Show]  │
├─────────────────────────────────────────────────────────────┤
│  Understanding Threshold Boundaries:                         │
│  These examples show matches near your threshold settings... │
├─────────────────────────────────────────────────────────────┤
│  🔗 Pre-Verified Mappings (2)                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MEAT LOAF - I'd Do Anything...                      │   │
│  │ Best Match: Meat Loaf - I'd Do Anything For Love    │   │
│  │ Artist: 100.0%  Title: 95.0%  (Identity Bridge)     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ✓ Will Auto-Link (3) - Above 85% threshold                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Beatles - Let It Be                                  │   │
│  │ Best Match: The Beatles - Let It Be                  │   │
│  │ Artist: 95.0%  Title: 100.0%  (High Confidence)     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ⚠ Sent to Review Queue (3) - Between 70% and 85%          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Hall & Oates - Maneater                              │   │
│  │ Best Match: Daryl Hall & John Oates - Maneater       │   │
│  │ Artist: 68.0%  Title: 100.0%  (Vector Match)        │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ✗ Will Be Rejected (1) - Below 70% threshold               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Unknown Artist - Unknown Song                        │   │
│  │ Best Match: Various Artists - Unknown                │   │
│  │ Artist: 45.0%  Title: 50.0%  (Vector Match)         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## User Experience Improvements

### Before ❌
- Random examples that might all be 95%+ matches
- Only 2-3 examples per category (can't see patterns)
- No way to see what happens at threshold boundaries
- Users had to guess what "66%" means
- No indication of potentially problematic matches
- Trial-and-error approach to setting thresholds

### After ✅
- Examples specifically selected near threshold boundaries
- **10-15 examples per category** to show variety and patterns
- Clear grouping by outcome (auto-link, review, reject)
- **Collapsible sections** to manage UI complexity
- Prominent similarity scores show what percentages mean
- **Quality warning badges** highlight potentially problematic matches
- Users can see: "If I set artist threshold to 70%, matches like 'Hall & Oates' → 'Daryl Hall & John Oates' (68% similarity) will be sent to review"
- Users can identify risky matches: "This match has a truncation risk - the matched title is much shorter than the original"

---

## Example Use Case

**Scenario**: User wants to adjust artist threshold from 85% to 70%

**Before**:
1. User moves slider to 70%
2. Clicks "Preview Impact" → sees "847 auto-links, 124 reviews"
3. Clicks "Refresh Samples" → sees random examples (might all be 95%+)
4. User has no idea what 70% actually means
5. User saves and hopes for the best

**After**:
1. User moves slider to 70%
2. Clicks "Preview Impact" → sees "847 auto-links, 124 reviews"
3. Clicks "Refresh" on Example Matches → sees stratified samples:
   - **Will Auto-Link**: "Beatles - Let It Be" → "The Beatles - Let It Be" (95% / 100%)
   - **Sent to Review**: "Hall & Oates - Maneater" → "Daryl Hall & John Oates - Maneater" (68% / 100%)
   - **Will Be Rejected**: "Unknown Artist" → "Various Artists" (45% / 50%)
4. User thinks: "Hmm, 'Hall & Oates' → 'Daryl Hall & John Oates' at 68% should probably be auto-linked, not sent to review"
5. User adjusts threshold to 65% and previews again
6. User saves with confidence

---

## Technical Implementation

### Backend Logic

```python
# Stratified sampling algorithm
if stratified:
    # Sample larger pool
    sample_size = 200
    
    # Categorize all samples
    for sample in all_samples:
        min_sim = min(artist_sim, title_sim)
        
        if min_sim >= artist_auto and min_sim < artist_auto + 0.10:
            near_auto.append(sample)
        elif min_sim >= artist_review and min_sim < artist_auto:
            in_review.append(sample)
        elif min_sim >= artist_review - 0.10 and min_sim < artist_review:
            near_review.append(sample)
    
    # Select 2-3 from each category
    response = near_auto[:3] + in_review[:3] + near_review[:3]
```

### Frontend Logic

```typescript
// Group samples by category
const groupedSamples = {
    identity_bridge: samples.filter(s => s.category === 'identity_bridge'),
    auto_link: samples.filter(s => s.category === 'auto_link'),
    review: samples.filter(s => s.category === 'review'),
    reject: samples.filter(s => s.category === 'reject'),
};

// Render each group with context
{groupedSamples.auto_link.length > 0 && (
    <div>
        <h4>Will Auto-Link ({groupedSamples.auto_link.length})
            - Above {(thresholds.artist_auto * 100).toFixed(0)}% threshold
        </h4>
        {groupedSamples.auto_link.map(sample => renderSample(sample))}
    </div>
)}
```

---

## Files Changed

**Backend**:
- `backend/src/airwave/api/routers/admin.py` - Added stratified sampling logic

**Frontend**:
- `frontend/src/lib/api.ts` - Added `stratified` parameter
- `frontend/src/components/admin/ExampleMatches.tsx` - Grouped display with prominent scores
- `frontend/src/pages/admin/MatchTuner.tsx` - Pass thresholds, use stratified=true

---

## Testing

1. Navigate to Match Tuner page
2. Adjust thresholds (e.g., artist auto to 70%)
3. Click "Refresh" on Example Matches
4. Verify:
   - Examples are grouped by category
   - Each group shows threshold range
   - Similarity scores are prominent (bold, large)
   - Examples are near threshold boundaries (not all 95%+)

---

## Performance Impact

- **Random sampling**: 1-2 seconds (10 logs)
- **Stratified sampling**: 5-10 seconds (200 logs)
- **Trade-off**: Worth it for much more valuable information

---

## Success Metrics

- ✅ Users can see what threshold percentages mean in practice
- ✅ Examples show matches near decision boundaries
- ✅ Clear grouping by outcome (auto-link, review, reject)
- ✅ Prominent similarity scores for context
- ✅ Users can make informed threshold decisions


