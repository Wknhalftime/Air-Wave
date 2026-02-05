import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Download, TrendingUp, CheckCircle, XCircle, Brain } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { useState } from 'react';

interface VictoryStats {
    total_logs: number;
    matched_logs: number;
    unmatched_logs: number;
    match_rate: number;
    verified_count: number;
    auto_matched_count: number;
    bridge_count: number;
    breakdown: { type: string; count: number }[];
}

export default function Reports() {
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [stationId, setStationId] = useState<number | null>(null);
    const [exportType, setExportType] = useState<'all' | 'matched' | 'unmatched'>('all');

    // Fetch victory stats
    const { data: victory, isLoading } = useQuery<VictoryStats>({
        queryKey: ['analytics', 'victory'],
        queryFn: () => fetcher('/analytics/victory')
    });

    // Fetch stations for dropdown
    const { data: stations } = useQuery<{ id: number, callsign: string }[]>({
        queryKey: ['stations'],
        queryFn: () => fetcher('/stations')
    });

    // Handle CSV download
    const handleExport = () => {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (stationId) params.append('station_id', stationId.toString());
        if (exportType === 'matched') params.append('matched_only', 'true');
        if (exportType === 'unmatched') params.append('unmatched_only', 'true');

        // Direct window open downloads the file
        // For production, using blob logic is better for auth handling, but window.open works for cookie/basic scenarios
        // Assuming base URL needs to be handled:
        const baseUrl = 'http://localhost:8000/api/v1'; // Should come from config
        window.open(`${baseUrl}/export/logs?${params.toString()}`, '_blank');
    };

    // Pie chart colors (8 distinct colors for match categories)
    const COLORS = [
        '#8b5cf6', // Purple - Identity Bridge
        '#3b82f6', // Blue - Exact Match
        '#10b981', // Green - High Confidence
        '#ec4899', // Pink - Vector Similarity
        '#f59e0b', // Orange - Title + Vector
        '#06b6d4', // Cyan - User Verified
        '#8b5cf6', // Purple variant - Auto-Promoted
        '#6b7280', // Gray - Other
    ];

    if (isLoading) return <div className="p-8 text-center text-gray-500">Loading analytics...</div>;

    return (
        <div className="space-y-8">
            <div className="flex items-center gap-3">
                <TrendingUp className="w-8 h-8 text-indigo-600" />
                <h1 className="text-3xl font-bold text-gray-900">Reports & Export</h1>
            </div>

            {/* Victory Section */}
            <div className="space-y-6">
                <h2 className="text-2xl font-semibold text-gray-800">Victory Analytics</h2>

                {/* Big Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white p-6 rounded-xl shadow-lg transform transition-transform hover:scale-105">
                        <div className="text-4xl font-bold">{victory?.match_rate}%</div>
                        <div className="text-indigo-100 mt-2 font-medium">Global Match Rate</div>
                    </div>

                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <div className="flex items-center gap-2 text-green-600 mb-2">
                            <CheckCircle className="w-5 h-5" />
                            <span className="text-sm font-medium uppercase tracking-wide">Matched Logs</span>
                        </div>
                        <div className="text-3xl font-bold text-gray-900">
                            {victory?.matched_logs.toLocaleString()}
                        </div>
                    </div>

                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <div className="flex items-center gap-2 text-red-600 mb-2">
                            <XCircle className="w-5 h-5" />
                            <span className="text-sm font-medium uppercase tracking-wide">Unmatched Logs</span>
                        </div>
                        <div className="text-3xl font-bold text-gray-900">
                            {victory?.unmatched_logs.toLocaleString()}
                        </div>
                    </div>

                    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                        <div className="flex items-center gap-2 text-purple-600 mb-2">
                            <Brain className="w-5 h-5" />
                            <span className="text-sm font-medium uppercase tracking-wide">Learned (Identity)</span>
                        </div>
                        <div className="text-3xl font-bold text-gray-900">
                            {victory?.bridge_count.toLocaleString()}
                        </div>
                    </div>
                </div>

                {/* Pie Chart */}
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-xl font-semibold mb-4 text-gray-800">Match Type Distribution</h3>
                    <div className="h-80 w-full min-w-0">
                        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                            <PieChart>
                                <Pie
                                    data={victory?.breakdown}
                                    dataKey="count"
                                    nameKey="type"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={100}
                                    label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                                >
                                    {victory?.breakdown.map((_, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Export Section */}
            <div className="space-y-6">
                <hr className="border-gray-200" />
                <h2 className="text-2xl font-semibold text-gray-800">Export Data</h2>

                <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        {/* Date Range */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Start Date
                            </label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                End Date
                            </label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                            />
                        </div>

                        {/* Station Filter */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Station (Optional)
                            </label>
                            <select
                                value={stationId || ''}
                                onChange={(e) => setStationId(e.target.value ? Number(e.target.value) : null)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                            >
                                <option value="">All Stations</option>
                                {stations?.map((s) => (
                                    <option key={s.id} value={s.id}>{s.callsign}</option>
                                ))}
                            </select>
                        </div>

                        {/* Export Type */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Export Type
                            </label>
                            <select
                                value={exportType}
                                onChange={(e) => setExportType(e.target.value as any)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                            >
                                <option value="all">All Logs</option>
                                <option value="matched">Matched Only</option>
                                <option value="unmatched">Unmatched Only</option>
                            </select>
                        </div>
                    </div>

                    <button
                        onClick={handleExport}
                        className="w-full md:w-auto px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center justify-center gap-2 font-medium shadow-md transition-all hover:shadow-lg focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                        <Download className="w-5 h-5" />
                        Download CSV Report
                    </button>
                    <p className="mt-4 text-sm text-gray-500">
                        Exports a localized CSV file.
                    </p>
                </div>
            </div>
        </div>
    );
}
