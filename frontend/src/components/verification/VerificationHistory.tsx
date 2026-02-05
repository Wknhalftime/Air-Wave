import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../../lib/api';
import type { AuditEntry } from '../../types';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { Undo, Search, Filter } from 'lucide-react';

export default function VerificationHistory() {
    const queryClient = useQueryClient();
    const [page, setPage] = useState(0);
    const pageSize = 50;

    // Filters
    const [artistFilter, setArtistFilter] = useState('');
    const [titleFilter, setTitleFilter] = useState('');
    const [actionTypeFilter, setActionTypeFilter] = useState('');
    const [fromDate, setFromDate] = useState('');
    const [toDate, setToDate] = useState('');

    // Query params
    const queryParams = new URLSearchParams({
        skip: (page * pageSize).toString(),
        limit: pageSize.toString(),
        ...(artistFilter && { artist: artistFilter }),
        ...(titleFilter && { title: titleFilter }),
        ...(actionTypeFilter && { action_type: actionTypeFilter }),
        ...(fromDate && { from_date: fromDate }),
        ...(toDate && { to_date: toDate }),
    }).toString();

    const { data: auditHistory, isLoading } = useQuery({
        queryKey: ['verification', 'audit', page, artistFilter, titleFilter, actionTypeFilter, fromDate, toDate],
        queryFn: () => fetcher<AuditEntry[]>(`/identity/audit?${queryParams}`)
        // Note: Endpoint changed to /identity/audit based on router implementation in identity.py
    });

    const undoMutation = useMutation({
        mutationFn: (auditId: number) => fetcher(`/identity/audit/${auditId}/undo`, { method: 'POST' }),
        onSuccess: (data: any) => {
            queryClient.invalidateQueries({ queryKey: ['verification', 'audit'] });
            queryClient.invalidateQueries({ queryKey: ['discovery', 'queue'] });
            if (data.was_already_undone) {
                toast.info('This action was already undone');
            } else {
                toast.success('Action undone successfully');
            }
        },
        onError: (error: any) => {
            toast.error(`Failed to undo action: ${error.message || 'Unknown error'}`);
        }
    });

    const handleUndo = (auditId: number) => {
        undoMutation.mutate(auditId);
    };

    const getActionColor = (type: string) => {
        switch (type) {
            case 'link': return 'bg-blue-100 text-blue-800';
            case 'promote': return 'bg-green-100 text-green-800';
            case 'bulk_link': return 'bg-indigo-100 text-indigo-800';
            case 'undo': return 'bg-gray-100 text-gray-800';
            case 'manual_bridge': return 'bg-purple-100 text-purple-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    };

    return (
        <div className="h-full flex flex-col">
            {/* Filters */}
            <div className="p-4 border-b bg-gray-50 flex gap-4 items-center flex-wrap">
                <div className="flex items-center gap-2 bg-white px-3 py-2 rounded border">
                    <Search size={16} className="text-gray-400" />
                    <input
                        placeholder="Filter Artist"
                        value={artistFilter}
                        onChange={e => setArtistFilter(e.target.value)}
                        className="outline-none text-sm w-32 md:w-48"
                    />
                </div>
                <div className="flex items-center gap-2 bg-white px-3 py-2 rounded border">
                    <Search size={16} className="text-gray-400" />
                    <input
                        placeholder="Filter Title"
                        value={titleFilter}
                        onChange={e => setTitleFilter(e.target.value)}
                        className="outline-none text-sm w-32 md:w-48"
                    />
                </div>
                <div className="flex items-center gap-2 bg-white px-3 py-2 rounded border">
                    <Filter size={16} className="text-gray-400" />
                    <select
                        value={actionTypeFilter}
                        onChange={e => setActionTypeFilter(e.target.value)}
                        className="outline-none text-sm bg-transparent"
                    >
                        <option value="">All Actions</option>
                        <option value="link">Link</option>
                        <option value="promote">Promote</option>
                        <option value="bulk_link">Bulk Link</option>
                        <option value="bulk_promote">Bulk Promote</option>
                        <option value="undo">Undo</option>
                        <option value="manual_bridge">Manual Bridge</option>
                    </select>
                </div>
                <div className="flex items-center gap-2 bg-white px-3 py-2 rounded border">
                    <span className="text-xs text-gray-400 font-medium">From:</span>
                    <input
                        type="date"
                        value={fromDate}
                        onChange={e => setFromDate(e.target.value)}
                        className="outline-none text-sm"
                    />
                </div>
                <div className="flex items-center gap-2 bg-white px-3 py-2 rounded border">
                    <span className="text-xs text-gray-400 font-medium">To:</span>
                    <input
                        type="date"
                        value={toDate}
                        onChange={e => setToDate(e.target.value)}
                        className="outline-none text-sm"
                    />
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm text-left">
                    <thead className="bg-gray-50 text-gray-500 uppercase font-medium sticky top-0">
                        <tr>
                            <th className="px-6 py-3">Time</th>
                            <th className="px-6 py-3">Action</th>
                            <th className="px-6 py-3">Artist</th>
                            <th className="px-6 py-3">Title</th>
                            <th className="px-6 py-3">Result</th>
                            <th className="px-6 py-3 text-center">Logs</th>
                            <th className="px-6 py-3 text-right">Undo</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {isLoading ? (
                            <tr><td colSpan={7} className="p-8 text-center text-gray-400">Loading history...</td></tr>
                        ) : auditHistory?.map((entry) => (
                            <tr key={entry.id} className="hover:bg-gray-50/50">
                                <td className="px-6 py-4 whitespace-nowrap text-gray-500" title={entry.created_at}>
                                    {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium uppercase ${getActionColor(entry.action_type)}`}>
                                        {entry.action_type}
                                    </span>
                                </td>
                                <td className="px-6 py-4 font-medium text-gray-900">{entry.raw_artist}</td>
                                <td className="px-6 py-4 text-gray-600">{entry.raw_title}</td>
                                <td className="px-6 py-4 text-gray-500">
                                    {entry.recording_artist && entry.recording_title ? (
                                        <span>{entry.recording_artist} - {entry.recording_title}</span>
                                    ) : (
                                        <span className="text-gray-300 italic">N/A</span>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-center">
                                    {entry.log_count > 0 && (
                                        <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs">
                                            {entry.log_count}
                                        </span>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {entry.undone_at ? (
                                        <span className="text-xs text-gray-400 italic">Undone</span>
                                    ) : entry.can_undo ? (
                                        <button
                                            onClick={() => handleUndo(entry.id)}
                                            className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1 rounded transition-colors"
                                            title="Undo this action"
                                            disabled={undoMutation.isPending}
                                        >
                                            <Undo size={16} />
                                        </button>
                                    ) : null}
                                </td>
                            </tr>
                        ))}
                        {!isLoading && auditHistory?.length === 0 && (
                            <tr><td colSpan={7} className="p-8 text-center text-gray-400">No history found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination Controls */}
            <div className="p-4 border-t bg-gray-50 flex justify-end gap-2">
                <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 bg-white border rounded disabled:opacity-50 text-sm"
                >
                    Previous
                </button>
                <span className="px-3 py-1 text-sm text-gray-600 self-center">Page {page + 1}</span>
                <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={!auditHistory || auditHistory.length < pageSize}
                    className="px-3 py-1 bg-white border rounded disabled:opacity-50 text-sm"
                >
                    Next
                </button>
            </div>
        </div>
    );
}
