import * as Diff from 'diff';
import { Check } from 'lucide-react';

/**
 * Normalizes text for comparison by collapsing whitespace and lowercasing.
 * "The  Beatles" -> "the beatles"
 */
export const normalizeForMatch = (str: string): string => {
    return (str || '').replace(/\s+/g, ' ').trim().toLowerCase();
};

/**
 * Renders a semantic diff between two strings.
 * Shows green check for perfect matches, character-level diffs otherwise.
 *
 * Rules:
 * 1. If normalized strings are identical, return Green Check (Perfect Match).
 * 2. If strings differ, render character-level diffs.
 * 3. Handle accessibility with aria-labels and clean-read sr-only text.
 * 4. Graceful error handling (fallback to plain text).
 */
export function renderDiff(localValue: string, remoteValue: string, label: string) {
    try {
        // Handle Empty/Null Explicitly
        if (!localValue || !remoteValue) {
            return (
                <span className="text-gray-400 italic">
                    {!localValue && !remoteValue ? "(Empty)" :
                        !localValue ? <span>(Empty) <span className="not-italic text-gray-500">vs</span> {remoteValue}</span> :
                            <span>{localValue} <span className="not-italic text-gray-500">vs</span> (Empty)</span>}
                </span>
            );
        }

        const cleanLocal = normalizeForMatch(localValue);
        const cleanRemote = normalizeForMatch(remoteValue);

        // Perfect Match (case/whitespace insensitive)
        if (cleanLocal === cleanRemote) {
            return (
                <span className="inline-flex items-center gap-2 text-green-700 font-medium">
                    <Check className="w-5 h-5 text-green-500" />
                    <span>{remoteValue}</span>
                </span>
            );
        }

        // Compute character-level diff
        const diff = Diff.diffChars(localValue, remoteValue);

        return (
            <span className="relative inline-block">
                {/* Screen reader text */}
                <span className="sr-only">
                    {`Difference detected for ${label}. Incoming: ${localValue}. Library Match: ${remoteValue}.`}
                </span>

                {/* Visual diff - let parent control font size/family */}
                <span className="break-words" aria-hidden="true">
                    {diff.map((part, index) => {
                        if (part.added) {
                            return (
                                <span
                                    key={index}
                                    className="bg-amber-100 text-amber-900 font-bold px-0.5 rounded"
                                    title={`Added: ${part.value}`}
                                >
                                    {part.value}
                                </span>
                            );
                        }
                        if (part.removed) {
                            // Don't show deletions in library column (confusing)
                            // The incoming column already shows the raw log data
                            return null;
                        }
                        return <span key={index}>{part.value}</span>;
                    })}
                </span>
            </span>
        );

    } catch (e) {
        console.error("Diff rendering failed", e);
        // Fail gracefully
        return <span>{remoteValue || <span className="text-gray-400 italic">(Empty)</span>}</span>;
    }
}
