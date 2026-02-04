import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Check, X, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { useState, useEffect } from 'react';


interface PendingMatch {
    id: number;
    played_at: string;
    station: string;
    raw_artist: string;
    raw_title: string;
    match_reason: string;
    track: {
        id: number;
        artist: string;
        title: string;
        path: string;
    };
}

interface ProposedSplit {
    id: number;
    raw_artist: string;
    proposed_artists: string[];
    status: string;
    confidence: number;
    created_at: string;
}

export default function Verification() {
    const queryClient = useQueryClient();
    const [view, setView] = useState<'matches' | 'identity'>('matches');
    const [processingId, setProcessingId] = useState<number | null>(null);
    const [processingAction, setProcessingAction] = useState<'confirm' | 'reject' | null>(null);
    const [batchSelections, setBatchSelections] = useState<Record<number, boolean>>({});

    const { data: matches, isLoading: isLoadingMatches } = useQuery({
        queryKey: ['matches', 'pending'],
        queryFn: () => fetcher<PendingMatch[]>('/library/matches/pending?limit=50'),
    });

    const { data: pendingSplits, isLoading: isLoadingSplits } = useQuery({
        queryKey: ['identity', 'splits', 'pending'],
        queryFn: () => fetcher<ProposedSplit[]>('/identity/splits/pending'),
        enabled: view === 'identity'
    });

    const verifyMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/library/matches/${id}/verify?apply_to_artist=${!!batchSelections[id]}`, { method: 'POST' }),
        onMutate: (id) => {
            setProcessingId(id);
            setProcessingAction('confirm');
        },
        onSuccess: (_, id) => {
            setTimeout(() => {
                queryClient.invalidateQueries({ queryKey: ['matches', 'pending'] });
                setProcessingId(null);
                setProcessingAction(null);
                setBatchSelections(prev => {
                    const next = { ...prev };
                    delete next[id];
                    return next;
                });
            }, 600); // Wait for animation
        }
    });

    const rejectMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/library/matches/${id}/reject?apply_to_artist=${!!batchSelections[id]}`, { method: 'POST' }),
        onMutate: (id) => {
            setProcessingId(id);
            setProcessingAction('reject');
        },
        onSuccess: (_, id) => {
            setTimeout(() => {
                queryClient.invalidateQueries({ queryKey: ['matches', 'pending'] });
                setProcessingId(null);
                setProcessingAction(null);
                setBatchSelections(prev => {
                    const next = { ...prev };
                    delete next[id];
                    return next;
                });
            }, 600); // Wait for animation
        }
    });

    const confirmSplitMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/identity/splits/${id}/confirm`, { method: 'POST' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'splits', 'pending'] });
        }
    });

    const rejectSplitMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/identity/splits/${id}/reject`, { method: 'POST' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'splits', 'pending'] });
        }
    });

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Ignore if input/textarea is focused (though we don't have many here)
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            if (view === 'matches' && matches && matches.length > 0) {
                const topMatch = matches[0];
                if (processingId) return; // Ignore if busy

                switch (e.key) {
                    case 'ArrowRight':
                        verifyMutation.mutate(topMatch.id);
                        break;
                    case 'ArrowLeft':
                        rejectMutation.mutate(topMatch.id);
                        break;
                    case ' ':
                        e.preventDefault(); // Prevent scroll
                        setBatchSelections(prev => ({
                            ...prev,
                            [topMatch.id]: !prev[topMatch.id]
                        }));
                        break;
                    case 'Escape':
                        setBatchSelections({});
                        break;
                }
            } else if (view === 'identity' && pendingSplits && pendingSplits.length > 0) {
                const topSplit = pendingSplits[0];
                // Can add Identity shortcuts?
                // Right -> Confirm, Left -> Reject
                switch (e.key) {
                    case 'ArrowRight':
                        confirmSplitMutation.mutate(topSplit.id);
                        break;
                    case 'ArrowLeft':
                        rejectSplitMutation.mutate(topSplit.id);
                        break;
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [matches, pendingSplits, view, processingId, verifyMutation, rejectMutation, confirmSplitMutation, rejectSplitMutation]);

    return (
        <div className="space-y-6">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Verification Hub</h1>
                    <p className="text-gray-500">Review automated matches and resolve artist identity splits.</p>
                </div>
                <div className="flex bg-gray-100 p-1 rounded-lg">
                    <button
                        onClick={() => setView('matches')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${view === 'matches' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Matches ({matches?.length || 0})
                    </button>
                    <button
                        onClick={() => setView('identity')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${view === 'identity' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Identity ({pendingSplits?.length || 0})
                    </button>
                </div>
            </header>

            <div className="space-y-4">
                {view === 'matches' ? (
                    isLoadingMatches ? (
                        <div className="p-8 text-center text-gray-500">Loading pending matches...</div>
                    ) : !matches || matches.length === 0 ? (
                        <div className="text-center py-20 text-gray-400">
                            <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                            <h2 className="text-xl font-medium text-gray-600">All caught up!</h2>
                            <p>No matches need review.</p>
                        </div>
                    ) : (
                        matches.map((match) => {
                            const isProcessing = processingId === match.id;
                            const isConfirming = isProcessing && processingAction === 'confirm';
                            const isRejecting = isProcessing && processingAction === 'reject';

                            return (
                                <div
                                    key={match.id}
                                    className={`
                                        bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden
                                        transition-all duration-500 ease-out
                                        ${isConfirming ? 'opacity-0 scale-95 bg-green-50 border-green-300' : ''}
                                        ${isRejecting ? 'opacity-0 scale-95 bg-red-50 border-red-300' : ''}
                                        ${!isProcessing ? 'hover:shadow-md' : ''}
                                    `}
                                >
                                    {/* Match Reason Badge - Centered Top */}
                                    <div className={`
                                        px-4 py-2 border-b flex items-center justify-center gap-2 text-xs font-medium
                                        ${match.match_reason === 'No Match Found'
                                            ? 'bg-red-50 border-red-100 text-red-700'
                                            : match.match_reason === 'Auto-Promoted Identity'
                                                ? 'bg-blue-50 border-blue-100 text-blue-700'
                                                : 'bg-gradient-to-r from-indigo-50 to-purple-50 border-indigo-100 text-indigo-700'
                                        }
                                    `}>
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        <span>{match.match_reason}</span>
                                    </div>

                                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-4 p-4">
                                        {/* Broadcast Log - Left */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-2">
                                                <div className="w-1 h-4 bg-blue-500 rounded-full"></div>
                                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Broadcast Log</span>
                                            </div>
                                            <div>
                                                <div className="font-semibold text-gray-900 text-lg">{match.raw_title}</div>
                                                <div className="text-gray-600">{match.raw_artist}</div>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-gray-500 pt-1">
                                                <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-medium">{match.station}</span>
                                                <span className="text-gray-400">•</span>
                                                <span>{new Date(match.played_at).toLocaleDateString()} {new Date(match.played_at).toLocaleTimeString()}</span>
                                            </div>
                                        </div>

                                        {/* Divider with Arrow - Center */}
                                        <div className="flex items-center justify-center">
                                            <div className="hidden lg:flex flex-col items-center gap-2">
                                                <div className="w-px h-full bg-gray-200"></div>
                                                <div className="text-gray-400">→</div>
                                                <div className="w-px h-full bg-gray-200"></div>
                                            </div>
                                            <div className="lg:hidden w-full h-px bg-gray-200"></div>
                                        </div>

                                        {/* Library Track - Right */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-2">
                                                <div className="w-1 h-4 bg-green-500 rounded-full"></div>
                                                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Library Track</span>
                                            </div>
                                            <div>
                                                <div className="font-semibold text-gray-900 text-lg">{match.track.title}</div>
                                                <div className="text-gray-600">{match.track.artist}</div>
                                            </div>
                                            <div className="text-xs pt-1 flex items-center gap-2">
                                                {match.track.path.startsWith('virtual://') ? (
                                                    <span className="bg-gray-100 text-gray-500 px-2 py-0.5 rounded font-medium border border-gray-200">
                                                        No Local File (Identity Only)
                                                    </span>
                                                ) : (
                                                    <span className="text-gray-400 font-mono truncate" title={match.track.path}>
                                                        {match.track.path}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Action Buttons - Bottom */}
                                    <div className="bg-gray-50 border-t border-gray-200 px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-3">
                                        <label className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 cursor-pointer select-none bg-white px-3 py-1.5 rounded-md border border-gray-200 hover:border-gray-300 transition-colors">
                                            <input
                                                type="checkbox"
                                                checked={!!batchSelections[match.id]}
                                                onChange={(e) => {
                                                    const val = e.target.checked;
                                                    setBatchSelections(prev => ({ ...prev, [match.id]: val }));
                                                }}
                                                className="w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                            />
                                            <span>Apply to all <strong>{match.raw_artist}</strong> ↔ <strong>{match.track.artist}</strong> matches?</span>
                                        </label>

                                        <div className="flex items-center gap-2 w-full sm:w-auto">
                                            <button
                                                onClick={() => verifyMutation.mutate(match.id)}
                                                disabled={isProcessing}
                                                className={`
                                                    flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-medium text-sm
                                                    transition-all duration-200
                                                    ${isConfirming
                                                        ? 'bg-green-600 text-white'
                                                        : 'bg-green-600 hover:bg-green-700 text-white hover:scale-105'
                                                    }
                                                    disabled:opacity-50 disabled:cursor-not-allowed
                                                `}
                                            >
                                                {isConfirming ? <CheckCircle2 className="w-4 h-4 animate-bounce" /> : <Check className="w-4 h-4" />}
                                                {isConfirming ? 'Confirmed!' : 'Confirm'}
                                            </button>
                                            <button
                                                onClick={() => rejectMutation.mutate(match.id)}
                                                disabled={isProcessing}
                                                className={`
                                                    flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-medium text-sm
                                                    transition-all duration-200
                                                    ${isRejecting
                                                        ? 'bg-red-600 text-white'
                                                        : 'bg-white hover:bg-red-50 text-red-600 border-2 border-red-200 hover:border-red-300 hover:scale-105'
                                                    }
                                                    disabled:opacity-50 disabled:cursor-not-allowed
                                                `}
                                            >
                                                {isRejecting ? <XCircle className="w-4 h-4 animate-bounce" /> : <X className="w-4 h-4" />}
                                                {isRejecting ? 'Rejected!' : 'Reject'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )
                ) : (
                    isLoadingSplits ? (
                        <div className="p-8 text-center text-gray-500">Loading identity proposals...</div>
                    ) : !pendingSplits || pendingSplits.length === 0 ? (
                        <div className="text-center py-20 text-gray-400">
                            <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                            <h2 className="text-xl font-medium text-gray-600">No identity resolutions needed</h2>
                            <p>Everything is correctly aligned.</p>
                        </div>
                    ) : (
                        pendingSplits.map((split) => (
                            <div key={split.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col md:flex-row items-center justify-between gap-6">
                                <div className="space-y-3 flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-bold text-orange-500 uppercase tracking-wider bg-orange-50 px-2 py-0.5 rounded">Proposed Artist Split</span>
                                        <span className="text-xs text-gray-400">•</span>
                                        <span className="text-xs text-gray-500">Confidence: {(split.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="text-lg font-bold text-gray-400 line-through decoration-red-300 decoration-2">{split.raw_artist}</div>
                                        <div className="text-gray-400">→</div>
                                        <div className="flex flex-wrap gap-2">
                                            {split.proposed_artists.map((artist, idx) => (
                                                <span key={idx} className="bg-green-100 text-green-700 font-bold px-3 py-1 rounded-md border border-green-200 shadow-sm">
                                                    {artist}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <p className="text-sm text-gray-500 italic">Heuristic pattern matching identified multiple distinct entities in this string.</p>
                                </div>
                                <div className="flex items-center gap-3 w-full md:w-auto">
                                    <button
                                        onClick={() => confirmSplitMutation.mutate(split.id)}
                                        className="flex-1 md:flex-none px-6 py-2.5 bg-green-600 text-white rounded-lg font-bold hover:bg-green-700 transition-all shadow-md hover:shadow-lg active:scale-95 flex items-center justify-center gap-2"
                                    >
                                        <Check className="w-4 h-4" /> Approve Split
                                    </button>
                                    <button
                                        onClick={() => rejectSplitMutation.mutate(split.id)}
                                        className="flex-1 md:flex-none px-6 py-2.5 bg-white text-gray-600 border border-gray-200 rounded-lg font-bold hover:bg-gray-50 transition-all active:scale-95 flex items-center justify-center gap-2"
                                    >
                                        <X className="w-4 h-4" /> Keep as One
                                    </button>
                                </div>
                            </div>
                        ))
                    )
                )}
            </div>
        </div>
    );
}
