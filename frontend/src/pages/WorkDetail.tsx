import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Music, Inbox } from 'lucide-react';
import { toTitleCase, formatArtistForDisplay } from '../utils/format';
import { useWork, useWorkRecordings } from '../hooks/useLibrary';
import RecordingRow from '../components/library/RecordingRow';
import Pagination from '../components/common/Pagination';
import EmptyState from '../components/common/EmptyState';

const PAGE_LIMIT = 100;

export default function WorkDetail() {
    const { id } = useParams<{ id: string }>();
    const workId = id ? parseInt(id, 10) : null;
    const [page, setPage] = useState(1);
    const [statusFilter, setStatusFilter] = useState<'all' | 'matched' | 'unmatched'>('all');
    const [sourceFilter, setSourceFilter] = useState<'all' | 'library' | 'metadata'>('all');

    const { data: work, isLoading: workLoading, error: workError } = useWork(workId);
    const {
        data: recordings,
        isLoading: recordingsLoading,
        error: recordingsError,
        isPlaceholderData,
    } = useWorkRecordings({
        workId,
        skip: (page - 1) * PAGE_LIMIT,
        limit: PAGE_LIMIT,
        status: statusFilter,
        source: sourceFilter,
    });



    if (workError) {
        return (
            <div className="space-y-6">
                <Link
                    to="/library"
                    className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Library
                </Link>
                <div className="text-center py-12 bg-white rounded-lg border border-red-100">
                    <p className="text-red-500">Work not found</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Breadcrumb */}
            <nav className="flex items-center gap-2 text-sm text-gray-600">
                <Link to="/library" className="hover:text-gray-900">
                    Library
                </Link>
                <span>/</span>
                {work?.artist_id && formatArtistForDisplay(work.artist_name) && (
                    <>
                        <Link
                            to={`/library/artists/${work.artist_id}`}
                            className="hover:text-gray-900"
                        >
                            {formatArtistForDisplay(work.artist_name)}
                        </Link>
                        <span>/</span>
                    </>
                )}
                <span className="text-gray-900 font-medium">
                    {work ? toTitleCase(work.title) : 'Loading...'}
                </span>
            </nav>

            {/* Work Header */}
            {workLoading ? (
                <div className="animate-pulse bg-white p-8 rounded-xl border border-gray-100">
                    <div className="h-8 bg-gray-200 w-1/3 mb-4 rounded" />
                    <div className="h-4 bg-gray-200 w-1/4 rounded" />
                </div>
            ) : work ? (
                <div className="bg-white p-8 rounded-xl border border-gray-100 shadow-sm">
                    <div className="flex items-start justify-between">
                        <div className="flex-1">
                            <h1 className="text-3xl font-bold text-gray-900 mb-2">
                                {toTitleCase(work.title)}
                            </h1>
                            <p className="text-lg text-gray-600 mb-4">{formatArtistForDisplay(work.artist_names)}</p>
                            <div className="flex items-center gap-6 text-sm text-gray-600">
                                <span className="flex items-center gap-2">
                                    <Music className="w-4 h-4" />
                                    {work.recording_count || 0} Recordings
                                </span>
                                {work.is_instrumental && (
                                    <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                                        Instrumental
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}

            {/* Filters */}
            <div className="bg-white p-4 rounded-lg border border-gray-100 shadow-sm">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                        <label htmlFor="status-filter" className="text-sm font-medium text-gray-700">
                            Status:
                        </label>
                        <select
                            id="status-filter"
                            value={statusFilter}
                            onChange={(e) => {
                                setStatusFilter(e.target.value as any);
                                setPage(1);
                            }}
                            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white transition-colors"
                        >
                            <option value="all">All Recordings</option>
                            <option value="matched">Matched Only</option>
                            <option value="unmatched">Unmatched Only</option>
                        </select>
                    </div>
                    <div className="flex items-center gap-2">
                        <label htmlFor="source-filter" className="text-sm font-medium text-gray-700">
                            Source:
                        </label>
                        <select
                            id="source-filter"
                            value={sourceFilter}
                            onChange={(e) => {
                                setSourceFilter(e.target.value as any);
                                setPage(1);
                            }}
                            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white transition-colors"
                        >
                            <option value="all">All Sources</option>
                            <option value="library">Library Files</option>
                            <option value="metadata">Metadata Only</option>
                        </select>
                    </div>
                    {(statusFilter !== 'all' || sourceFilter !== 'all') && (
                        <button
                            onClick={() => {
                                setStatusFilter('all');
                                setSourceFilter('all');
                                setPage(1);
                            }}
                            className="ml-auto text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                        >
                            Clear filters
                        </button>
                    )}
                </div>
            </div>

            {/* Recordings Table */}
            <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Recordings</h2>

                {recordingsError ? (
                    <div className="text-center py-12 bg-white rounded-lg border border-red-100">
                        <p className="text-red-500">Error loading recordings</p>
                    </div>
                ) : recordingsLoading ? (
                    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden">
                        <div className="animate-pulse p-6 space-y-4">
                            {[...Array(5)].map((_, i) => (
                                <div key={i} className="h-12 bg-gray-200 rounded" />
                            ))}
                        </div>
                    </div>
                ) : recordings && recordings.length > 0 ? (
                    <>
                        <div className="bg-white rounded-lg border border-gray-100 overflow-hidden shadow-sm">
                            <table className="w-full">
                                <thead className="bg-gray-50 border-b border-gray-200">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Title
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Version
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Duration
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Filename
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Status
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Source
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 bg-white">
                                    {recordings.map((recording) => (
                                        <RecordingRow key={recording.id} recording={recording} />
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <Pagination
                            currentPage={page}
                            onPageChange={setPage}
                            hasNextPage={recordings.length === PAGE_LIMIT && !isPlaceholderData}
                            isLoading={recordingsLoading}
                        />
                    </>
                ) : (
                    <EmptyState
                        icon={Inbox}
                        title="No recordings found"
                        description="Try adjusting your filters to see more results."
                    />
                )}
            </div>
        </div>
    );
}

