import { Link, Outlet, useLocation } from 'react-router-dom';
import { Home, ListMusic, History, Activity, BarChart3, Settings, CheckSquare, Radio, Brain, TrendingUp } from 'lucide-react';
import { clsx } from 'clsx';
import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { GlobalTaskProgress } from '../components/GlobalTaskProgress';

export default function MainLayout() {
    const location = useLocation();

    const { data: health } = useQuery({
        queryKey: ['system', 'health'],
        queryFn: () => fetcher<{ status: string, database: string }>('/system/health'),
        refetchInterval: 30000
    });

    const links = [
        { to: '/', label: 'Dashboard', icon: Home },
        { to: '/stations', label: 'Stations', icon: Radio },
        { to: '/identity', label: 'Identity', icon: Brain },
        { to: '/reports', label: 'Reports', icon: TrendingUp },
        { to: '/library', label: 'Library', icon: ListMusic },
        { to: '/history', label: 'History', icon: History },
        { to: '/analytics', label: 'Analytics', icon: BarChart3 },
        { to: '/verification', label: 'Reviews', icon: CheckSquare },
    ];

    return (
        <div className="flex h-screen bg-gray-50 text-gray-900 font-sans">
            {/* Sidebar */}
            <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
                <div className="p-6 border-b border-gray-100">
                    <h1 className="text-xl font-bold text-indigo-600 tracking-tight flex items-center gap-2">
                        <Activity className="w-6 h-6" />
                        Airwave
                    </h1>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    {links.map((link) => {
                        const Icon = link.icon;
                        const isActive = location.pathname === link.to;
                        return (
                            <Link
                                key={link.to}
                                to={link.to}
                                className={clsx(
                                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                                    isActive
                                        ? "bg-indigo-50 text-indigo-700"
                                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                                )}
                            >
                                <Icon className="w-5 h-5" />
                                {link.label}
                            </Link>
                        );
                    })}
                </nav>

                {/* Status Footer */}
                <div className="mt-auto">
                    {/* Global Task Progress */}
                    <div className="px-4 pb-3">
                        <GlobalTaskProgress />
                    </div>

                    <div className="p-4 border-t border-gray-100 text-xs">
                        <Link to="/admin" className="flex items-center gap-2 text-gray-500 hover:text-indigo-600 mb-4 transition-colors">
                            <Settings className="w-4 h-4" />
                            <span>Administration</span>
                        </Link>

                        <div className="flex items-center justify-between text-gray-500">
                            <span>System Status</span>
                            <span className={clsx(
                                "w-2 h-2 rounded-full",
                                health?.status === 'ok' ? "bg-green-500" : "bg-red-500"
                            )} />
                        </div>
                        <div className="mt-1 text-gray-400">
                            DB: {health?.database || 'Connecting...'}
                        </div>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto flex flex-col">
                {/* Top Header */}
                <header className="bg-white border-b border-gray-200 px-8 py-4 sticky top-0 z-10">
                    <div className="max-w-3xl">
                        <div className="relative">
                            <Activity className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search library, logs, and history..."
                                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all shadow-sm"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        const target = e.target as HTMLInputElement;
                                        if (target.value.trim()) {
                                            window.location.href = `/search?q=${encodeURIComponent(target.value)}`;
                                        }
                                    }
                                }}
                            />
                        </div>
                    </div>
                </header>

                <div className="p-8 max-w-7xl mx-auto w-full">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
