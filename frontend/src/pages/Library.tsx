import { useState } from 'react';
import { Search } from 'lucide-react';
import { useArtists } from '../hooks/useArtists';
import { ArtistGrid } from '../components/library/ArtistGrid';

const PAGE_LIMIT = 24;

export default function Library() {
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState('');
    const limit = PAGE_LIMIT;

    const { data: artists, isLoading, error, isPlaceholderData } = useArtists({
        page,
        limit,
        search,
    });

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Library</h2>
                    <p className="text-sm text-gray-500 mt-1">Browse by Artist</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Find artist..."
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setPage(1);
                            }}
                            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none w-64 text-sm"
                        />
                    </div>
                </div>
            </div>

            {error ? (
                <div className="text-center py-12 bg-white rounded-lg border border-red-100">
                    <p className="text-red-500">Error loading artists. Please try refreshing.</p>
                </div>
            ) : (
                <ArtistGrid artists={artists || []} isLoading={isLoading} />
            )}

            {/* Pagination Controls */}
            {artists && artists.length > 0 && (
                <div className="flex justify-center mt-8 gap-2">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1 || isLoading}
                        className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                    >
                        Previous
                    </button>
                    <button
                        onClick={() => setPage((p) => p + 1)}
                        disabled={
                            !artists ||
                            artists.length < limit ||
                            isLoading ||
                            isPlaceholderData
                        }
                        className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}

