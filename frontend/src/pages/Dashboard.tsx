import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Music, Radio, Clock } from 'lucide-react';

export default function Dashboard() {
    const { data: stats } = useQuery({
        queryKey: ['library', 'stats'],
        queryFn: () => fetcher<{ total_tracks: number, total_stations: number }>('/library/stats')
    });

    const cards = [
        { label: 'Total Tracks', value: stats?.total_tracks ?? '-', icon: Music, color: 'text-indigo-600', bg: 'bg-indigo-50' },
        { label: 'Stations Monitored', value: stats?.total_stations ?? '0', icon: Radio, color: 'text-emerald-600', bg: 'bg-emerald-50' },
        { label: 'Uptime', value: '99.9%', icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50' }, // Still Mock
    ];

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
                <p className="text-gray-500 mt-1">System Overview</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {cards.map((card) => {
                    const Icon = card.icon;
                    return (
                        <div key={card.label} className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4">
                            <div className={`p-3 rounded-lg ${card.bg}`}>
                                <Icon className={`w-6 h-6 ${card.color}`} />
                            </div>
                            <div>
                                <div className="text-sm font-medium text-gray-500">{card.label}</div>
                                <div className="text-2xl font-bold text-gray-900">{card.value}</div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
