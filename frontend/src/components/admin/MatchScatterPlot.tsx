import React, { useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
    match: any;
    candidates: MatchCandidate[];
    category: string;
    action: string;
}

interface ScatterDataPoint {
    x: number; // title_sim (0-100)
    y: number; // artist_sim (0-100)
    category: string;
    sample: MatchSample;
}

interface MatchScatterPlotProps {
    samples: MatchSample[];
    thresholds: {
        artist_auto: number;
        artist_review: number;
        title_auto: number;
        title_review: number;
    };
}

const getCategoryColor = (category: string) => {
    switch (category) {
        case 'auto_link':
            return '#22c55e'; // green
        case 'review':
            return '#eab308'; // yellow
        case 'reject':
            return '#ef4444'; // red
        case 'identity_bridge':
            return '#3b82f6'; // blue
        default:
            return '#9ca3af'; // gray
    }
};

export const MatchScatterPlot: React.FC<MatchScatterPlotProps> = ({ samples, thresholds }) => {
    const [selectedPoint, setSelectedPoint] = useState<ScatterDataPoint | null>(null);

    // Transform samples into scatter plot data
    const scatterData: ScatterDataPoint[] = samples
        .filter(s => s.candidates && s.candidates.length > 0 && s.category)
        .map(sample => ({
            x: sample.candidates[0].title_sim * 100,
            y: sample.candidates[0].artist_sim * 100,
            category: sample.category || 'unknown',
            sample: sample,
        }));

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length > 0) {
            const point: ScatterDataPoint = payload[0].payload;
            if (!point || !point.sample || !point.category) {
                return null;
            }
            return (
                <div className="bg-background border border-border rounded-lg p-3 shadow-lg">
                    <div className="text-xs font-semibold mb-1">
                        {point.sample.raw_artist} - {point.sample.raw_title}
                    </div>
                    <div className="text-xs text-muted-foreground mb-2">
                        → {point.sample.candidates[0].artist} - {point.sample.candidates[0].title}
                    </div>
                    <div className="flex gap-3 text-xs">
                        <span>Artist: <strong>{point.y.toFixed(1)}%</strong></span>
                        <span>Title: <strong>{point.x.toFixed(1)}%</strong></span>
                    </div>
                    <Badge
                        variant="outline"
                        className="mt-2 text-xs"
                        style={{
                            backgroundColor: getCategoryColor(point.category) + '20',
                            borderColor: getCategoryColor(point.category),
                            color: getCategoryColor(point.category)
                        }}
                    >
                        {(point.category || 'unknown').replace('_', ' ').toUpperCase()}
                    </Badge>
                </div>
            );
        }
        return null;
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-sm font-medium">2D Threshold Visualization</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                    Each dot represents a match. Position shows artist (Y) and title (X) similarity. Lines show thresholds.
                </p>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Legend */}
                    <div className="flex flex-wrap gap-3 text-xs">
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3b82f6' }}></div>
                            <span>Identity Bridge</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#22c55e' }}></div>
                            <span>Auto-Link</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#eab308' }}></div>
                            <span>Review</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ef4444' }}></div>
                            <span>Reject</span>
                        </div>
                    </div>

                    {/* Scatter Plot */}
                    <ResponsiveContainer width="100%" height={400}>
                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis 
                                type="number" 
                                dataKey="x" 
                                name="Title Similarity" 
                                unit="%" 
                                domain={[40, 100]}
                                label={{ value: 'Title Similarity →', position: 'bottom', offset: 0 }}
                            />
                            <YAxis 
                                type="number" 
                                dataKey="y" 
                                name="Artist Similarity" 
                                unit="%" 
                                domain={[40, 100]}
                                label={{ value: 'Artist Similarity ↑', angle: -90, position: 'left' }}
                            />
                            <Tooltip content={<CustomTooltip />} />

                            {/* Threshold Lines */}
                            {/* Artist Auto Threshold (horizontal green line) */}
                            <ReferenceLine
                                y={thresholds.artist_auto * 100}
                                stroke="#22c55e"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                label={{ value: `Artist Auto: ${(thresholds.artist_auto * 100).toFixed(0)}%`, position: 'left', fill: '#22c55e' }}
                            />

                            {/* Artist Review Threshold (horizontal yellow line) */}
                            <ReferenceLine
                                y={thresholds.artist_review * 100}
                                stroke="#eab308"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                label={{ value: `Artist Review: ${(thresholds.artist_review * 100).toFixed(0)}%`, position: 'left', fill: '#eab308' }}
                            />

                            {/* Title Auto Threshold (vertical green line) */}
                            <ReferenceLine
                                x={thresholds.title_auto * 100}
                                stroke="#22c55e"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                label={{ value: `Title Auto: ${(thresholds.title_auto * 100).toFixed(0)}%`, position: 'top', fill: '#22c55e' }}
                            />

                            {/* Title Review Threshold (vertical yellow line) */}
                            <ReferenceLine
                                x={thresholds.title_review * 100}
                                stroke="#eab308"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                label={{ value: `Title Review: ${(thresholds.title_review * 100).toFixed(0)}%`, position: 'top', fill: '#eab308' }}
                            />

                            {/* Scatter points */}
                            <Scatter
                                data={scatterData}
                                fill="#8884d8"
                                onClick={(data) => setSelectedPoint(data)}
                            >
                                {scatterData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={getCategoryColor(entry.category)} />
                                ))}
                            </Scatter>
                        </ScatterChart>
                    </ResponsiveContainer>

                    {/* Selected Point Details */}
                    {selectedPoint && (
                        <div className="border rounded-lg p-3 bg-muted/50">
                            <div className="text-xs font-semibold mb-2">Selected Match Details</div>
                            <div className="space-y-1 text-xs">
                                <div><strong>Raw:</strong> {selectedPoint.sample.raw_artist} - {selectedPoint.sample.raw_title}</div>
                                <div><strong>Match:</strong> {selectedPoint.sample.candidates[0].artist} - {selectedPoint.sample.candidates[0].title}</div>
                                <div className="flex gap-3 mt-2">
                                    <span>Artist: <strong>{selectedPoint.y.toFixed(1)}%</strong></span>
                                    <span>Title: <strong>{selectedPoint.x.toFixed(1)}%</strong></span>
                                    <span>Vector: <strong>{selectedPoint.sample.candidates[0].vector_dist.toFixed(3)}</strong></span>
                                </div>
                                <Badge
                                    variant="outline"
                                    className="mt-2"
                                    style={{
                                        backgroundColor: getCategoryColor(selectedPoint.category) + '20',
                                        borderColor: getCategoryColor(selectedPoint.category),
                                        color: getCategoryColor(selectedPoint.category)
                                    }}
                                >
                                    {selectedPoint.category.replace('_', ' ').toUpperCase()}
                                </Badge>
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

