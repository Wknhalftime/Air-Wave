import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Music, Radio, Activity } from 'lucide-react';
import { clsx } from 'clsx';
import { toTitleCase, formatArtistForDisplay } from '../utils/format';

interface TrackResult {
    id: number;
    artist: string;
    title: string;
    album?: string;
    path: string;
    type: 'track';
}

interface LogResult {
    id: number;
    played_at: string; // ISO string
    raw_artist: string;
    raw_title: string;
    station_callsign: string;
    match_reason?: string;
    track_id?: number;
    type: 'log';
}

interface SearchResponse {
    tracks: TrackResult[];
    logs: LogResult[];
}

export default function Search() {
    const [searchParams] = useSearchParams();
    const query = searchParams.get('q') || '';

    // De-bounce queries if we were typing, but here we read from URL mainly
    // Just simple query for now
    const { data, isLoading } = useQuery({
        queryKey: ['search', query],
        queryFn: () => fetcher<SearchResponse>(`/search?q=${encodeURIComponent(query)}&limit=50`),
        enabled: query.length >= 2,
    });

    if (!query) {
        return (
            <div className="text-center py-20 text-gray-400">
                <Activity className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <h2 className="text-xl font-medium text-gray-600">Enter a search term</h2>
                <p>Search your Library and Broadcast History together.</p>
            </div>
        );
    }

    if (isLoading) {
        return <div className="p-8 text-center text-gray-500">Searching archive...</div>;
    }

    const hasTracks = data?.tracks && data.tracks.length > 0;
    const hasLogs = data?.logs && data.logs.length > 0;

    if (!hasTracks && !hasLogs) {
        return (
            <div className="text-center py-20 text-gray-400">
                <h2 className="text-xl font-medium text-gray-600">No results found</h2>
                <p>Try searching for a different artist or song title.</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <h1 className="text-2xl font-bold text-gray-800">
                Results for <span className="text-indigo-600">"{query}"</span>
            </h1>

            {/* Tracks Section */}
            {hasTracks && (
                <section>
                    <div className="flex items-center gap-2 mb-4">
                        <Music className="w-5 h-5 text-indigo-500" />
                        <h2 className="text-lg font-semibold text-gray-700">Library Tracks</h2>
                        <span className="text-xs font-medium bg-gray-100 px-2 py-0.5 rounded-full text-gray-500">
                            {data.tracks.length}
                        </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {data.tracks.map((track) => (
                            <div key={track.id} className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                                <div className="font-semibold text-gray-900 truncate" title={toTitleCase(track.title)}>{toTitleCase(track.title)}</div>
                                <div className="text-sm text-gray-600 truncate">{formatArtistForDisplay(track.artist)}</div>
                                {track.album && <div className="text-xs text-gray-400 mt-1 truncate">{track.album}</div>}
                                <div className="mt-3 text-xs font-mono text-gray-300 truncate" title={track.path}>
                                    {track.path}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* Logs Section - The "Evidence" */}
            {hasLogs && (
                <section>
                    <div className="flex items-center gap-2 mb-4">
                        <Radio className="w-5 h-5 text-indigo-500" />
                        <h2 className="text-lg font-semibold text-gray-700">Broadcast History</h2>
                        <span className="text-xs font-medium bg-gray-100 px-2 py-0.5 rounded-full text-gray-500">
                            {data.logs.length}
                        </span>
                    </div>
                    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-gray-50 text-gray-500 font-medium border-b border-gray-200">
                                <tr>
                                    <th className="px-4 py-3 w-32">Time</th>
                                    <th className="px-4 py-3 w-24">Station</th>
                                    <th className="px-4 py-3">Raw Data (Artist - Title)</th>
                                    <th className="px-4 py-3 w-64">Match Intelligence</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {data.logs.map((log) => (
                                    <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                                            {new Date(log.played_at).toLocaleString()}
                                        </td>
                                        <td className="px-4 py-3 font-medium text-indigo-600">
                                            {log.station_callsign}
                                        </td>
                                        <td className="px-4 py-3 text-gray-800">
                                            {log.raw_artist} - {log.raw_title}
                                        </td>
                                        <td className="px-4 py-3">
                                            {log.track_id ? (
                                                <div className="flex items-center gap-2" title={log.match_reason || 'Unknown Match'}>
                                                    <span className={clsx(
                                                        "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border",
                                                        log.match_reason?.includes("High Confidence")
                                                            ? "bg-green-50 text-green-700 border-green-200"
                                                            : log.match_reason?.includes("Exact")
                                                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                                                : "bg-yellow-50 text-yellow-700 border-yellow-200"
                                                    )}>
                                                        {log.match_reason?.includes("Exact") && <Music className="w-3 h-3" />}
                                                        {log.match_reason?.includes("Vector") && <Activity className="w-3 h-3" />}
                                                        <span className="truncate max-w-[200px]">{log.match_reason || "Legacy Match"}</span>
                                                    </span>
                                                </div>
                                            ) : (
                                                <span className="text-gray-400 text-xs italic">Unmatched</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
}
