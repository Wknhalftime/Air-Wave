import { useState } from 'react';
import { toast } from 'sonner';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { bridgesApi } from '../api/bridges';
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import {
    Search, Ban, Undo2, Brain,
    ExternalLink, Pencil, Trash2
} from "lucide-react";
import { useDebounce } from "../hooks/useDebounce";

// Interfaces
interface Bridge {
    id: number;
    log_signature: string;
    reference_artist: string;
    reference_title: string;
    recording_id: number;
    is_revoked: boolean;
    updated_at: string;
    recording: {
        title: string;
        work: {
            artist: {
                name: string;
            };
        };
    };
    created_at?: string;
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

    // --- Bridges State ---
    const [search, setSearch] = useState("");
    const [includeRevoked, setIncludeRevoked] = useState(false);
    const debouncedSearch = useDebounce(search, 500);

    // Fetch Bridges (New API)
    const { data: bridges, isLoading: bridgesLoading } = useQuery({
        queryKey: ["bridges", debouncedSearch, includeRevoked],
        queryFn: () => bridgesApi.list({
            search: debouncedSearch,
            include_revoked: includeRevoked,
            page_size: 100,
        }),
        enabled: activeTab === 'bridges',
    });

    const bridgeMutation = useMutation({
        mutationFn: ({ id, is_revoked }: { id: number; is_revoked: boolean }) =>
            bridgesApi.updateStatus(id, is_revoked),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["bridges"] });
            toast.success(data.is_revoked ? "Bridge revoked" : "Bridge restored");
        },
        onError: () => {
            toast.error("Failed to update bridge status");
        }
    });

    // --- Aliases State ---
    const { data: aliases, isLoading: aliasesLoading } = useQuery({
        queryKey: ['identity', 'aliases'],
        queryFn: () => fetcher<ArtistAlias[]>('/identity/aliases'),
        enabled: activeTab === 'aliases',
    });

    // Alias Mutations
    const deleteAliasMutation = useMutation({
        mutationFn: (id: number) => fetcher(`/identity/aliases/${id}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['identity', 'aliases'] });
            toast.success("Alias deleted");
        },
        onError: () => toast.error("Failed to delete alias")
    });

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
            toast.success("Alias updated");
        },
        onError: () => toast.error("Failed to update alias")
    });

    // Alias UI State
    const [editingAliasId, setEditingAliasId] = useState<number | null>(null);
    const [editValue, setEditValue] = useState('');

    const startEditing = (alias: ArtistAlias) => {
        setEditingAliasId(alias.id);
        setEditValue(alias.resolved_name || '');
    };

    const handleSaveAlias = (id: number) => {
        if (!editValue.trim()) return;
        updateAliasMutation.mutate({ id, resolved_name: editValue });
    };

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
                    {['bridges', 'aliases'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab as any)}
                            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === tab
                                ? 'border-indigo-600 text-indigo-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {tab === 'bridges' && 'Recall Bridges'}
                            {tab === 'aliases' && 'Artist Aliases'}
                        </button>
                    ))}
                </nav>
            </div>

            <div className="pt-6">
                {activeTab === 'bridges' && (
                    <div className="space-y-6">
                        {/* Filters */}
                        <div className="flex items-center gap-4 bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
                            <div className="relative flex-1 max-w-sm">
                                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search mappings..."
                                    className="pl-9"
                                    value={search}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
                                />
                            </div>
                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="show-revoked"
                                    checked={includeRevoked}
                                    onCheckedChange={setIncludeRevoked}
                                />
                                <Label htmlFor="show-revoked">Show Revoked</Label>
                            </div>
                        </div>

                        {/* Bridges Table */}
                        {bridgesLoading ? (
                            <div className="text-gray-500 text-center py-8">Loading bridges...</div>
                        ) : !bridges || bridges.length === 0 ? (
                            <div className="text-center py-8">
                                <p className="text-gray-500">No matching bridges found.</p>
                                {!includeRevoked && <p className="text-sm text-gray-400 mt-2">Try checking "Show Revoked" or clearing search.</p>}
                            </div>
                        ) : (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                                <table className="min-w-full divide-y divide-gray-200 text-sm">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Log Signature</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resolved To</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {bridges.map((bridge: Bridge) => (
                                            <tr key={bridge.id} className={`hover:bg-gray-50 ${bridge.is_revoked ? 'bg-gray-50 opacity-75' : ''}`}>
                                                <td className="px-6 py-4">
                                                    <div className="font-medium text-gray-900">{bridge.reference_title}</div>
                                                    <div className="text-gray-500 text-xs">{bridge.reference_artist}</div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="font-medium text-green-700">{bridge.recording?.title}</div>
                                                    <div className="text-green-600 text-xs">{bridge.recording?.work?.artist?.name}</div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    {bridge.is_revoked ? (
                                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                                            Revoked
                                                        </span>
                                                    ) : (
                                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                                            Active
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    {bridge.is_revoked ? (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => bridgeMutation.mutate({ id: bridge.id, is_revoked: false })}
                                                            disabled={bridgeMutation.isPending}
                                                        >
                                                            <Undo2 className="w-4 h-4 mr-2" />
                                                            Restore
                                                        </Button>
                                                    ) : (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                                                            onClick={() => bridgeMutation.mutate({ id: bridge.id, is_revoked: true })}
                                                            disabled={bridgeMutation.isPending}
                                                        >
                                                            <Ban className="w-4 h-4 mr-2" />
                                                            Revoke
                                                        </Button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'aliases' && (
                    <div className="space-y-6">
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
                    </div>
                )}
            </div>
        </div>
    );
}
