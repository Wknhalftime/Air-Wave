import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle2, AlertCircle, XCircle, Loader2, Link2 } from 'lucide-react';
import type { MatchImpactResponse } from '@/types/match-tuner';

interface ImpactSummaryProps {
    impact: MatchImpactResponse | null;
    loading: boolean;
}

export const ImpactSummary: React.FC<ImpactSummaryProps> = ({ impact, loading }) => {
    if (loading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                    <Card key={i} className="animate-pulse">
                        <CardHeader className="pb-3">
                            <div className="h-4 bg-muted rounded w-24"></div>
                        </CardHeader>
                        <CardContent>
                            <div className="h-8 bg-muted rounded w-16 mb-2"></div>
                            <div className="h-3 bg-muted rounded w-20"></div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    if (!impact) {
        return (
            <Card className="border-dashed">
                <CardContent className="pt-6 text-center text-muted-foreground">
                    <p>Click "Preview Impact" to see how your thresholds affect matching</p>
                </CardContent>
            </Card>
        );
    }

    const cards = [
        {
            title: 'Auto-Link',
            icon: CheckCircle2,
            count: impact.auto_link_count,
            percentage: impact.auto_link_percentage,
            description: 'Will be linked immediately',
            color: 'text-green-600 dark:text-green-400',
            bgColor: 'bg-green-50 dark:bg-green-950/20',
            borderColor: 'border-green-200 dark:border-green-800',
        },
        {
            title: 'Review',
            icon: AlertCircle,
            count: impact.review_count,
            percentage: impact.review_percentage,
            description: 'Need manual verification',
            color: 'text-yellow-600 dark:text-yellow-400',
            bgColor: 'bg-yellow-50 dark:bg-yellow-950/20',
            borderColor: 'border-yellow-200 dark:border-yellow-800',
        },
        {
            title: 'Reject',
            icon: XCircle,
            count: impact.reject_count,
            percentage: impact.reject_percentage,
            description: 'Below threshold',
            color: 'text-red-600 dark:text-red-400',
            bgColor: 'bg-red-50 dark:bg-red-950/20',
            borderColor: 'border-red-200 dark:border-red-800',
        },
        {
            title: 'Identity Bridge',
            icon: Link2,
            count: impact.identity_bridge_count,
            percentage: impact.identity_bridge_percentage,
            description: 'Pre-verified mappings',
            color: 'text-blue-600 dark:text-blue-400',
            bgColor: 'bg-blue-50 dark:bg-blue-950/20',
            borderColor: 'border-blue-200 dark:border-blue-800',
        },
    ];

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {cards.map((card) => {
                    const Icon = card.icon;
                    return (
                        <Card
                            key={card.title}
                            className={`${card.bgColor} ${card.borderColor} border-2`}
                        >
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Icon className={`h-4 w-4 ${card.color}`} />
                                    <span>{card.title}</span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className={`text-2xl font-bold ${card.color}`}>
                                    {card.count.toLocaleString()}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">
                                    {card.percentage.toFixed(1)}% · {card.description}
                                </p>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {/* Additional Info */}
            <div className="text-xs text-muted-foreground space-y-1">
                <p>
                    <strong>Sample Analysis:</strong> Based on {impact.sample_size.toLocaleString()} of{' '}
                    {impact.total_unmatched.toLocaleString()} unmatched logs (±3% accuracy)
                </p>
                {(impact.edge_cases.within_5pct_of_auto > 0 ||
                    impact.edge_cases.within_5pct_of_review > 0) && (
                    <p className="text-yellow-600 dark:text-yellow-400">
                        <strong>⚠️ Edge Cases:</strong>{' '}
                        {impact.edge_cases.within_5pct_of_auto > 0 &&
                            `${impact.edge_cases.within_5pct_of_auto} matches within 5% of auto threshold`}
                        {impact.edge_cases.within_5pct_of_auto > 0 &&
                            impact.edge_cases.within_5pct_of_review > 0 &&
                            ', '}
                        {impact.edge_cases.within_5pct_of_review > 0 &&
                            `${impact.edge_cases.within_5pct_of_review} matches within 5% of review threshold`}
                    </p>
                )}
            </div>
        </div>
    );
};

