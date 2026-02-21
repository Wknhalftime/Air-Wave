# Match Tuner Stratified Sampling - Critical Fixes

## Problem

User reported that stratified sampling was not working - showing **0 Review examples** even though the review range was 70-85% for artist and 70-80% for title.

## Root Causes

### 1. Inconsistent Category Logic

**Issue**: The category assignment logic (lines 312-330) and stratified sampling logic (lines 400-424) were using different criteria.

**Original Category Logic**:
- Based on `match_type` (Exact, High Confidence, Review Confidence, Vector)
- Inconsistent with three-range filtering

**Original Stratified Logic**:
- Used `min(artist_sim, title_sim)` for categorization
- Compared against `thresholds["artist_auto"]` for BOTH artist and title
- Only included matches within 10% of thresholds ("near" ranges)

**Problem**: This meant:
- A match with artist=75%, title=75% would be categorized as "review" in the first pass
- But in stratified sampling, it would be excluded because it wasn't "near" any threshold
- Result: 0 examples in review category

### 2. Incorrect Threshold Comparison

**Issue**: Used `thresholds["artist_auto"]` for both artist and title comparisons instead of separate thresholds.

**Should be**:
- Artist: `thresholds["artist_auto"]` and `thresholds["artist_review"]`
- Title: `thresholds["title_auto"]` and `thresholds["title_review"]`

### 3. Too Restrictive "Near" Ranges

**Issue**: Only included matches within ±10% of thresholds, missing most of the review range.

**Example**: With artist_auto=85%, artist_review=70%:
- "Near auto": 85-95% only
- "In review": Excluded most 70-85% range
- "Near review": 60-70% only

## Solutions Implemented

### Fix 1: Consistent Three-Range Filtering

**Updated category assignment (lines 312-330)**:
```python
if "Identity Bridge" in reason:
    category = "identity_bridge"
elif (artist_sim >= thresholds["artist_auto"] and
      title_sim >= thresholds["title_auto"]):
    category = "auto_link"  # BOTH above auto
elif (artist_sim >= thresholds["artist_review"] and
      title_sim >= thresholds["title_review"]):
    category = "review"  # BOTH above review, at least one below auto
else:
    category = "reject"  # Either below review
```

**Updated stratified sampling (lines 400-424)**:
```python
if item["category"] == "identity_bridge":
    identity_bridge.append(item)
elif (artist_sim >= thresholds["artist_auto"] and 
      title_sim >= thresholds["title_auto"]):
    near_auto.append(item)  # All auto-link matches
elif (artist_sim >= thresholds["artist_review"] and 
      title_sim >= thresholds["title_review"]):
    in_review.append(item)  # All review matches
else:
    near_review.append(item)  # All reject matches
```

### Fix 2: Separate Artist/Title Thresholds

Now correctly uses:
- `thresholds["artist_auto"]` and `thresholds["title_auto"]` for auto-link
- `thresholds["artist_review"]` and `thresholds["title_review"]` for review

### Fix 3: Include ALL Matches in Each Range

Removed the "near threshold" restriction - now includes ALL matches in each category:
- **Auto-link**: ALL matches where both artist AND title ≥ auto thresholds
- **Review**: ALL matches where both ≥ review but at least one < auto
- **Reject**: ALL matches where either < review

Then selects 10-15 examples from each category.

### Fix 4: Increased Sample Size

Changed from 500 to **1000 logs** to ensure enough matches in each category.

## Expected Results

After these fixes, users should see:
- ✅ **10-15 examples in Auto-link category** (both artist and title ≥ auto thresholds)
- ✅ **10-15 examples in Review category** (both ≥ review, at least one < auto)
- ✅ **10-15 examples in Reject category** (either < review)
- ✅ **Up to 10 Identity Bridge examples** (pre-verified mappings)

Total: **30-50 examples** showing variety across all ranges.

## Performance Impact

- Sample size: 1000 logs (up from 500)
- Expected time: 15-20 seconds (up from 10-15 seconds)
- Trade-off: Worth it for comprehensive, accurate categorization

## Testing

1. Navigate to Match Tuner
2. Set thresholds (e.g., artist_auto=85%, artist_review=70%, title_auto=80%, title_review=70%)
3. Click "Refresh" on Example Matches
4. Verify you see examples in ALL categories (Auto, Review, Reject)
5. Verify examples match the threshold ranges

