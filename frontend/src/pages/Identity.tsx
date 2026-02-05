import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Trash2, Brain, AlertTriangle, ArrowUpDown, Filter, Pencil, ExternalLink } from 'lucide-react';
import { useState, useMemo } from 'react';
import { OnboardingAlert } from '../components/OnboardingAlert';

// Interfaces
interface IdentityBridge {
    id: number;
    raw_artist: string;
    raw_title: string;
    recording: {
        id: number;
        title: string;
        artist: string;
    };
    confidence: number;
    created_at: string;
}

interface ArtistAlias {
    id: number;
    raw_name: string;
    resolved_name: string | null;
    is_verified: boolean;
    created_at: string;
}

export default function Identity() {
    const [activeTab, setActiveTab] = useState<'bridges' | 'aliases' | 'conflicts'>('bridges');
    const queryClient = useQueryClient();

    // Fetch bridges
    const { data: bridges, isLoading: bridgesLoading } = useQuery({
        queryKey: ['identity', 'bridges'],
        queryFn: () => fetcher<IdentityBridge[]>('/identity/bridges?limit=100')
    });

    // Fetch aliases
    const { data: aliases, isLoading: aliasesLoading } = useQuery({
        queryKey: ['identity', 'aliases'],
        queryFn: () => fetcher<ArtistAlias[]>('/identity/aliases')
    });

    // Delete bridge mutation
    const deleteBridgeMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/identity/bridges/${id}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'bridges'] });
        }
    });

    // Delete alias mutation
    const deleteAliasMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/identity/aliases/${id}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'aliases'] });
        }
    });

    // Update alias mutation
    const updateAliasMutation = useMutation({
        mutationFn: ({ id, resolved_name }: { id: number, resolved_name: string }) =>
            fetcher(`/identity/aliases/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resolved_name })
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'aliases'] });
            setEditingAliasId(null);
        }
    });

    // State for filtering/sorting
    const [sortField, setSortField] = useState<'date' | 'artist' | 'title'>('date');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
    const [filterSelf, setFilterSelf] = useState(false);
    const [filterText, setFilterText] = useState('');
    const [selectedIds, setSelectedIds] = useState<number[]>([]);

    // Editing State
    const [editingAliasId, setEditingAliasId] = useState<number | null>(null);
    const [editValue, setEditValue] = useState('');

    const startEditing = (alias: ArtistAlias) => {
        setEditingAliasId(alias.id);
        setEditValue(alias.resolved_name || '');
    };

    const handleSaveAlias = (id: number) => {
        if (!editValue.trim()) return; // Don't allow empty
        updateAliasMutation.mutate({ id, resolved_name: editValue });
    };



    // Reset selection when tab changes
    const handleTabChange = (tab: any) => {
        setActiveTab(tab);
        setSelectedIds([]);
        setFilterText('');
    };

    // Derived Data: Bridges
    const processedBridges = useMemo(() => {
        if (!bridges) return [];
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        let result = [...bridges];

        // Filter
        if (filterText) {
            const lower = filterText.toLowerCase();
            result = result.filter(b =>
                b.raw_artist.toLowerCase().includes(lower) ||
                b.raw_title.toLowerCase().includes(lower) ||
                b.recording.artist.toLowerCase().includes(lower)
            );
        }
        if (filterSelf) {
            result = result.filter(b => b.raw_artist.toLowerCase() === b.recording.artist.toLowerCase());
        }

        // Sort
        result.sort((a, b) => {
            let valA: any = '';
            let valB: any = '';

            switch (sortField) {
                case 'date':
                    valA = new Date(a.created_at).getTime();
                    valB = new Date(b.created_at).getTime();
                    break;
                case 'artist':
                    valA = a.raw_artist.toLowerCase();
                    valB = b.raw_artist.toLowerCase();
                    break;
                case 'title':
                    valA = a.raw_title.toLowerCase();
                    valB = b.raw_title.toLowerCase();
                    break;
            }

            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });

        return result;
    }, [bridges, sortField, sortDirection, filterText, filterSelf]);

    // Bulk Delete
    const handleBulkDelete = async () => {
        if (!confirm(`Delete ${selectedIds.length} items?`)) return;

        // Parallel delete (MVP)
        const promises = selectedIds.map(id =>
            activeTab === 'bridges'
                ? deleteBridgeMutation.mutateAsync(id)
                : deleteAliasMutation.mutateAsync(id)
        );

        await Promise.all(promises);
        setSelectedIds([]);
    };

    const toggleSelect = (id: number) => {
        setSelectedIds(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
    };

    const toggleAll = () => {
        const source = activeTab === 'bridges' ? processedBridges : aliases || [];
        if (selectedIds.length === source.length) {
            setSelectedIds([]);
        } else {
            setSelectedIds(source.map(x => x.id));
        }
    };

    // const conflicts = []; 

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-indigo-100 rounded-xl text-indigo-600">
                    <Brain className="w-8 h-8" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Identity Manager</h1>
                    <p className="text-gray-500">Audit and control the AI's memory (Adaptive Recall).</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200">
                <nav className="flex gap-8">
                    {['bridges', 'aliases', 'conflicts'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => handleTabChange(tab as any)}
                            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === tab
                                ? 'border-indigo-600 text-indigo-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {tab === 'bridges' && 'Recall Bridges'}
                            {tab === 'aliases' && 'Artist Aliases'}
                            {tab === 'conflicts' && 'Conflicts'}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Tab Content */}
            <div className="pt-6">
                {activeTab === 'bridges' && (
                    <>
                        {/* Onboarding Alert */}
                        {!bridgesLoading && (!bridges || bridges.length === 0) && (
                            <OnboardingAlert type="no-bridges" />
                        )}

                        {/* Toolbar */}
                        <div className="flex items-center gap-4 mb-4 bg-white p-3 rounded-lg border border-gray-200 shadow-sm">
                            <input
                                type="text"
                                placeholder="Search bridges..."
                                value={filterText}
                                onChange={e => setFilterText(e.target.value)}
                                className="flex-1 border-gray-300 rounded-md text-sm focus:ring-indigo-500 focus:border-indigo-500"
                            />

                            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                                <Filter className="w-4 h-4 text-gray-400" />
                                <input
                                    type="checkbox"
                                    checked={filterSelf}
                                    onChange={e => setFilterSelf(e.target.checked)}
                                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                />
                                <span>Show Self-Matches Only</span>
                            </label>

                            <div className="h-6 w-px bg-gray-200 mx-2"></div>

                            {selectedIds.length > 0 && (
                                <button
                                    onClick={handleBulkDelete}
                                    className="bg-red-50 text-red-600 px-3 py-1.5 rounded-md text-sm font-medium hover:bg-red-100 transition-colors flex items-center gap-2"
                                >
                                    <Trash2 className="w-4 h-4" />
                                    Delete {selectedIds.length}
                                </button>
                            )}
                        </div>

                        {bridgesLoading ? (
                            <div className="text-gray-500">Loading bridges...</div>
                        ) : processedBridges.length === 0 ? (
                            <div className="text-gray-500 italic text-center py-8">No matching bridges found.</div>
                        ) : (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                                <table className="min-w-full divide-y divide-gray-200 text-sm">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-4 py-3 w-10">
                                                <input
                                                    type="checkbox"
                                                    checked={processedBridges.length > 0 && selectedIds.length === processedBridges.length}
                                                    onChange={toggleAll}
                                                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                                />
                                            </th>
                                            <th
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                                                onClick={() => {
                                                    if (sortField === 'artist') setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
                                                    else setSortField('artist');
                                                }}
                                            >
                                                <div className="flex items-center gap-1">
                                                    Raw Input
                                                    {sortField === 'artist' && <ArrowUpDown className="w-3 h-3" />}
                                                </div>
                                            </th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mapped To Library</th>
                                            <th
                                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                                                onClick={() => {
                                                    if (sortField === 'date') setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
                                                    else setSortField('date');
                                                }}
                                            >
                                                <div className="flex items-center gap-1">
                                                    Created
                                                    {sortField === 'date' && <ArrowUpDown className="w-3 h-3" />}
                                                </div>
                                            </th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">confidence</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {processedBridges.map((bridge) => (
                                            <tr key={bridge.id} className={`hover:bg-gray-50 ${selectedIds.includes(bridge.id) ? 'bg-indigo-50' : ''}`}>
                                                <td className="px-4 py-4">
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedIds.includes(bridge.id)}
                                                        onChange={() => toggleSelect(bridge.id)}
                                                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                                    />
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="font-medium text-gray-900">{bridge.raw_title}</div>
                                                    <div className="text-gray-500">{bridge.raw_artist}</div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="font-medium text-green-700">{bridge.recording.title}</div>
                                                    <div className="text-green-600">{bridge.recording.artist}</div>
                                                </td>
                                                <td className="px-6 py-4 text-gray-500">
                                                    {new Date(bridge.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    {(bridge.confidence * 100).toFixed(0)}%
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}

                {activeTab === 'aliases' && (
                    <>
                        {aliasesLoading ? (
                            <div className="text-gray-500">Loading aliases...</div>
                        ) : !aliases || aliases.length === 0 ? (
                            <div className="text-gray-500 italic">No artist aliases found.</div>
                        ) : (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                                <table className="min-w-full divide-y divide-gray-200 text-sm">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Raw Name</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resolved Name</th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {aliases.map((alias) => (
                                            <tr key={alias.id} className="hover:bg-gray-50">
                                                <td className="px-6 py-4 font-mono text-gray-600 flex items-center gap-2 group">
                                                    {alias.raw_name}
                                                    <a
                                                        href={`https://www.google.com/search?q=${encodeURIComponent(alias.raw_name)} music artist`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="ml-2 opacity-0 group-hover:opacity-100 text-blue-400 hover:text-blue-600 transition-all inline-block align-middle"
                                                        title="Search on Google"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        <ExternalLink className="w-3 h-3" />
                                                    </a>
                                                </td>
                                                <td className="px-6 py-4 font-bold text-gray-900">
                                                    {editingAliasId === alias.id ? (
                                                        <input
                                                            autoFocus
                                                            type="text"
                                                            value={editValue}
                                                            onChange={(e) => setEditValue(e.target.value)}
                                                            onKeyDown={(e) => {
                                                                if (e.key === 'Enter') handleSaveAlias(alias.id);
                                                                if (e.key === 'Escape') setEditingAliasId(null);
                                                            }}
                                                            onBlur={() => handleSaveAlias(alias.id)}
                                                            className="w-full border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                                                            placeholder="Use semicolons for multiple artists (e.g. Artist A; Artist B)"
                                                        />
                                                    ) : (
                                                        <div
                                                            onClick={() => startEditing(alias)}
                                                            className="cursor-pointer hover:bg-yellow-50 hover:text-indigo-600 px-2 py-1 -ml-2 rounded border border-transparent hover:border-yellow-200 transition-all flex items-center gap-2 group"
                                                            title="Click to Edit"
                                                        >
                                                            {alias.resolved_name || <span className="text-gray-400 italic">Ignored (Null)</span>}
                                                            <Pencil className="w-3 h-3 text-gray-300 opacity-0 group-hover:opacity-100" />
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <button
                                                        onClick={() => {
                                                            if (confirm('Delete this alias?')) {
                                                                deleteAliasMutation.mutate(alias.id);
                                                            }
                                                        }}
                                                        className="text-gray-400 hover:text-red-600 transition-colors"
                                                    >
                                                        <Trash2 className="w-5 h-5" />
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}

                {activeTab === 'conflicts' && (
                    <div className="text-center py-12 bg-gray-50 rounded-xl border border-dashed border-gray-300">
                        <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-gray-900">No Conflicts Detected</h3>
                        <p className="text-gray-500">Your memory banks are consistent.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
