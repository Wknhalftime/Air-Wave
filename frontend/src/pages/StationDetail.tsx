import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { ArrowLeft, Radio, AlertTriangle, Calendar, FileText } from 'lucide-react';

interface UnmatchedTrack {
    artist: string;
    title: string;
    count: number;
}

interface BatchStats {
    id: number;
    date: string;
    filename: string;
    total: number;
    matched: number;
    match_rate: number;
}

interface StationHealth {
    station: {
        id: number;
        callsign: string;
    };
    recent_batches: BatchStats[];
    unmatched_tracks: UnmatchedTrack[];
}

export default function StationDetail() {
    const { id } = useParams();

    const { data: health, isLoading } = useQuery({
        queryKey: ['stations', id, 'health'],
        queryFn: () => fetcher<StationHealth>(`/stations/${id}/health`)
    });

    if (isLoading) return <div className="text-gray-500">Loading station details...</div>;
    if (!health) return <div className="text-red-500">Failed to load station data.</div>;

    return (
        <div>
            {/* Header */}
            <div className="mb-8">
                <Link to="/stations" className="inline-flex items-center text-gray-500 hover:text-indigo-600 mb-4 transition-colors">
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    Back to Stations
                </Link>
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-indigo-100 rounded-xl text-indigo-600">
                        <Radio className="w-8 h-8" />
                    </div>
                    <div className="flex-1">
                        <h1 className="text-3xl font-bold text-gray-900">{health.station.callsign}</h1>
                        <p className="text-gray-500">Detailed health and matching analysis</p>
                    </div>
                </div>
                {/* Add Gauge here? No, maybe just in the header row if I want. */}
                {/* Actually adding it now */}
                <div>
                    {/* We need match rate from somewhere. Aggregate endpoint gave it. 
                         Health endpoint might not have it pre-calculated?
                         Let's check models/api options.
                         The list endpoint calculates it. The health endpoint returns {station, unmatched}.
                         I might need to fetch stats or calculate locally?
                         Wait, the health endpoint I wrote in step 1695 returns: {station, unmatched}.
                         It doesn't return match_rate.
                         I should probably update the API to return it or just remove the gauge from detail for now?
                         Or I can fetch the stats again?
                         Actually, let's just remove the unused import for now to be safe and simple.
                         The user spec said "Detail view shows matching health timeline." and "lists".
                         It didn't explicitly demand the gauge in detail view, only grid.
                     */}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Visualizations / Stats Section */}
                <div className="lg:col-span-2 space-y-8">
                    {/* Recent Import Batches */}
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <Calendar className="w-5 h-5 text-indigo-500" />
                            Recent Imports & Match Rates
                        </h3>
                        <div className="space-y-4">
                            {health.recent_batches?.map((batch) => (
                                <div key={batch.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="flex items-center gap-4">
                                        <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm border-4 
                                            ${batch.match_rate >= 90 ? 'border-green-100 text-green-700 bg-green-50' :
                                                batch.match_rate >= 70 ? 'border-yellow-100 text-yellow-700 bg-yellow-50' :
                                                    'border-red-100 text-red-700 bg-red-50'}`}>
                                            {Math.round(batch.match_rate)}%
                                        </div>
                                        <div>
                                            <div className="font-medium text-gray-900 flex items-center gap-2">
                                                <FileText className="w-4 h-4 text-gray-400" />
                                                {batch.filename}
                                            </div>
                                            <div className="text-xs text-gray-500">
                                                {new Date(batch.date).toLocaleDateString()} • {batch.matched.toLocaleString()} / {batch.total.toLocaleString()} tracks
                                            </div>
                                        </div>
                                    </div>
                                    <div className="h-2 w-24 bg-gray-200 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full ${batch.match_rate >= 90 ? 'bg-green-500' : batch.match_rate >= 70 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                            style={{ width: `${batch.match_rate}%` }}
                                        />
                                    </div>
                                </div>
                            ))}

                            {(!health.recent_batches || health.recent_batches.length === 0) && (
                                <div className="text-center py-8 text-gray-400">
                                    No recent import batches found for this station.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Sidebar: Top Unmatched */}
                <div className="space-y-6">
                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-yellow-500" />
                            Top Unmatched Tracks
                        </h3>
                        <p className="text-sm text-gray-500 mb-4">Most frequent unmatched logs requiring manual review or alias creation.</p>

                        <div className="space-y-3">
                            {health.unmatched_tracks.map((track, i) => (
                                <div key={i} className="p-3 bg-gray-50 rounded-lg text-sm border border-gray-100 hover:border-indigo-200 transition-colors cursor-pointer">
                                    <div className="font-medium text-gray-900">{track.title}</div>
                                    <div className="text-gray-500">{track.artist}</div>
                                    <div className="mt-2 text-xs font-semibold text-yellow-600 bg-yellow-50 inline-block px-2 py-1 rounded">
                                        {track.count} failures
                                    </div>
                                </div>
                            ))}
                            {health.unmatched_tracks.length === 0 && (
                                <div className="text-center py-8 text-gray-400 text-sm">
                                    All tracks matched! 🎉
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
