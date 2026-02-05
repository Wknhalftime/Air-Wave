import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, X, CheckCircle2, Pencil, ExternalLink } from 'lucide-react';
import { fetcher } from '../../lib/api';

interface ProposedSplit {
    id: number;
    raw_artist: string;
    proposed_artists: string[];
    status: string;
    confidence: number;
    created_at: string;
}

export default function IdentityProposals() {
    const queryClient = useQueryClient();

    // Split Editing State
    const [editingSplitId, setEditingSplitId] = useState<number | null>(null);
    const [editSplitValue, setEditSplitValue] = useState('');

    const { data: pendingSplits, isLoading: isLoadingSplits } = useQuery({
        queryKey: ['identity', 'splits', 'pending'],
        queryFn: () => fetcher<ProposedSplit[]>('/identity/splits/pending'),
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

    const updateSplitMutation = useMutation({
        mutationFn: ({ id, artists }: { id: number, artists: string[] }) =>
            fetcher(`/identity/splits/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proposed_artists: artists })
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'splits', 'pending'] });
            setEditingSplitId(null);
        }
    });

    const handleStartEditSplit = (split: ProposedSplit) => {
        setEditingSplitId(split.id);
        setEditSplitValue(split.proposed_artists.join('; '));
    };

    const handleSaveSplit = () => {
        if (!editingSplitId) return;
        const artists = editSplitValue.split(';')
            .map(s => s.trim())
            .filter(s => s.length > 0);

        if (artists.length === 0) return;

        updateSplitMutation.mutate({ id: editingSplitId, artists });
    };

    if (isLoadingSplits) {
        return <div className="p-8 text-center text-gray-500">Loading identity proposals...</div>;
    }

    if (!pendingSplits || pendingSplits.length === 0) {
        return (
            <div className="text-center py-20 text-gray-400">
                <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                <h2 className="text-xl font-medium text-gray-600">No identity resolutions needed</h2>
                <p>Everything is correctly aligned.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {pendingSplits.map((split) => (
                <div key={split.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="space-y-3 flex-1">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-orange-500 uppercase tracking-wider bg-orange-50 px-2 py-0.5 rounded">Proposed Artist Split</span>
                            <span className="text-xs text-gray-400">•</span>
                            <span className="text-xs text-gray-500">Confidence: {(split.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <div className="text-lg font-bold text-gray-400 line-through decoration-red-300 decoration-2">{split.raw_artist}</div>
                                <a
                                    href={`https://www.google.com/search?q=${encodeURIComponent(split.raw_artist)} music artist`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-300 hover:text-blue-500 transition-colors"
                                    title="Search on Google"
                                >
                                    <ExternalLink className="w-4 h-4" />
                                </a>
                            </div>
                            <div className="text-gray-400">→</div>
                            <div className="flex flex-wrap gap-2 items-center">
                                {editingSplitId === split.id ? (
                                    <div className="flex items-center gap-2">
                                        <input
                                            autoFocus
                                            type="text"
                                            value={editSplitValue}
                                            onChange={(e) => setEditSplitValue(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleSaveSplit();
                                                if (e.key === 'Escape') setEditingSplitId(null);
                                            }}
                                            onBlur={handleSaveSplit}
                                            className="border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-1 w-64"
                                            placeholder="Artist A; Artist B..."
                                        />
                                        <span className="text-xs text-gray-400">Press Enter to save</span>
                                    </div>
                                ) : (
                                    <>
                                        {split.proposed_artists.map((artist, idx) => (
                                            <span key={idx} className="bg-green-100 text-green-700 font-bold px-3 py-1 rounded-md border border-green-200 shadow-sm cursor-default">
                                                {artist}
                                            </span>
                                        ))}
                                        <button
                                            onClick={() => handleStartEditSplit(split)}
                                            className="text-gray-400 hover:text-indigo-600 transition-colors bg-gray-50 hover:bg-white p-1 rounded-full border border-transparent hover:border-gray-200"
                                            title="Edit Split Tags"
                                        >
                                            <Pencil className="w-3.5 h-3.5" />
                                        </button>
                                    </>
                                )}
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
            ))}
        </div>
    );
}
