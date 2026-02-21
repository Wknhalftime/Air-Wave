import React from 'react';
import { Button } from '@/components/ui/button';
import { Info } from 'lucide-react';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';

interface Thresholds {
    artist_auto: number;
    artist_review: number;
    title_auto: number;
    title_review: number;
}

interface Preset {
    name: string;
    description: string;
    thresholds: Thresholds;
    variant: 'default' | 'secondary' | 'outline';
}

const PRESETS: Preset[] = [
    {
        name: 'Conservative',
        description: 'High confidence required - fewer auto-links, more manual review. Use if your data has inconsistencies.',
        thresholds: {
            artist_auto: 0.90,
            artist_review: 0.75,
            title_auto: 0.85,
            title_review: 0.70,
        },
        variant: 'outline',
    },
    {
        name: 'Balanced',
        description: 'Recommended for most users - good balance of automation and accuracy.',
        thresholds: {
            artist_auto: 0.85,
            artist_review: 0.70,
            title_auto: 0.80,
            title_review: 0.65,
        },
        variant: 'default',
    },
    {
        name: 'Aggressive',
        description: 'More auto-links - use if your data is clean and consistent.',
        thresholds: {
            artist_auto: 0.75,
            artist_review: 0.60,
            title_auto: 0.70,
            title_review: 0.55,
        },
        variant: 'outline',
    },
];

interface PresetButtonsProps {
    currentThresholds: Thresholds;
    onPresetSelect: (thresholds: Thresholds) => void;
}

export const PresetButtons: React.FC<PresetButtonsProps> = ({
    currentThresholds,
    onPresetSelect,
}) => {
    // Check if current thresholds match a preset
    const isPresetActive = (preset: Preset) => {
        return (
            Math.abs(currentThresholds.artist_auto - preset.thresholds.artist_auto) < 0.01 &&
            Math.abs(currentThresholds.artist_review - preset.thresholds.artist_review) < 0.01 &&
            Math.abs(currentThresholds.title_auto - preset.thresholds.title_auto) < 0.01 &&
            Math.abs(currentThresholds.title_review - preset.thresholds.title_review) < 0.01
        );
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <h3 className="text-sm font-medium">Quick Presets</h3>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                            <p>
                                Choose a preset to quickly set all thresholds, or manually adjust
                                the sliders below for custom settings.
                            </p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>

            <div className="flex gap-2 flex-wrap">
                {PRESETS.map((preset) => {
                    const isActive = isPresetActive(preset);
                    return (
                        <TooltipProvider key={preset.name}>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant={isActive ? 'default' : preset.variant}
                                        size="sm"
                                        onClick={() => onPresetSelect(preset.thresholds)}
                                        className={isActive ? 'ring-2 ring-primary ring-offset-2' : ''}
                                    >
                                        {preset.name}
                                        {isActive && ' ✓'}
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent className="max-w-xs">
                                    <p className="font-semibold mb-1">{preset.name}</p>
                                    <p className="text-xs mb-2">{preset.description}</p>
                                    <div className="text-xs space-y-1">
                                        <div>Artist Auto: {(preset.thresholds.artist_auto * 100).toFixed(0)}%</div>
                                        <div>Artist Review: {(preset.thresholds.artist_review * 100).toFixed(0)}%</div>
                                        <div>Title Auto: {(preset.thresholds.title_auto * 100).toFixed(0)}%</div>
                                        <div>Title Review: {(preset.thresholds.title_review * 100).toFixed(0)}%</div>
                                    </div>
                                </TooltipContent>
                            </Tooltip>
                        </TooltipProvider>
                    );
                })}
                
                {/* Custom indicator */}
                {!PRESETS.some(isPresetActive) && (
                    <Button variant="secondary" size="sm" disabled>
                        Custom ✓
                    </Button>
                )}
            </div>
        </div>
    );
};

