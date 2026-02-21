import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { CheckCircle2, List, Search, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import { toTitleCase, formatArtistForDisplay } from '../utils/format';
import { useState, useEffect, useMemo } from 'react';
import IdentityProposals from '../components/verification/IdentityProposals';
import SearchDrawer from '../components/verification/SearchDrawer';
import VerificationHistory from '../components/verification/VerificationHistory';
import UndoBanner from '../components/verification/UndoBanner';
import { toast } from 'sonner';

type SortMode = 'count' | 'title' | 'artist-group';

import type { QueueItem, ArtistQueueItem } from '../types';

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
    const [view, setView] = useState<'artists' | 'matches' | 'identity'>('artists');
    const [matchMode, setMatchMode] = useState<'list' | 'history'>(() => {
        // Persistence: Match Mode (Story 3.1) - Initial Load
        const saved = localStorage.getItem('airwave_match_mode');
        return (saved === 'list' || saved === 'history') ? saved : 'list';
    });

    const [showOnlyWithSuggestions, setShowOnlyWithSuggestions] = useState(() => {
        const saved = localStorage.getItem('airwave_filter_has_suggestion');
        return saved === 'true';
    });

    useEffect(() => {
        localStorage.setItem('airwave_match_mode', matchMode);
    }, [matchMode]);

    useEffect(() => {
        localStorage.setItem('airwave_filter_has_suggestion', String(showOnlyWithSuggestions));
    }, [showOnlyWithSuggestions]);

    const [sortMode, setSortMode] = useState<SortMode>(() => {
        const saved = localStorage.getItem('airwave_sort_mode');
        return (saved === 'count' || saved === 'title' || saved === 'artist-group') ? saved : 'artist-group';
    });

    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

    useEffect(() => {
        localStorage.setItem('airwave_sort_mode', sortMode);
    }, [sortMode]);

    // Undo state (Story 3.5)
    const [lastAction, setLastAction] = useState<{
        auditIds: number[];
        summary: string;
    } | null>(null);

    // Search drawer state
    const [isSearchDrawerOpen, setIsSearchDrawerOpen] = useState(false);
    const [searchingForItem, setSearchingForItem] = useState<QueueItem | null>(null);

    // Batch selection state (Story 3.4)
    const [selectedSignatures, setSelectedSignatures] = useState<Set<string>>(new Set());
    const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

    const { data: queueItems, isLoading: isLoadingQueue } = useQuery({
        queryKey: ['discovery', 'queue', showOnlyWithSuggestions],
        queryFn: () => {
            const params = showOnlyWithSuggestions ? '?has_suggestion=true&limit=100' : '?limit=100';
            return fetcher<QueueItem[]>(`/discovery/queue${params}`);
        },
    });

    const { data: pendingSplits, isLoading: isLoadingSplits } = useQuery({
        queryKey: ['identity', 'splits', 'pending'],
        queryFn: () => fetcher<ProposedSplit[]>('/identity/splits/pending'),
        enabled: view === 'identity'
    });

    const { data: artistQueue, isLoading: isLoadingArtists } = useQuery({
        queryKey: ['discovery', 'artist-queue'],
        queryFn: () => fetcher<ArtistQueueItem[]>('/discovery/artist-queue'),
        enabled: view === 'artists'
    });

    const artistLinkMutation = useMutation({
        mutationFn: (params: { raw_name: string; resolved_name: string }) => 
            fetcher<{ status: string; affected_items: number }>('/discovery/artist-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            }),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'artist-queue'] });
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
            toast.success(`Linked "${variables.raw_name}" to "${variables.resolved_name}". ${data.affected_items} items will be re-matched.`);
        },
        onError: () => {
            toast.error('Failed to link artist');
        }
    });

    const sortedItems = useMemo(() => {
        if (!queueItems) return [];
        const items = [...queueItems];
        
        switch (sortMode) {
            case 'title':
                return items.sort((a, b) => a.raw_title.localeCompare(b.raw_title));
            case 'count':
                return items.sort((a, b) => b.count - a.count);
            case 'artist-group':
            default:
                return items.sort((a, b) => {
                    const artistCompare = (a.raw_artist || '').localeCompare(b.raw_artist || '');
                    if (artistCompare !== 0) return artistCompare;
                    return a.raw_title.localeCompare(b.raw_title);
                });
        }
    }, [queueItems, sortMode]);

    const groupedItems = useMemo(() => {
        if (sortMode !== 'artist-group') return null;
        
        const groups = new Map<string, QueueItem[]>();
        sortedItems.forEach(item => {
            const artist = item.raw_artist || 'Unknown Artist';
            if (!groups.has(artist)) groups.set(artist, []);
            groups.get(artist)!.push(item);
        });
        return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    }, [sortedItems, sortMode]);

    const handleToggleGroup = (artist: string) => {
        setExpandedGroups(prev => {
            const next = new Set(prev);
            if (next.has(artist)) {
                next.delete(artist);
            } else {
                next.add(artist);
            }
            return next;
        });
    };

    const handleExpandAll = () => {
        if (groupedItems) {
            setExpandedGroups(new Set(groupedItems.map(([artist]) => artist)));
        }
    };

    const handleCollapseAll = () => {
        setExpandedGroups(new Set());
    };

    const linkMutation = useMutation({
        mutationFn: (item: QueueItem) => fetcher<{ status: string, signature: string, audit_id: number }>('/discovery/link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                signature: item.signature,
                work_id: item.suggested_work_id,  // Phase 4: Send work_id instead of recording_id
            }),
        }),
        onSuccess: (data, item) => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
            setLastAction({
                auditIds: [data.audit_id],
                summary: `Linked ${item.raw_artist} - ${item.raw_title}`
            });
        }
    });

    const undoMutation = useMutation({
        mutationFn: async (auditIds: number[]) => {
            // Execute undo for all provided IDs
            const results = await Promise.allSettled(
                auditIds.map(id => fetcher(`/identity/audit/${id}/undo`, { method: 'POST' }))
            );
            return results;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
            queryClient.invalidateQueries({ queryKey: ['verification', 'audit'] });
            toast.success('Action undone');
            setLastAction(null); // Clear banner
        }
    });

    const [searchInitialQuery, setSearchInitialQuery] = useState<string>('');

    const handleOpenSearch = (item: QueueItem, initialQuery?: string) => {
        setSearchingForItem(item);
        setSearchInitialQuery(initialQuery ?? `${item.raw_artist.trim()} ${item.raw_title.trim()}`);
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
                        suggested_work_id: recording.work_id,  // Phase 4: Use work_id
                        suggested_work: {
                            id: recording.work_id,
                            title: recording.title,
                            artist: {
                                name: recording.artist
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

    // Batch selection handlers
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



    // ... (rest of state) ...

    const handleBulkLink = async () => {
        if (!queueItems) return;
        const selectedItems = queueItems.filter(item => selectedSignatures.has(item.signature));

        const allHaveSuggestions = selectedItems.every(item => item.suggested_work_id);  // Phase 4: Check work_id
        if (!allHaveSuggestions) {
            toast.error('All selected items must have suggestions to bulk link');
            return;
        }

        setProcessingIds(new Set(selectedItems.map(i => i.signature)));
        const BATCH_SIZE = 20;

        let successCount = 0;
        let failedCount = 0;
        let auditIds: number[] = [];

        // Chunk processing
        for (let i = 0; i < selectedItems.length; i += BATCH_SIZE) {
            const chunk = selectedItems.slice(i, i + BATCH_SIZE);

            const results = await Promise.allSettled(
                chunk.map(item =>
                    fetcher<{ status: string, signature: string, audit_id: number }>('/discovery/link', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            signature: item.signature,
                            work_id: item.suggested_work_id,  // Phase 4: Send work_id
                            is_batch: true
                        }),
                    })
                )
            );

            results.forEach(r => {
                if (r.status === 'fulfilled') {
                    successCount++;
                    // @ts-ignore
                    if (r.value.audit_id) auditIds.push(r.value.audit_id);
                } else {
                    failedCount++;
                }
            });
        }

        queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
        setProcessingIds(new Set());
        setSelectedSignatures(new Set());

        if (failedCount > 0) {
            toast.error(`Linked ${successCount} of ${selectedItems.length}. ${failedCount} failed.`);
        } else {
            if (auditIds.length > 0) {
                setLastAction({
                    auditIds,
                    summary: `Bulk linked ${successCount} tracks`
                });
            } else {
                toast.success(`Linked ${successCount} tracks`);
            }
        }
    };

    const handleBulkIgnore = async () => {
        if (!queueItems) return;
        const selectedItems = queueItems.filter(item => selectedSignatures.has(item.signature));

        setProcessingIds(new Set(selectedItems.map(i => i.signature)));

        const BATCH_SIZE = 20;
        let successCount = 0;
        let failedCount = 0;

        for (let i = 0; i < selectedItems.length; i += BATCH_SIZE) {
            const chunk = selectedItems.slice(i, i + BATCH_SIZE);
            const results = await Promise.allSettled(
                chunk.map(item =>
                    fetcher(`/discovery/${encodeURIComponent(item.signature)}`, {
                        method: 'DELETE',
                    })
                )
            );
            results.forEach(r => {
                if (r.status === 'fulfilled') successCount++;
                else failedCount++;
            });
        }

        if (failedCount === 0) {
            toast.success(`Ignored ${successCount} of ${selectedItems.length} tracks`);
        } else {
            toast.error(`Ignored ${successCount} of ${selectedItems.length}. ${failedCount} failed.`);
        }

        setProcessingIds(new Set());
        setSelectedSignatures(new Set());
        queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
    };

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            // List Mode Shortcuts
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
    }, [queueItems, view, matchMode]);

    return (
        <div className="space-y-6">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Verification Hub</h1>
                    <p className="text-gray-500">Review automated matches and resolve artist identity splits.</p>
                </div>
                <div className="flex bg-gray-100 p-1 rounded-lg">
                    <button
                        onClick={() => setView('artists')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${view === 'artists' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Artist Linking ({artistQueue?.length || 0})
                    </button>
                    <button
                        onClick={() => setView('matches')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${view === 'matches' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Song Linking ({queueItems?.length || 0})
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
                {view === 'artists' ? (
                    // Artist Linking View
                    isLoadingArtists ? (
                        <div className="p-8 text-center text-gray-500">Loading artist queue...</div>
                    ) : !artistQueue || artistQueue.length === 0 ? (
                        <div className="text-center py-20 text-gray-400">
                            <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                            <h2 className="text-xl font-medium text-gray-600">All Artists Linked!</h2>
                            <p>No unmatched artists found. Proceed to Song Linking.</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <div className="text-sm text-gray-500 mb-4">
                                Link raw artist names to your library artists. This improves song matching accuracy.
                            </div>
                            {artistQueue.map((artist) => (
                                <div
                                    key={artist.raw_name}
                                    className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-all"
                                >
                                    <div className="flex items-center justify-between gap-4">
                                        <div className="flex-1">
                                            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Raw Name</div>
                                            <div className="font-semibold text-gray-900">{artist.raw_name}</div>
                                            <div className="text-sm text-gray-500">{artist.item_count} item{artist.item_count !== 1 ? 's' : ''} affected</div>
                                        </div>
                                        <div className="flex-1">
                                            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Suggested Library Artist</div>
                                            {artist.suggested_artist ? (
                                                <div className="font-semibold text-green-600">{artist.suggested_artist.name}</div>
                                            ) : (
                                                <div className="text-gray-400 italic">No suggestion found</div>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {artist.suggested_artist && (
                                                <button
                                                    onClick={() => artistLinkMutation.mutate({
                                                        raw_name: artist.raw_name,
                                                        resolved_name: artist.suggested_artist!.name
                                                    })}
                                                    disabled={artistLinkMutation.isPending}
                                                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                                                >
                                                    Link
                                                </button>
                                            )}
                                            <button
                                                onClick={() => {
                                                    if (queueItems && queueItems.length > 0) {
                                                        const sampleItem = queueItems.find(q => q.raw_artist === artist.raw_name);
                                                        if (sampleItem) {
                                                            handleOpenSearch(sampleItem, artist.raw_name);
                                                        }
                                                    }
                                                }}
                                                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
                                            >
                                                <Search className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )
                ) : view === 'matches' ? (
                    <>
                        {/* View Toggle */}
                        <div className="flex justify-between items-center bg-white p-2 rounded-lg border border-gray-200 shadow-sm mb-4">
                            <div className="flex items-center gap-4 px-2">
                                <span className="text-sm text-gray-500 font-medium">
                                    {queueItems?.length || 0} items {showOnlyWithSuggestions ? '(filtered)' : 'in queue'}
                                </span>
                                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={showOnlyWithSuggestions}
                                        onChange={(e) => setShowOnlyWithSuggestions(e.target.checked)}
                                        className="w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                    />
                                    Hide items without suggestions
                                </label>
                            </div>
                            <div className="flex bg-gray-100 p-0.5 rounded-md">
                                <button
                                    onClick={() => setMatchMode('list')}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${matchMode === 'list' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                                    title="List View (Batch Mode)"
                                >
                                    <List className="w-4 h-4" /> List
                                </button>
                                <button
                                    onClick={() => setMatchMode('history')}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${matchMode === 'history' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`}
                                    title="History"
                                >
                                    <Clock className="w-4 h-4" /> History
                                </button>
                                <button
                                    onClick={() => queueItems && queueItems.length > 0 && handleOpenSearch(queueItems[0])}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium text-gray-500 hover:text-gray-700 transition-all"
                                    title="Search Library"
                                    disabled={!queueItems || queueItems.length === 0}
                                >
                                    <Search className="w-4 h-4" /> Search
                                </button>
                            </div>
                        </div>

                        {/* Sort Controls (for list view only) */}
                        {matchMode === 'list' && queueItems && queueItems.length > 0 && (
                            <div className="flex items-center justify-between bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
                                <div className="flex items-center gap-3">
                                    <label className="text-sm text-gray-600 font-medium">Sort by:</label>
                                    <select
                                        value={sortMode}
                                        onChange={(e) => setSortMode(e.target.value as SortMode)}
                                        className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:ring-indigo-500 focus:border-indigo-500"
                                    >
                                        <option value="artist-group">Grouped by Artist</option>
                                        <option value="count">By Count (Impact)</option>
                                        <option value="title">A-Z by Title</option>
                                    </select>
                                </div>
                                {sortMode === 'artist-group' && groupedItems && (
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-gray-500">{groupedItems.length} artists</span>
                                        <button
                                            onClick={handleExpandAll}
                                            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                                        >
                                            Expand All
                                        </button>
                                        <span className="text-gray-300">|</span>
                                        <button
                                            onClick={handleCollapseAll}
                                            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                                        >
                                            Collapse All
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Content Area */}
                        {matchMode === 'history' ? (
                            <VerificationHistory />
                        ) : isLoadingQueue ? (
                            <div className="p-8 text-center text-gray-500">Loading discovery queue...</div>
                        ) : !queueItems || queueItems.length === 0 ? (
                            <div className="text-center py-20 text-gray-400">
                                <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-green-500" />
                                <h2 className="text-xl font-medium text-gray-600">Queue Cleared!</h2>
                                <p>No unmatched logs found.</p>
                            </div>
                        ) : sortMode === 'artist-group' && groupedItems ? (
                            // Grouped List View
                            <div className="space-y-2">
                                {groupedItems.map(([artist, items]) => {
                                    const isExpanded = expandedGroups.has(artist);
                                    return (
                                        <div key={artist} className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                                            <button
                                                onClick={() => handleToggleGroup(artist)}
                                                className="w-full flex items-center justify-between p-3 hover:bg-gray-50 transition-colors"
                                            >
                                                <div className="flex items-center gap-2">
                                                    {isExpanded ? (
                                                        <ChevronDown className="w-5 h-5 text-gray-400" />
                                                    ) : (
                                                        <ChevronRight className="w-5 h-5 text-gray-400" />
                                                    )}
                                                    <span className="font-semibold text-gray-900">{artist}</span>
                                                </div>
                                                <span className="text-sm text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                                                    {items.length} item{items.length !== 1 ? 's' : ''}
                                                </span>
                                            </button>
                                            {isExpanded && (
                                                <div className="border-t border-gray-100 divide-y divide-gray-100">
                                                    {items.map((item) => {
                                                        const isSelected = selectedSignatures.has(item.signature);
                                                        const isProcessing = processingIds.has(item.signature);
                                                        const apiArtist = formatArtistForDisplay(item.suggested_work?.artist?.name || "No suggestion");  // Phase 4: Use suggested_work
                                                        const apiTitle = toTitleCase(item.suggested_work?.title || "");  // Phase 4: Use suggested_work
                                                        return (
                                                            <div
                                                                key={item.signature}
                                                                className={`p-4 pl-10 ${isSelected ? 'bg-blue-50' : ''} ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}
                                                            >
                                                                <div className="flex items-start gap-4">
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={isSelected}
                                                                        onChange={() => handleToggleSelect(item.signature)}
                                                                        className="mt-1 w-5 h-5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                                                    />
                                                                    <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div>
                                                                            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Raw Title</div>
                                                                            <span
                                                                                onClick={() => handleOpenSearch(item, item.raw_title)}
                                                                                onKeyDown={(e) => e.key === 'Enter' && handleOpenSearch(item, item.raw_title)}
                                                                                className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer"
                                                                                role="button"
                                                                                tabIndex={0}
                                                                            >
                                                                                {item.raw_title}
                                                                            </span>
                                                                        </div>
                                                                        <div>
                                                                            <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Suggested Match</div>
                                                                            <div className="font-semibold text-gray-900">{apiTitle || 'No suggestion'}</div>
                                                                            <div className="text-sm text-gray-600">{apiArtist}</div>
                                                                        </div>
                                                                    </div>
                                                                    {item.suggested_work_id && (  // Phase 4: Check work_id
                                                                        <button
                                                                            onClick={() => {
                                                                                queryClient.setQueryData(['discovery', 'queue', showOnlyWithSuggestions], (old: QueueItem[] | undefined) => {
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
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            // Flat List View (sorted by count or title)
                            <div className="space-y-2">
                                {sortedItems.map((item) => {
                                    const isSelected = selectedSignatures.has(item.signature);
                                    const isProcessing = processingIds.has(item.signature);
                                    const apiArtist = formatArtistForDisplay(item.suggested_work?.artist?.name || "No suggestion");  // Phase 4: Use suggested_work
                                    const apiTitle = toTitleCase(item.suggested_work?.title || "");  // Phase 4: Use suggested_work

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
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => handleToggleSelect(item.signature)}
                                                    className="mt-1 w-5 h-5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                                />
                                                <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Raw Data</div>
                                                        <span
                                                            onClick={() => handleOpenSearch(item, item.raw_title)}
                                                            onKeyDown={(e) => e.key === 'Enter' && handleOpenSearch(item, item.raw_title)}
                                                            className="font-semibold text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer block"
                                                            role="button"
                                                            tabIndex={0}
                                                        >
                                                            {item.raw_title}
                                                        </span>
                                                        <span
                                                            onClick={() => handleOpenSearch(item, item.raw_artist)}
                                                            onKeyDown={(e) => e.key === 'Enter' && handleOpenSearch(item, item.raw_artist)}
                                                            className="text-sm text-indigo-500 hover:text-indigo-700 hover:underline cursor-pointer"
                                                            role="button"
                                                            tabIndex={0}
                                                        >
                                                            {item.raw_artist}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Suggested Match</div>
                                                        <div className="font-semibold text-gray-900">{apiTitle || 'No suggestion'}</div>
                                                        <div className="text-sm text-gray-600">{apiArtist}</div>
                                                    </div>
                                                </div>
                                                {item.suggested_work_id && (  // Phase 4: Check work_id
                                                    <button
                                                        onClick={() => {
                                                            queryClient.setQueryData(['discovery', 'queue', showOnlyWithSuggestions], (old: QueueItem[] | undefined) => {
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

                        {/* Bulk Action Footer */}
                        {matchMode === 'list' && selectedSignatures.size > 0 && (
                            <div className="fixed bottom-0 left-0 right-0 backdrop-blur-sm bg-white/90 border-t border-gray-200 shadow-lg p-4 transition-transform duration-300 ease-out z-40">
                                <div className="max-w-7xl mx-auto flex items-center justify-between">
                                    <div className="text-sm font-medium text-gray-700">
                                        {selectedSignatures.size} item{selectedSignatures.size > 1 ? 's' : ''} selected
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <button
                                            onClick={handleBulkLink}
                                            disabled={!queueItems?.filter(item => selectedSignatures.has(item.signature)).every(item => item.suggested_work_id)}  // Phase 4: Check work_id
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

            <SearchDrawer
                isOpen={isSearchDrawerOpen}
                onClose={() => {
                    setIsSearchDrawerOpen(false);
                    setSearchingForItem(null);
                }}
                onSelect={handleSearchSelect}
                initialQuery={searchInitialQuery}
            />

            {lastAction && (
                <UndoBanner
                    summary={lastAction.summary}
                    onUndo={() => undoMutation.mutate(lastAction.auditIds)}
                    onDismiss={() => setLastAction(null)}
                />
            )}
        </div>
    );
}
