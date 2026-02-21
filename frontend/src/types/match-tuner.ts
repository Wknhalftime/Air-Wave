// Match Tuner Types

export interface MatchImpactResponse {
    total_unmatched: number;
    sample_size: number;
    auto_link_count: number;
    auto_link_percentage: number;
    review_count: number;
    review_percentage: number;
    reject_count: number;
    reject_percentage: number;
    identity_bridge_count: number;
    identity_bridge_percentage: number;
    edge_cases: {
        within_5pct_of_auto: number;
        within_5pct_of_review: number;
    };
    thresholds_used: {
        artist_auto: number;
        artist_review: number;
        title_auto: number;
        title_review: number;
    };
}

