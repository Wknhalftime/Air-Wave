import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, XCircle, Link2, AlertTriangle, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface MatchCandidate {
    recording_id: number;
    artist: string;
    title: string;
    artist_sim: number;
    title_sim: number;
    vector_dist: number;
    match_type: string;
    quality_warnings?: string[];
    edge_case?: string;
}

interface MatchSample {
    id: number;
    raw_artist: string;
    raw_title: string;
    match: { recording_id: number; reason: string } | null;
    candidates: MatchCandidate[];
    category?: string;
    action?: string;
}

interface ExampleMatchesProps {
    samples: MatchSample[];
    loading: boolean;
    onRefresh: () => void;
    thresholds: {
        artist_auto: number;
        artist_review: number;
        title_auto: number;
        title_review: number;
    };
}

const getCategoryIcon = (category?: string) => {
    switch (category) {
        case 'auto_link':
            return <CheckCircle2 className="h-4 w-4 text-green-600" />;
        case 'review':
            return <AlertCircle className="h-4 w-4 text-yellow-600" />;
        case 'reject':
            return <XCircle className="h-4 w-4 text-red-600" />;
        case 'identity_bridge':
            return <Link2 className="h-4 w-4 text-blue-600" />;
        default:
            return null;
    }
};

const getCategoryLabel = (category?: string) => {
    switch (category) {
        case 'auto_link':
            return 'Auto-Link';
        case 'review':
            return 'Review';
        case 'reject':
            return 'Reject';
        case 'identity_bridge':
            return 'Identity Bridge';
        default:
            return 'Unknown';
    }
};

