"""Quick test script for Phase 0 backend endpoints.

Run this after starting the backend to verify the new endpoints work correctly.

Usage:
    python test_phase0_endpoints.py
"""

import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000/api/v1/admin"


def test_match_samples():
    """Test the enhanced /match-samples endpoint."""
    print("\n" + "="*60)
    print("TEST 1: Match Samples with Categorization")
    print("="*60)
    
    # Test without custom thresholds
    print("\n1a. Testing without custom thresholds...")
    response = requests.get(f"{BASE_URL}/match-samples?limit=5")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Got {len(data)} samples")
        
        if data:
            sample = data[0]
            print(f"\nSample match:")
            print(f"  Raw: {sample['raw_artist']} - {sample['raw_title']}")
            print(f"  Category: {sample.get('category', 'N/A')}")
            print(f"  Action: {sample.get('action', 'N/A')}")
            
            if sample.get('match'):
                print(f"  Match: {sample['match']['reason']}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
    
    # Test with custom thresholds
    print("\n1b. Testing with custom thresholds (strict)...")
    response = requests.get(
        f"{BASE_URL}/match-samples",
        params={
            "limit": 5,
            "artist_auto": 0.95,
            "artist_review": 0.85,
            "title_auto": 0.90,
            "title_review": 0.80
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Got {len(data)} samples with strict thresholds")
        
        # Count categories
        categories = {}
        for sample in data:
            cat = sample.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\nCategory distribution:")
        for cat, count in categories.items():
            print(f"  {cat}: {count}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)


def test_match_impact():
    """Test the new /match-impact endpoint."""
    print("\n" + "="*60)
    print("TEST 2: Match Impact Analysis")
    print("="*60)
    
    # Test with balanced thresholds
    print("\n2a. Testing with balanced thresholds...")
    response = requests.get(
        f"{BASE_URL}/match-impact",
        params={
            "artist_auto": 0.85,
            "artist_review": 0.70,
            "title_auto": 0.80,
            "title_review": 0.70,
            "sample_size": 100  # Small sample for quick test
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"\nImpact Analysis:")
        print(f"  Total Unmatched: {data['total_unmatched']}")
        print(f"  Sample Size: {data['sample_size']}")
        print(f"  Auto-Link: {data['auto_link_count']} ({data['auto_link_percentage']}%)")
        print(f"  Review: {data['review_count']} ({data['review_percentage']}%)")
        print(f"  Reject: {data['reject_count']} ({data['reject_percentage']}%)")
        print(f"  Identity Bridge: {data['identity_bridge_count']} ({data['identity_bridge_percentage']}%)")
        print(f"\nEdge Cases:")
        print(f"  Within 5% of auto: {data['edge_cases']['within_5pct_of_auto']}")
        print(f"  Within 5% of review: {data['edge_cases']['within_5pct_of_review']}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
    
    # Test with strict thresholds
    print("\n2b. Testing with strict thresholds...")
    response = requests.get(
        f"{BASE_URL}/match-impact",
        params={
            "artist_auto": 0.95,
            "artist_review": 0.85,
            "title_auto": 0.90,
            "title_review": 0.80,
            "sample_size": 100
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"  Auto-Link: {data['auto_link_count']} ({data['auto_link_percentage']}%)")
        print(f"  Review: {data['review_count']} ({data['review_percentage']}%)")
        print(f"  Reject: {data['reject_count']} ({data['reject_percentage']}%)")
        print("\n  ℹ️ Note: Auto-link count should be lower with strict thresholds")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)


def test_validation():
    """Test validation of /match-impact endpoint."""
    print("\n" + "="*60)
    print("TEST 3: Validation")
    print("="*60)
    
    # Test invalid threshold (> 1.0)
    print("\n3a. Testing invalid threshold (> 1.0)...")
    response = requests.get(
        f"{BASE_URL}/match-impact",
        params={
            "artist_auto": 1.5,  # Invalid!
            "artist_review": 0.70,
            "title_auto": 0.80,
            "title_review": 0.70
        }
    )
    
    if response.status_code == 400:
        print(f"✅ Correctly rejected invalid threshold")
        print(f"  Error: {response.json()['detail']}")
    else:
        print(f"❌ Should have returned 400, got {response.status_code}")
    
    # Test review > auto
    print("\n3b. Testing review threshold > auto threshold...")
    response = requests.get(
        f"{BASE_URL}/match-impact",
        params={
            "artist_auto": 0.70,
            "artist_review": 0.85,  # Higher than auto!
            "title_auto": 0.80,
            "title_review": 0.70
        }
    )
    
    if response.status_code == 400:
        print(f"✅ Correctly rejected invalid threshold order")
        print(f"  Error: {response.json()['detail']}")
    else:
        print(f"❌ Should have returned 400, got {response.status_code}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PHASE 0 BACKEND ENDPOINT TESTS")
    print("="*60)
    print("\nMake sure the backend is running on http://localhost:8000")
    print("Press Ctrl+C to cancel, or Enter to continue...")
    input()
    
    try:
        test_match_samples()
        test_match_impact()
        test_validation()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETE!")
        print("="*60)
        print("\n✅ Phase 0 backend endpoints are working correctly!")
        print("\nNext steps:")
        print("  1. Review the test results above")
        print("  2. Proceed with Phase 1 (Frontend UX)")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to backend")
        print("Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

