import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';

interface TopItem {
    name: string;
    artist: string;
    title: string;
    count: number;
}

interface DailyItem {
    date: string;
    count: number;
}

export default function Analytics() {
    const { data: topTracks } = useQuery<TopItem[]>({
        queryKey: ['analytics', 'top-tracks'],
        queryFn: () => fetcher('/analytics/top-tracks?limit=10')
    });

    const { data: topArtists } = useQuery<{ name: string; count: number }[]>({
        queryKey: ['analytics', 'top-artists'],
        queryFn: () => fetcher('/analytics/top-artists?limit=10')
    });

    const { data: dailyActivity } = useQuery<DailyItem[]>({
        queryKey: ['analytics', 'daily-activity'],
        queryFn: () => fetcher('/analytics/daily-activity?days=30')
    });

    return (
        <div className="space-y-8 animate-fade-in p-6">
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-600">
                Analytics
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* Top Tracks Bar Chart */}
                <div className="p-6 bg-white/5 backdrop-blur-lg rounded-xl border border-white/10 shadow-xl">
                    <h2 className="text-xl font-semibold mb-4 text-purple-200">Top Tracks</h2>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={topTracks} layout="vertical" margin={{ left: 20 }}>
                                <XAxis type="number" hide />
                                <YAxis dataKey="title" type="category" width={100} tick={{ fill: '#aaa', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1a1a1a', border: 'none', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Top Artists Bar Chart */}
                <div className="p-6 bg-white/5 backdrop-blur-lg rounded-xl border border-white/10 shadow-xl">
                    <h2 className="text-xl font-semibold mb-4 text-pink-200">Top Artists</h2>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={topArtists} layout="vertical" margin={{ left: 20 }}>
                                <XAxis type="number" hide />
                                <YAxis dataKey="name" type="category" width={100} tick={{ fill: '#aaa', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1a1a1a', border: 'none', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Bar dataKey="count" fill="#ec4899" radius={[0, 4, 4, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Daily Activity Line Chart */}
            <div className="p-6 bg-white/5 backdrop-blur-lg rounded-xl border border-white/10 shadow-xl">
                <h2 className="text-xl font-semibold mb-4 text-blue-200">Listen History (30 Days)</h2>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dailyActivity}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                            <XAxis dataKey="date" tick={{ fill: '#aaa', fontSize: 10 }} />
                            <YAxis tick={{ fill: '#aaa' }} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1a1a1a', border: 'none', borderRadius: '8px' }}
                                itemStyle={{ color: '#fff' }}
                            />
                            <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
