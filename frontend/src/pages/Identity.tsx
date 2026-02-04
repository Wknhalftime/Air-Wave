import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Trash2, Brain, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

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

    const conflicts = []; // Placeholder for conflicts logic if needed client-side, or derived

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
                            onClick={() => setActiveTab(tab as any)}
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
                        {bridgesLoading ? (
                            <div className="text-gray-500">Loading bridges...</div>
                        ) : !bridges || bridges.length === 0 ? (
                            <div className="text-gray-500 italic">No identity bridges found.</div>
                        ) : (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                                <table className="min-w-full divide-y divide-gray-200 text-sm">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Raw Input</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mapped To Library</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {bridges.map((bridge) => (
                                            <tr key={bridge.id} className="hover:bg-gray-50">
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
                                                    <button
                                                        onClick={() => {
                                                            if (confirm('Forget this memory? Matches will decrease.')) {
                                                                deleteBridgeMutation.mutate(bridge.id);
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
                                                <td className="px-6 py-4 font-mono text-gray-600">
                                                    {alias.raw_name}
                                                </td>
                                                <td className="px-6 py-4 font-bold text-gray-900">
                                                    {alias.resolved_name || <span className="text-gray-400 italic">Ignored (Null)</span>}
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
