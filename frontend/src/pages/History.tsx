import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Calendar, Filter } from 'lucide-react';

interface Station {
    id: number;
    callsign: string;
}

interface BroadcastLog {
    id: number;
    played_at: string;
    station: Station;
    raw_artist: string;
    raw_title: string;
    track_id: number | null;
}

export default function History() {
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]); // Default Today

    const { data: logs, isLoading } = useQuery({
        queryKey: ['history', 'logs', date],
        queryFn: () => fetcher<BroadcastLog[]>(`/history/logs?date=${date}&limit=500`)
    });

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">Broadcast History</h2>
                <div className="flex gap-2">
                    <div className="relative">
                        <input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                            className="pl-10 pr-3 py-2 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                        <Calendar className="w-4 h-4 text-gray-500 absolute left-3 top-2.5 pointer-events-none" />
                    </div>
                    <button className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50">
                        <Filter className="w-4 h-4 text-gray-500" />
                        Filter
                    </button>
                </div>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Station</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Artist</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {isLoading ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">Loading logs...</td></tr>
                        ) : logs?.length === 0 ? (
                            <tr><td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">No logs for this date.</td></tr>
                        ) : (
                            logs?.map((log) => (
                                <tr key={log.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {new Date(log.played_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-indigo-600">{log.station.callsign}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.raw_artist}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.raw_title}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
