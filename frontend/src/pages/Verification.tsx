import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { CheckCircle2, Layers, List, Search } from 'lucide-react';
import { useState, useEffect } from 'react';
import IdentityProposals from '../components/verification/IdentityProposals';
import FocusDeck from '../components/verification/FocusDeck';
import SearchDrawer from '../components/verification/SearchDrawer';

import type { QueueItem } from '../types';

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
    const [matchMode, setMatchMode] = useState<'deck' | 'list'>('deck');
    const [processingId, setProcessingId] = useState<string | null>(null);

    // Search drawer state
    const [isSearchDrawerOpen, setIsSearchDrawerOpen] = useState(false);
    const [searchingForItem, setSearchingForItem] = useState<QueueItem | null>(null);

    // Batch selection state (Story 3.4)
    const [selectedSignatures, setSelectedSignatures] = useState<Set<string>>(new Set());
    const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

    const { data: queueItems, isLoading: isLoadingQueue } = useQuery({
        queryKey: ['discovery', 'queue'],
        queryFn: () => fetcher<QueueItem[]>('/discovery/queue?limit=100'),
    });

    const { data: pendingSplits, isLoading: isLoadingSplits } = useQuery({
        queryKey: ['identity', 'splits', 'pending'],
        queryFn: () => fetcher<ProposedSplit[]>('/identity/splits/pending'),
        enabled: view === 'identity'
    });

    const linkMutation = useMutation({
        mutationFn: (item: QueueItem) => fetcher('/discovery/link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                signature: item.signature,
                recording_id: item.suggested_recording_id,
            }),
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
        }
    });

    const dismissMutation = useMutation({
        mutationFn: (signature: string) => fetcher(`/discovery/${encodeURIComponent(signature)}`, {
            method: 'DELETE',
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
        }
    });

    const promoteMutation = useMutation({
        mutationFn: (item: QueueItem) => fetcher('/discovery/promote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signature: item.signature }),
        }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
        }
    });

    // Handlers for deck actions
    const handleDeckAction = (item: QueueItem, action: 'link' | 'skip' | 'publish') => {
        // Optimistic Update: Remove from list immediately to trigger exit animation
        queryClient.setQueryData(['discovery', 'queue'], (old: QueueItem[] | undefined) => {
            if (!old) return [];
            return old.filter(i => i.signature !== item.signature);
        });

        // Trigger Mutation
        if (action === 'link') linkMutation.mutate(item);
        else if (action === 'skip') dismissMutation.mutate(item.signature);
        else if (action === 'publish') promoteMutation.mutate(item);
    };

    const handleOpenSearch = (item: QueueItem) => {
        setSearchingForItem(item);
        setIsSearchDrawerOpen(true);
    };

    const handleSearchSelect = (recording: { id: number; artist: string; title: string }) => {
        if (!searchingForItem) return;

        // Update the queue item with the selected recording
        queryClient.setQueryData(['discovery', 'queue'], (old: QueueItem[] | undefined) => {
            if (!old) return [];
            return old.map(item => {
                if (item.signature === searchingForItem.signature) {
                    return {
                        ...item,
                        suggested_recording_id: recording.id,
                        suggested_recording: {
                            id: recording.id,
                            title: recording.title,
                            work: {
                                artist: {
                                    name: recording.artist
                                }
                            }
                        }
                    };
                }
                return item;
            });
        });

        setIsSearchDrawerOpen(false);
        setSearchingForItem(null);
    };

    // Batch selection handlers (Story 3.4)
    const handleToggleSelect = (signature: string) => {
        setSelectedSignatures(prev => {
            const next = new Set(prev);
            if (next.has(signature)) {
                next.delete(signature);
            } else {
                next.add(signature);
            }
            return next;
        });
    };

    const handleToggleSelectAll = () => {
        if (!queueItems) return;
        if (selectedSignatures.size === queueItems.length) {
            setSelectedSignatures(new Set());
        } else {
            setSelectedSignatures(new Set(queueItems.map(item => item.signature)));
        }
    };

    const handleBulkLink = async () => {
        if (!queueItems) return;
        const selectedItems = queueItems.filter(item => selectedSignatures.has(item.signature));

        // Check all have suggestions
        const allHaveSuggestions = selectedItems.every(item => item.suggested_recording_id);
        if (!allHaveSuggestions) {
            alert('All selected items must have suggestions to bulk link');
            return;
        }

        setProcessingIds(new Set(selectedItems.map(i => i.signature)));

        const results = await Promise.allSettled(
            selectedItems.map(item =>
                fetcher('/discovery/link', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        signature: item.signature,
                        recording_id: item.suggested_recording_id,
                    }),
                })
            )
        );

        const successCount = results.filter(r => r.status === 'fulfilled').length;
        const failedCount = results.filter(r => r.status === 'rejected').length;

        if (failedCount === 0) {
            alert(`✅ Linked ${successCount} of ${selectedItems.length} tracks`);
        } else {
            alert(`⚠️ Linked ${successCount} of ${selectedItems.length}. ${failedCount} failed.`);
        }

        setProcessingIds(new Set());
        setSelectedSignatures(new Set());
        queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
    };

    const handleBulkIgnore = async () => {
        if (!queueItems) return;
        const selectedItems = queueItems.filter(item => selectedSignatures.has(item.signature));

        setProcessingIds(new Set(selectedItems.map(i => i.signature)));

        const results = await Promise.allSettled(
            selectedItems.map(item =>
                fetcher(`/discovery/${encodeURIComponent(item.signature)}`, {
                    method: 'DELETE',
                })
            )
        );

        const successCount = results.filter(r => r.status === 'fulfilled').length;
        const failedCount = results.filter(r => r.status === 'rejected').length;

        if (failedCount === 0) {
            alert(`✅ Ignored ${successCount} of ${selectedItems.length} tracks`);
        } else {
            alert(`⚠️ Ignored ${successCount} of ${selectedItems.length}. ${failedCount} failed.`);
        }

        setProcessingIds(new Set());
        setSelectedSignatures(new Set());
        queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
    };

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            // Deck Mode Shortcuts
            if (view === 'matches' && matchMode === 'deck' && queueItems && queueItems.length > 0) {
                const currentItem = queueItems[0];
                if (processingId) return;

                switch (e.key.toLowerCase()) {
                    case 'arrowright':
                        if (currentItem.suggested_recording_id) {
                            handleDeckAction(currentItem, 'link');
                        }
                        break;
                    case 'arrowleft':
                        handleDeckAction(currentItem, 'skip');
                        break;
                    case 's':
                        handleOpenSearch(currentItem);
                        break;
                    case 'p':
                        handleDeckAction(currentItem, 'publish');
                        break;
                }
            }

            // List Mode Shortcuts (Story 3.4)
            if (view === 'matches' && matchMode === 'list' && queueItems && queueItems.length > 0) {
                if (e.ctrlKey || e.metaKey) {
                    switch (e.key.toLowerCase()) {
                        case 'a':
                            e.preventDefault();
                            handleToggleSelectAll();
                            break;
                        case 'd':
                            e.preventDefault();
                            setSelectedSignatures(new Set());
                            break;
                    }
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [queueItems, view, matchMode, processingId]);

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
                        Matches ({queueItems?.length || 0})
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
                    <>
                        {/* View Toggle */}
                        <div className="flex justify-between items-center bg-white p-2 rounded-lg border border-gray-200 shadow-sm mb-4">
                            <div className="text-sm text-gray-500 font-medium px-2">
                                {queueItems?.length || 0} items in queue
                            </div>
                            <div className="flex bg-gray-100 p-0.5 rounded-md">
                                <button
                                    onClick={() => setMatchMode('deck')}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${matchMode === 'deck' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                                    title="Focus Deck (Fast Mode)"
                                >
                                    <Layers className="w-4 h-4" /> Deck
                                </button>
                                <button
                                    onClick={() => setMatchMode('list')}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${matchMode === 'list' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                                    title="List View (Batch Mode)"
                                >
                                    <List className="w-4 h-4" /> List
                                </button>
                                <button
                                    onClick={() => queueItems && queueItems.length > 0 && handleOpenSearch(queueItems[0])}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium text-gray-500 hover:text-gray-700 transition-all"
                                    title="Search Library (S)"
                                    disabled={!queueItems || queueItems.length === 0}
                                >
                                    <Search className="w-4 h-4" /> Search
                                </button>
                            </div>
                        </div>

                        {/* Content Area */}
                        {isLoadingQueue ? (
                            <div className="p-8 text-center text-gray-500">Loading discovery queue...</div>
                        ) : matchMode === 'deck' ? (
                            <FocusDeck
                                items={queueItems || []}
                                onAction={handleDeckAction}
                                onSearch={handleOpenSearch}
                                processingId={processingId}
                            />
                        ) : !queueItems || queueItems.length === 0 ? (
                            <div className="text-center py-20 text-gray-400">
                                <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                                <h2 className="text-xl font-medium text-gray-600">Queue Cleared!</h2>
                                <p>No unmatched logs found.</p>
                            </div>
                        ) : (
                            // List View with Batch Selection (Story 3.4)
                            <div className="space-y-2">
                                {queueItems.map((item) => {
                                    const isSelected = selectedSignatures.has(item.signature);
                                    const isProcessing = processingIds.has(item.signature);
                                    const apiArtist = item.suggested_recording?.work?.artist?.name || "No suggestion";
                                    const apiTitle = item.suggested_recording?.title || "";

                                    return (
                                        <div
                                            key={item.signature}
                                            className={`
                                                bg-white rounded-lg shadow-sm border border-gray-200 p-4
                                                transition-all duration-200
                                                ${isSelected ? 'bg-blue-50 border-blue-300' : 'hover:shadow-md'}
                                                ${isProcessing ? 'opacity-50 pointer-events-none' : ''}
                                            `}
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Checkbox */}
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => handleToggleSelect(item.signature)}
                                                    className="mt-1 w-5 h-5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                                />

                                                {/* Content */}
                                                <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    {/* Raw Data */}
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Raw Data</div>
                                                        <div className="font-semibold text-gray-900">{item.raw_title}</div>
                                                        <div className="text-sm text-gray-600">{item.raw_artist}</div>
                                                    </div>

                                                    {/* Suggested Match */}
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Suggested Match</div>
                                                        <div className="font-semibold text-gray-900">{apiTitle}</div>
                                                        <div className="text-sm text-gray-600">{apiArtist}</div>
                                                    </div>
                                                </div>

                                                {/* Individual Actions */}
                                                {item.suggested_recording_id && (
                                                    <button
                                                        onClick={() => {
                                                            queryClient.setQueryData(['discovery', 'queue'], (old: QueueItem[] | undefined) => {
                                                                if (!old) return [];
                                                                return old.filter(i => i.signature !== item.signature);
                                                            });
                                                            linkMutation.mutate(item);
                                                        }}
                                                        className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                                                    >
                                                        Link
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}

                        {/* Bulk Action Footer (Story 3.4) - THIS IS THE KEY FIX! */}
                        {matchMode === 'list' && selectedSignatures.size > 0 && (
                            <div className="fixed bottom-0 left-0 right-0 backdrop-blur-sm bg-white/90 border-t border-gray-200 shadow-lg p-4 transition-transform duration-300 ease-out">
                                <div className="max-w-7xl mx-auto flex items-center justify-between">
                                    <div className="text-sm font-medium text-gray-700">
                                        {selectedSignatures.size} item{selectedSignatures.size > 1 ? 's' : ''} selected
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <button
                                            onClick={handleBulkLink}
                                            disabled={!queueItems?.filter(item => selectedSignatures.has(item.signature)).every(item => item.suggested_recording_id)}
                                            className="px-6 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                        >
                                            Bulk Link
                                        </button>
                                        <button
                                            onClick={handleBulkIgnore}
                                            className="px-6 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 transition-colors"
                                        >
                                            Bulk Ignore
                                        </button>
                                        <button
                                            onClick={() => setSelectedSignatures(new Set())}
                                            className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
                                        >
                                            Clear Selection
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    isLoadingSplits ? (
                        <div className="p-8 text-center text-gray-500">Loading identity proposals...</div>
                    ) : (
                        <IdentityProposals />
                    )
                )}
            </div>

            {/* SearchDrawer - Available for both Deck and List views */}
            <SearchDrawer
                isOpen={isSearchDrawerOpen}
                onClose={() => {
                    setIsSearchDrawerOpen(false);
                    setSearchingForItem(null);
                }}
                onSelect={handleSearchSelect}
                initialQuery={searchingForItem ? `${searchingForItem.raw_artist.trim()} ${searchingForItem.raw_title.trim()}` : ''}
            />
        </div>
    );
}
