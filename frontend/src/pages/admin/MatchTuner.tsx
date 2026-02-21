import React, { useEffect, useState } from 'react';
import { TunerSlider } from '@/components/admin/TunerSlider';
import { PresetButtons } from '@/components/admin/PresetButtons';
import { ImpactSummary } from '@/components/admin/ImpactSummary';
import { ExampleMatches } from '@/components/admin/ExampleMatches';
import { MatchScatterPlot } from '@/components/admin/MatchScatterPlot';
import { matchTunerApi } from '@/lib/api';
import type { MatchImpactResponse } from '@/types/match-tuner';
import { Button } from '@/components/ui/button';
import { Loader2, BarChart3, List, ScatterChart } from 'lucide-react';
import { toast } from 'sonner';
import { TaskProgress } from '@/components/TaskProgress';

interface Thresholds {
    artist_auto: number;
    artist_review: number;
    title_auto: number;
    title_review: number;
}

interface MatchCandidate {
    recording_id: number;
    artist: string;
    title: string;
    artist_sim: number;
    title_sim: number;
    vector_dist: number;
    match_type: string;
}

interface MatchSample {
    id: number;
    raw_artist: string;
    raw_title: string;
    match: { recording_id: number; reason: string } | null;
    candidates: MatchCandidate[];
}

