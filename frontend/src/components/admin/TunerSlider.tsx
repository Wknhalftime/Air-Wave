import React, { useRef, useState, useEffect } from 'react';
import { cn } from '@/lib/utils'; // Standard tailwind merge

interface SamplePoint {
    id: number;
    label_a: string;
    label_b: string;
    score: number;
}

interface TunerSliderProps {
    title: string;
    autoThreshold: number;
    reviewThreshold: number;
    onChange: (auto: number, review: number) => void;
    samples: SamplePoint[];
}

export const TunerSlider: React.FC<TunerSliderProps> = ({
    title, autoThreshold, reviewThreshold, onChange, samples
}) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dragging, setDragging] = useState<'auto' | 'review' | null>(null);

    // Slider operates on 0.4-1.0 scale (40%-100%)
    const MIN_THRESHOLD = 0.4;

    // Convert value (0.4-1) to percentage position (0%-100%) on slider
    const toPct = (val: number) => {
        const normalized = (val - MIN_THRESHOLD) / (1 - MIN_THRESHOLD);
        return `${Math.max(0, Math.min(100, normalized * 100))}%`;
    };

    // Convert pixel position to value (0.4-1)
    const fromPct = (pct: number) => {
        return MIN_THRESHOLD + (pct * (1 - MIN_THRESHOLD));
    };

    const handleMouseDown = (type: 'auto' | 'review') => (e: React.MouseEvent) => {
        setDragging(type);
        e.preventDefault();
    };

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!dragging || !containerRef.current) return;

            const rect = containerRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left;
            let pctVal = x / rect.width;
            pctVal = Math.max(0, Math.min(1, pctVal));

            // Convert to actual value (0.4-1.0 range)
            let rawVal = fromPct(pctVal);

            // Constraint: Auto >= Review
            if (dragging === 'auto') {
                const newAuto = Math.max(rawVal, reviewThreshold + 0.01);
                onChange(newAuto, reviewThreshold);
            } else {
                const newReview = Math.min(rawVal, autoThreshold - 0.01);
                onChange(autoThreshold, newReview);
            }
        };

        const handleMouseUp = () => setDragging(null);

        if (dragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [dragging, autoThreshold, reviewThreshold, onChange]);

    return (
        <div className="bg-card p-6 rounded-lg shadow-sm border mb-6 select-none">
            <h3 className="text-lg font-semibold mb-2">{title}</h3>

            <div className="relative h-24 mt-8 mb-4 mx-4" ref={containerRef}>
                {/* Background Track */}
                <div className="absolute top-1/2 left-0 right-0 h-4 -mt-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-800">
                    {/* Zones */}

                    {/* Red Zone (0 to Review) */}
                    <div className="absolute h-full bg-red-100 dark:bg-red-900/30"
                        style={{ left: 0, width: toPct(reviewThreshold) }} />

                    {/* Yellow Zone (Review to Auto) */}
                    <div className="absolute h-full bg-yellow-100 dark:bg-yellow-900/30"
                        style={{
                            left: toPct(reviewThreshold),
                            width: `${((autoThreshold - reviewThreshold) / (1 - MIN_THRESHOLD)) * 100}%`
                        }} />

                    {/* Green Zone (Auto to 1) */}
                    <div className="absolute h-full bg-green-100 dark:bg-green-900/30"
                        style={{ left: toPct(autoThreshold), right: 0 }} />
                </div>

                {/* Sample Points */}
                {samples
                    .filter(s => s.score >= MIN_THRESHOLD) // Only show samples >= 40%
                    .map((s) => (
                        <div key={s.id}
                            className={cn(
                                "absolute top-12 w-2 h-4 -ml-1 rounded-full transition-colors cursor-pointer hover:scale-150",
                                s.score >= autoThreshold ? "bg-green-500" :
                                    s.score >= reviewThreshold ? "bg-yellow-500" : "bg-red-500"
                            )}
                            style={{ left: toPct(s.score) }}
                            title={`${s.label_a} ↔ ${s.label_b}\nSimilarity: ${(s.score * 100).toFixed(1)}%`}
                        />
                    ))}

                {/* Review Handle (Yellow) */}
                <div
                    className="absolute top-1/2 -mt-6 -ml-3 w-6 h-12 cursor-ew-resize z-20 group"
                    style={{ left: toPct(reviewThreshold) }}
                    onMouseDown={handleMouseDown('review')}
                >
                    <div className="w-1 h-full bg-yellow-500 mx-auto rounded-full group-hover:scale-x-150 transition-transform" />
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded border border-yellow-300 font-mono">
                        {(reviewThreshold * 100).toFixed(1)}%
                    </div>
                </div>

                {/* Auto Handle (Green) */}
                <div
                    className="absolute top-1/2 -mt-6 -ml-3 w-6 h-12 cursor-ew-resize z-20 group"
                    style={{ left: toPct(autoThreshold) }}
                    onMouseDown={handleMouseDown('auto')}
                >
                    <div className="w-1 h-full bg-green-500 mx-auto rounded-full group-hover:scale-x-150 transition-transform" />
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-green-100 text-green-800 text-xs px-2 py-1 rounded border border-green-300 font-mono">
                        {(autoThreshold * 100).toFixed(1)}%
                    </div>
                </div>
            </div>

            <div className="flex justify-between text-sm text-muted-foreground mt-8 px-4">
                <span>Mismatch (Reject)</span>
                <span>Review Needed (Flag)</span>
                <span>Match (Auto)</span>
            </div>

            {/* Live Stats */}
            <div className="mt-4 grid grid-cols-3 gap-2 text-center text-sm">
                <div className="bg-red-50 dark:bg-red-950/20 p-2 rounded">
                    Missed: {samples.filter(s => s.score < reviewThreshold).length}
                </div>
                <div className="bg-yellow-50 dark:bg-yellow-950/20 p-2 rounded">
                    Review: {samples.filter(s => s.score >= reviewThreshold && s.score < autoThreshold).length}
                </div>
                <div className="bg-green-50 dark:bg-green-950/20 p-2 rounded">
                    Auto: {samples.filter(s => s.score >= autoThreshold).length}
                </div>
            </div>
        </div>
    );
};