const getCategoryColor = (category?: string) => {
    switch (category) {
        case 'auto_link':
            return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
        case 'review':
            return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
        case 'reject':
            return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
        case 'identity_bridge':
            return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
        default:
            return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
};

const getQualityWarningLabel = (warning: string) => {
    switch (warning) {
        case 'truncation_risk':
            return 'Truncation Risk';
        case 'length_mismatch':
            return 'Length Mismatch';
        case 'extra_text':
            return 'Extra Text';
        case 'case_only':
            return 'Case Only';
        default:
            return warning;
    }
};

const getQualityWarningIcon = (warning: string) => {
    switch (warning) {
        case 'truncation_risk':
        case 'length_mismatch':
            return <AlertTriangle className="h-3 w-3" />;
        case 'extra_text':
        case 'case_only':
            return <Info className="h-3 w-3" />;
        default:
            return <AlertCircle className="h-3 w-3" />;
    }
};

const getEdgeCaseLabel = (edgeCase: string) => {
    switch (edgeCase) {
        case 'near_auto_threshold':
            return 'Near Auto Threshold';
        case 'near_review_threshold':
            return 'Near Review Threshold';
        default:
            return edgeCase;
    }
};

const getEdgeCaseDescription = (edgeCase: string) => {
    switch (edgeCase) {
        case 'near_auto_threshold':
            return 'Within 5% of auto-link threshold - small changes could affect this match';
        case 'near_review_threshold':
            return 'Within 5% of review threshold - small changes could affect this match';
        default:
            return '';
    }
};

const renderSample = (sample: MatchSample, thresholds: { artist_auto: number; artist_review: number; title_auto: number; title_review: number }) => {
    const bestCandidate = sample.candidates[0];
    if (!bestCandidate) return null;

    const artistSim = bestCandidate.artist_sim * 100;
    const titleSim = bestCandidate.title_sim * 100;
    const minSim = Math.min(artistSim, titleSim);
    const hasWarnings = bestCandidate.quality_warnings && bestCandidate.quality_warnings.length > 0;

    return (
        <div
            key={sample.id}
            className={`border rounded-lg p-3 space-y-2 hover:bg-muted/50 transition-colors ${hasWarnings ? 'border-orange-300 dark:border-orange-700' : ''}`}
        >
            {/* Broadcast data */}
            <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">
                        {sample.raw_artist} - {sample.raw_title}
                    </div>
                </div>
            </div>

            {/* Best match with prominent similarity scores */}
            <div className="space-y-1">
                <div className="text-xs text-muted-foreground">
                    Best Match: <span className="font-medium">{bestCandidate.artist} - {bestCandidate.title}</span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Artist:</span>
                        <span className="text-sm font-bold text-foreground">
                            {artistSim.toFixed(1)}%
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Title:</span>
                        <span className="text-sm font-bold text-foreground">
                            {titleSim.toFixed(1)}%
                        </span>
                    </div>
                    <span className="text-xs text-muted-foreground">({bestCandidate.match_type})</span>
                </div>

                {/* Quality warnings */}
                {hasWarnings && (
                    <div className="flex flex-wrap gap-1 mt-2">
                        {bestCandidate.quality_warnings!.map((warning, idx) => (
                            <Badge key={idx} variant="outline" className="text-xs bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300 border-orange-300">
                                <span className="flex items-center gap-1">
                                    {getQualityWarningIcon(warning)}
                                    {getQualityWarningLabel(warning)}
                                </span>
                            </Badge>
                        ))}
                    </div>
                )}

                {/* Edge case warning */}
                {bestCandidate.edge_case && (
                    <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-700 rounded-md">
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-semibold text-amber-900 dark:text-amber-100">
                                    {getEdgeCaseLabel(bestCandidate.edge_case)}
                                </div>
                                <div className="text-xs text-amber-700 dark:text-amber-300 mt-0.5">
                                    {getEdgeCaseDescription(bestCandidate.edge_case)}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export const ExampleMatches: React.FC<ExampleMatchesProps> = ({ samples, loading, onRefresh, thresholds }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['auto_link', 'review']));

    // Group samples by category for stratified display
    const groupedSamples = {
        identity_bridge: samples.filter(s => s.category === 'identity_bridge'),
        auto_link: samples.filter(s => s.category === 'auto_link'),
        review: samples.filter(s => s.category === 'review'),
        reject: samples.filter(s => s.category === 'reject'),
    };

    // Count edge cases
    const edgeCaseCount = samples.filter(s =>
        s.candidates && s.candidates.length > 0 && s.candidates[0].edge_case
    ).length;

    const toggleCategory = (category: string) => {
        const newExpanded = new Set(expandedCategories);
        if (newExpanded.has(category)) {
            newExpanded.delete(category);
        } else {
            newExpanded.add(category);
        }
        setExpandedCategories(newExpanded);
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                        <div className="h-4 w-4 bg-muted rounded animate-pulse"></div>
                        <div className="h-4 bg-muted rounded w-32 animate-pulse"></div>
                    </CardTitle>
                </CardHeader>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <CardTitle className="text-sm font-medium">
                            Example Matches ({samples.length})
                        </CardTitle>
                        {edgeCaseCount > 0 && (
                            <Badge variant="outline" className="bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300 border-amber-300">
                                <AlertTriangle className="h-3 w-3 mr-1" />
                                {edgeCaseCount} Edge Case{edgeCaseCount !== 1 ? 's' : ''}
                            </Badge>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <Button variant="ghost" size="sm" onClick={onRefresh}>
                            Refresh
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsExpanded(!isExpanded)}
                        >
                            {isExpanded ? (
                                <>
                                    <ChevronUp className="h-4 w-4 mr-1" />
                                    Hide
                                </>
                            ) : (
                                <>
                                    <ChevronDown className="h-4 w-4 mr-1" />
                                    Show
                                </>
                            )}
                        </Button>
                    </div>
                </div>
                {edgeCaseCount > 0 && (
                    <p className="text-xs text-muted-foreground mt-2">
                        ⚠️ {edgeCaseCount} match{edgeCaseCount !== 1 ? 'es are' : ' is'} within 5% of a threshold boundary. Small threshold changes could affect these matches.
                    </p>
                )}
            </CardHeader>

            {isExpanded && (
                <CardContent className="space-y-4">
                    {samples.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            No example matches available. Click "Refresh" to load samples.
                        </p>
                    ) : (
                        <>
                            {/* Helper text */}
                            <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg space-y-1">
                                <p className="font-medium">Understanding Threshold Boundaries:</p>
                                <p>These examples show 10-15 matches per category to help you see patterns and variety.</p>
                                <p className="flex items-center gap-1 text-orange-600 dark:text-orange-400">
                                    <AlertTriangle className="h-3 w-3" />
                                    <span className="font-medium">Quality warnings</span> flag potentially problematic matches (truncation, length mismatch, extra text).
                                </p>
                            </div>

                            {/* Identity Bridge matches */}
                            {groupedSamples.identity_bridge.length > 0 && (
                                <div className="space-y-2">
                                    <button
                                        onClick={() => toggleCategory('identity_bridge')}
                                        className="w-full text-left"
                                    >
                                        <h4 className="text-xs font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1 hover:underline">
                                            {expandedCategories.has('identity_bridge') ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                            <Link2 className="h-3 w-3" />
                                            Pre-Verified Mappings ({groupedSamples.identity_bridge.length})
                                        </h4>
                                    </button>
                                    {expandedCategories.has('identity_bridge') && groupedSamples.identity_bridge.map((sample) => renderSample(sample, thresholds))}
                                </div>
                            )}

                            {/* Auto-link matches (just above threshold) */}
                            {groupedSamples.auto_link.length > 0 && (
                                <div className="space-y-2">
                                    <button
                                        onClick={() => toggleCategory('auto_link')}
                                        className="w-full text-left"
                                    >
                                        <h4 className="text-xs font-semibold text-green-600 dark:text-green-400 flex items-center gap-1 hover:underline">
                                            {expandedCategories.has('auto_link') ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                            <CheckCircle2 className="h-3 w-3" />
                                            Will Auto-Link ({groupedSamples.auto_link.length})
                                            <span className="text-muted-foreground font-normal">
                                                - Above {(thresholds.artist_auto * 100).toFixed(0)}% threshold
                                            </span>
                                        </h4>
                                    </button>
                                    {expandedCategories.has('auto_link') && groupedSamples.auto_link.map((sample) => renderSample(sample, thresholds))}
                                </div>
                            )}

                            {/* Review matches (between thresholds) */}
                            {groupedSamples.review.length > 0 && (
                                <div className="space-y-2">
                                    <button
                                        onClick={() => toggleCategory('review')}
                                        className="w-full text-left"
                                    >
                                        <h4 className="text-xs font-semibold text-yellow-600 dark:text-yellow-400 flex items-center gap-1 hover:underline">
                                            {expandedCategories.has('review') ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                            <AlertCircle className="h-3 w-3" />
                                            Sent to Review Queue ({groupedSamples.review.length})
                                            <span className="text-muted-foreground font-normal">
                                                - Between {(thresholds.artist_review * 100).toFixed(0)}% and {(thresholds.artist_auto * 100).toFixed(0)}%
                                            </span>
                                        </h4>
                                    </button>
                                    {expandedCategories.has('review') && groupedSamples.review.map((sample) => renderSample(sample, thresholds))}
                                </div>
                            )}

                            {/* Reject matches (below threshold) */}
                            {groupedSamples.reject.length > 0 && (
                                <div className="space-y-2">
                                    <button
                                        onClick={() => toggleCategory('reject')}
                                        className="w-full text-left"
                                    >
                                        <h4 className="text-xs font-semibold text-red-600 dark:text-red-400 flex items-center gap-1 hover:underline">
                                            {expandedCategories.has('reject') ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                            <XCircle className="h-3 w-3" />
                                            Will Be Rejected ({groupedSamples.reject.length})
                                            <span className="text-muted-foreground font-normal">
                                                - Below {(thresholds.artist_review * 100).toFixed(0)}% threshold
                                            </span>
                                        </h4>
                                    </button>
                                    {expandedCategories.has('reject') && groupedSamples.reject.map((sample) => renderSample(sample, thresholds))}
                                </div>
                            )}
                        </>
                    )}
                </CardContent>
            )}
        </Card>
    );
};