export const MatchTuner: React.FC = () => {
    const [loading, setLoading] = useState(true);
    const [reEvaluating, setReEvaluating] = useState(false);
    const [reEvaluateTaskId, setReEvaluateTaskId] = useState<string | null>(null);
    const [thresholds, setThresholds] = useState<Thresholds>({
        artist_auto: 0.9, artist_review: 0.6,
        title_auto: 0.8, title_review: 0.6
    });
    const [samples, setSamples] = useState<MatchSample[]>([]);
    const [impact, setImpact] = useState<MatchImpactResponse | null>(null);
    const [loadingImpact, setLoadingImpact] = useState(false);
    const [viewMode, setViewMode] = useState<'list' | 'scatter'>('list');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [tData, sData] = await Promise.all([
                matchTunerApi.getThresholds(),
                matchTunerApi.getMatchSamples(10)  // Reduced from 30 to 10 for performance
            ]);
            setThresholds(tData);
            setSamples(sData);
        } catch (e) {
            toast.error("Failed to load tuner data");
        } finally {
            setLoading(false);
        }
    };

    const refreshSamples = async () => {
        // Refresh samples with current thresholds for stratified categorization
        try {
            const sData = await matchTunerApi.getMatchSamples(10, thresholds, true); // stratified=true
            setSamples(sData);
            toast.success("Samples refreshed");
        } catch (e) {
            toast.error("Failed to refresh samples");
        }
    };

    const handleSave = async () => {
        try {
            await matchTunerApi.updateThresholds(thresholds);
            toast.success("Thresholds saved!");
        } catch (e) {
            toast.error("Failed to save settings");
        }
    };

    const handleReEvaluate = async () => {
        setReEvaluating(true);
        try {
            const response = await matchTunerApi.reEvaluate();
            setReEvaluateTaskId(response.task_id);
            toast.success("Re-evaluation started!");
        } catch (e) {
            toast.error("Failed to start re-evaluation");
            setReEvaluating(false);
        }
    };

    const handlePreviewImpact = async () => {
        setLoadingImpact(true);
        try {
            const impactData = await matchTunerApi.getMatchImpact({
                ...thresholds,
                sample_size: 1000,
            });
            setImpact(impactData);
            toast.success("Impact analysis complete!");
        } catch (e) {
            toast.error("Failed to analyze impact");
        } finally {
            setLoadingImpact(false);
        }
    };

    const handlePresetSelect = (presetThresholds: Thresholds) => {
        setThresholds(presetThresholds);
        setImpact(null); // Clear impact when thresholds change
        toast.info("Preset applied - click 'Preview Impact' to see results");
    };

    // Prepare data for sliders - filter to >= 40%
    const MIN_THRESHOLD = 0.4;

    // For Artist Slider: We use the best candidate's Artist Sim Score
    const artistSamples = samples.flatMap(s => s.candidates
        .filter(c => c.artist_sim >= MIN_THRESHOLD)
        .map(c => ({
            id: s.id * 1000 + c.recording_id,
            label_a: s.raw_artist,
            label_b: c.artist,
            score: c.artist_sim
        })));

    // For Title Slider: We generally care about title sim comparisons
    const titleSamples = samples.flatMap(s => s.candidates
        .filter(c => c.title_sim >= MIN_THRESHOLD)
        .map(c => ({
            id: s.id * 1000 + c.recording_id + 1,
            label_a: s.raw_title,
            label_b: c.title,
            score: c.title_sim
        })));

    // Deduplicate? Sliders might get crowded. TunerSlider handles it visually (overlap).

    if (loading) return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>;

    return (
        <div className="container mx-auto p-6 max-w-6xl">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Match Intelligence Tuner</h1>
                    <p className="text-muted-foreground">Calibrate the sensitivity of the auto-matching engine.</p>
                </div>
                <div className="gap-2 flex">
                    <Button variant="outline" onClick={refreshSamples}>Refresh Samples</Button>
                    <Button variant="secondary" onClick={handleReEvaluate} disabled={reEvaluating}>
                        {reEvaluating ? 'Re-evaluating...' : 'Re-evaluate Matches'}
                    </Button>
                    <Button onClick={handleSave}>Save Changes</Button>
                </div>
            </header>

            {/* Preset Buttons */}
            <div className="mb-6">
                <PresetButtons
                    currentThresholds={thresholds}
                    onPresetSelect={handlePresetSelect}
                />
            </div>

            {/* Impact Summary */}
            <div className="mb-8">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold">Impact Preview</h2>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handlePreviewImpact}
                        disabled={loadingImpact}
                    >
                        {loadingImpact ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Analyzing...
                            </>
                        ) : (
                            <>
                                <BarChart3 className="mr-2 h-4 w-4" />
                                Preview Impact
                            </>
                        )}
                    </Button>
                </div>
                <ImpactSummary impact={impact} loading={loadingImpact} />
            </div>

            <TunerSlider
                title="Artist Sensitivity (Fuzzy Name Matching)"
                autoThreshold={thresholds.artist_auto}
                reviewThreshold={thresholds.artist_review}
                samples={artistSamples}
                onChange={(auto, review) => {
                    setThresholds(prev => ({ ...prev, artist_auto: auto, artist_review: review }));
                    setImpact(null); // Clear impact when thresholds change
                }}
            />

            <TunerSlider
                title="Title Tolerance (Vector & Text Matching)"
                autoThreshold={thresholds.title_auto}
                reviewThreshold={thresholds.title_review}
                samples={titleSamples}
                onChange={(auto, review) => {
                    setThresholds(prev => ({ ...prev, title_auto: auto, title_review: review }));
                    setImpact(null); // Clear impact when thresholds change
                }}
            />

            {/* Example Matches with View Toggle */}
            <div className="mb-8 space-y-4">
                {/* View Toggle */}
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">Match Examples</h3>
                    <div className="flex gap-2">
                        <Button
                            variant={viewMode === 'list' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setViewMode('list')}
                        >
                            <List className="h-4 w-4 mr-1" />
                            List View
                        </Button>
                        <Button
                            variant={viewMode === 'scatter' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setViewMode('scatter')}
                        >
                            <ScatterChart className="h-4 w-4 mr-1" />
                            2D View
                        </Button>
                    </div>
                </div>

                {/* Conditional Rendering */}
                {viewMode === 'list' ? (
                    <ExampleMatches
                        samples={samples}
                        loading={loading}
                        onRefresh={refreshSamples}
                        thresholds={thresholds}
                    />
                ) : (
                    <MatchScatterPlot
                        samples={samples}
                        thresholds={thresholds}
                    />
                )}
            </div>

            {/* Re-evaluation Progress */}
            {reEvaluateTaskId && (
                <div className="mt-8 bg-muted p-4 rounded">
                    <h4 className="font-semibold mb-2">Re-evaluation Progress</h4>
                    <TaskProgress
                        taskId={reEvaluateTaskId}
                        onComplete={() => {
                            setReEvaluateTaskId(null);
                            setReEvaluating(false);
                            toast.success("Re-evaluation complete!");
                        }}
                    />
                </div>
            )}

            <div className="mt-8 bg-muted p-4 rounded text-sm text-muted-foreground">
                <h4 className="font-semibold mb-2">How it works</h4>
                <p>
                    The tuner fetches actual unmatched logs and compares them against potential candidates.
                    Adjusting the sliders changes how strict the system is when deciding whether to
                    <strong> Auto-Match</strong> (Green) or flag for <strong>Review</strong> (Yellow).
                    Items in Red will remain Unmatched.
                </p>
            </div>
        </div>
    );
};
