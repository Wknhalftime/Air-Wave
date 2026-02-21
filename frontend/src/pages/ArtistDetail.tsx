import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Music, Disc, Inbox } from 'lucide-react';
import { toTitleCase, formatArtistForDisplay } from '../utils/format';
import { useArtist, useArtistWorks } from '../hooks/useLibrary';
import WorkRow from '../components/library/WorkRow';
import Pagination from '../components/common/Pagination';
import EmptyState from '../components/common/EmptyState';

const PAGE_LIMIT = 24;

export default function ArtistDetail() {
    const { id } = useParams<{ id: string }>();
    const artistId = id ? parseInt(id, 10) : null;
    const [page, setPage] = useState(1);

    const { data: artist, isLoading: artistLoading, error: artistError } = useArtist(artistId);
    const {
        data: works,
        isLoading: worksLoading,
        error: worksError,
        isPlaceholderData,
    } = useArtistWorks({
        artistId,
        skip: (page - 1) * PAGE_LIMIT,
        limit: PAGE_LIMIT,
    });

    if (artistError) {
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
                    <p className="text-red-500">Artist not found</p>
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
                <span className="text-gray-900 font-medium">
                    {artist ? (formatArtistForDisplay(artist.name) || '–') : 'Loading...'}
                </span>
            </nav>

            {/* Artist Header */}
            {artistLoading ? (
                <div className="animate-pulse bg-white p-8 rounded-xl border border-gray-100">
                    <div className="flex items-center gap-6">
                        <div className="w-32 h-32 rounded-full bg-gray-200" />
                        <div className="flex-1">
                            <div className="h-8 bg-gray-200 w-1/3 mb-4 rounded" />
                            <div className="h-4 bg-gray-200 w-1/4 rounded" />
                        </div>
                    </div>
                </div>
            ) : artist ? (
                <div className="bg-white p-8 rounded-xl border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-6">
                        <div className="w-32 h-32 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-4xl font-bold text-white">
                            {formatArtistForDisplay(artist.name).charAt(0)}
                        </div>
                        <div className="flex-1">
                            <h1 className="text-3xl font-bold text-gray-900 mb-2">
                                {formatArtistForDisplay(artist.name)}
                            </h1>
                            <div className="flex items-center gap-6 text-sm text-gray-600">
                                <span className="flex items-center gap-2">
                                    <Music className="w-4 h-4" />
                                    {artist.work_count || 0} Works
                                </span>
                                <span className="flex items-center gap-2">
                                    <Disc className="w-4 h-4" />
                                    {artist.recording_count || 0} Recordings
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}

            {/* Works Section */}
            <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Works</h2>

                {worksError ? (
                    <div className="text-center py-12 bg-white rounded-lg border border-red-100">
                        <p className="text-red-500">Error loading works</p>
                    </div>
                ) : worksLoading ? (
                    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden">
                        <div className="animate-pulse p-6 space-y-4">
                            {[...Array(6)].map((_, i) => (
                                <div key={i} className="h-12 bg-gray-200 rounded" />
                            ))}
                        </div>
                    </div>
                ) : works && works.length > 0 ? (
                    <>
                        <div className="bg-white rounded-lg border border-gray-100 overflow-hidden shadow-sm">
                            <table className="w-full">
                                <thead className="bg-gray-50 border-b border-gray-200">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Title
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Artist
                                        </th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                            Recordings
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 bg-white">
                                    {works.map((work) => (
                                        <WorkRow key={work.id} work={work} compact />
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <Pagination
                            currentPage={page}
                            onPageChange={setPage}
                            hasNextPage={works.length === PAGE_LIMIT && !isPlaceholderData}
                            isLoading={worksLoading}
                        />
                    </>
                ) : (
                    <EmptyState
                        icon={Inbox}
                        title="No works found"
                        description="This artist doesn't have any works yet."
                    />
                )}
            </div>
        </div>
    );
}

