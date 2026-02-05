import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetcher } from '../lib/api';
import { Upload, Settings, Activity, FolderSync, CheckCircle, Radio, Brain, AlertTriangle } from 'lucide-react';
import { TaskProgress } from '../components/TaskProgress';
import { useTaskProgress } from '../hooks/useTaskProgress';

interface SystemSetting {
    key: string;
    value: string;
    description: string;
}

interface PipelineStats {
    total_logs: number;
    unmatched_logs: number;
    discovery_queue: number;
    total_tracks: number;
}

export default function Admin() {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState<'ingestion' | 'processing' | 'system'>('ingestion');

    // Track task IDs for progress - restore from localStorage on mount
    const [scanTaskId, setScanTaskId] = useState<string | null>(() => {
        return localStorage.getItem('airwave_scan_task_id');
    });
    const [syncTaskId, setSyncTaskId] = useState<string | null>(() => {
        return localStorage.getItem('airwave_sync_task_id');
    });
    const [importTaskId, setImportTaskId] = useState<string | null>(() => {
        return localStorage.getItem('airwave_import_task_id');
    });
    const [discoveryTaskId, setDiscoveryTaskId] = useState<string | null>(() => {
        return localStorage.getItem('airwave_discovery_task_id');
    });

    // Persist task IDs to localStorage when they change
    useEffect(() => {
        if (scanTaskId) {
            localStorage.setItem('airwave_scan_task_id', scanTaskId);
        } else {
            localStorage.removeItem('airwave_scan_task_id');
        }
    }, [scanTaskId]);

    useEffect(() => {
        if (syncTaskId) {
            localStorage.setItem('airwave_sync_task_id', syncTaskId);
        } else {
            localStorage.removeItem('airwave_sync_task_id');
        }
    }, [syncTaskId]);

    useEffect(() => {
        if (importTaskId) {
            localStorage.setItem('airwave_import_task_id', importTaskId);
        } else {
            localStorage.removeItem('airwave_import_task_id');
        }
    }, [importTaskId]);

    useEffect(() => {
        if (discoveryTaskId) {
            localStorage.setItem('airwave_discovery_task_id', discoveryTaskId);
        } else {
            localStorage.removeItem('airwave_discovery_task_id');
        }
    }, [discoveryTaskId]);

    // --- Status Tab ---
    const scanMutation = useMutation({
        mutationFn: () => fetcher<{ status: string, task_id: string }>('/admin/trigger-scan', { method: 'POST' }),
        onSuccess: (data) => setScanTaskId(data.task_id)
    });

    const syncMutation = useMutation({
        mutationFn: (path: string) => fetcher<{ status: string, task_id: string }>('/admin/scan', {
            method: 'POST',
            body: JSON.stringify({ path: path || undefined }),
            headers: { 'Content-Type': 'application/json' }
        }),
        onSuccess: (data) => setSyncTaskId(data.task_id)
    });

    const discoveryMutation = useMutation({
        mutationFn: () => fetcher<{ status: string, task_id: string }>('/admin/trigger-discovery', { method: 'POST' }),
        onSuccess: (data) => setDiscoveryTaskId(data.task_id)
    });

    // --- Import Tab ---
    const [file, setFile] = useState<File | null>(null);
    const [legacyPath, setLegacyPath] = useState("D:\\PythonStuff\\airwave-new\\backend\\data\\imports");
    const [bulkImportError, setBulkImportError] = useState<string | null>(null);

    const importMutation = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            // Use relative path to hit the Vite proxy
            const res = await fetch('/api/v1/admin/import', {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error("Upload Failed");
            return res.json();
        },
        onSuccess: (data) => setImportTaskId(data.task_id)
    });

    const legacyImportMutation = useMutation({
        mutationFn: async () => {
            setBulkImportError(null); // Clear previous errors
            return fetcher<{ status: string, task_id: string }>('/admin/import-folder', {
                method: 'POST',
                body: JSON.stringify({ path: legacyPath }),
                headers: { 'Content-Type': 'application/json' }
            });
        },
        onSuccess: (data) => {
            setImportTaskId(data.task_id);
            setBulkImportError(null);
        },
        onError: (error: any) => {
            console.error('Bulk import failed:', error);

            // Extract error message from response
            let errorMessage = 'Unknown error occurred';
            if (error.detail) {
                errorMessage = error.detail;
            } else if (error.message) {
                errorMessage = error.message;
            }

            setBulkImportError(errorMessage);
        }
    });

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) setFile(e.target.files[0]);
    };

    const handleUpload = () => {
        if (file) importMutation.mutate(file);
    };

    const handleLegacyImport = () => {
        legacyImportMutation.mutate();
    };

    // Track task statuses for success wizards
    const { status: importStatus } = useTaskProgress(importTaskId);
    const { status: scanStatus } = useTaskProgress(scanTaskId);
    const { status: syncStatus } = useTaskProgress(syncTaskId);
    const { status: discoveryStatus } = useTaskProgress(discoveryTaskId);

    // --- Settings Tab ---
    const { data: settings, isLoading } = useQuery<SystemSetting[]>({
        queryKey: ['admin', 'settings'],
        queryFn: () => fetcher('/admin/settings')
    });

    // --- Pipeline Stats ---
    const { data: stats } = useQuery<PipelineStats>({
        queryKey: ['admin', 'pipeline'],
        queryFn: () => fetcher('/admin/pipeline-stats'),
        refetchInterval: 5000 // Refresh every 5s
    });

    // Helper to get value
    const getSetting = (key: string) => settings?.find(s => s.key === key)?.value || '';

    const saveSettingMutation = useMutation({
        mutationFn: (setting: { key: string, value: string }) => fetcher('/admin/settings', {
            method: 'POST',
            body: JSON.stringify(setting),
            headers: { 'Content-Type': 'application/json' }
        }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'settings'] })
    });

    return (
        <div className="space-y-6 animate-fade-in">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
                <Settings className="w-8 h-8 text-gray-600" />
                System Administration
            </h1>

            {/* Tabs */}
            <div className="flex space-x-4 border-b border-gray-200">
                <button
                    onClick={() => setActiveTab('ingestion')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'ingestion' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    Ingestion
                </button>
                <button
                    onClick={() => setActiveTab('processing')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'processing' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    Processing
                </button>
                <button
                    onClick={() => setActiveTab('system')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'system' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    System
                </button>
            </div>

            {/* Content */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 min-h-[400px]">

                {activeTab === 'processing' && (
                    <div className="space-y-6">
                        <h2 className="text-xl font-semibold mb-4">Processing Operations</h2>

                        {/* Pipeline Dashboard */}
                        {stats && (
                            <div className="grid grid-cols-4 gap-4 mb-8">
                                <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
                                    <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Total Ingested</div>
                                    <div className="text-2xl font-bold text-gray-900">{stats.total_logs.toLocaleString()}</div>
                                    <div className="text-xs text-gray-400 mt-1">Broadcast Logs</div>
                                </div>
                                <div className="p-4 bg-white border border-red-100 rounded-xl shadow-sm relative overflow-hidden">
                                    <div className="absolute top-0 right-0 p-2 opacity-10">
                                        <AlertTriangle className="w-12 h-12 text-red-500" />
                                    </div>
                                    <div className="text-xs font-medium text-red-600 uppercase tracking-wider mb-1">Unmatched</div>
                                    <div className="text-2xl font-bold text-red-700">{stats.unmatched_logs.toLocaleString()}</div>
                                    <div className="text-xs text-red-500 mt-1">Pending Processing</div>
                                </div>
                                <div className="p-4 bg-white border border-blue-100 rounded-xl shadow-sm relative overflow-hidden">
                                    <div className="absolute top-0 right-0 p-2 opacity-10">
                                        <Brain className="w-12 h-12 text-blue-500" />
                                    </div>
                                    <div className="text-xs font-medium text-blue-600 uppercase tracking-wider mb-1">Discovery Queue</div>
                                    <div className="text-2xl font-bold text-blue-700">{stats.discovery_queue.toLocaleString()}</div>
                                    <div className="text-xs text-blue-500 mt-1">Aggregated Signatures</div>
                                </div>
                                <div className="p-4 bg-white border border-green-100 rounded-xl shadow-sm relative overflow-hidden">
                                    <div className="absolute top-0 right-0 p-2 opacity-10">
                                        <CheckCircle className="w-12 h-12 text-green-500" />
                                    </div>
                                    <div className="text-xs font-medium text-green-600 uppercase tracking-wider mb-1">Verified Library</div>
                                    <div className="text-2xl font-bold text-green-700">{stats.total_tracks.toLocaleString()}</div>
                                    <div className="text-xs text-green-500 mt-1">Active Recordings</div>
                                </div>
                            </div>
                        )}

                        {/* Run Discovery */}
                        <div className="p-4 border rounded-lg bg-blue-50 hover:bg-blue-100 transition border-blue-200">
                            <div className="flex items-center gap-3 mb-2">
                                <Brain className="w-5 h-5 text-blue-600" />
                                <h3 className="font-medium text-blue-900">Run Discovery</h3>
                            </div>
                            <p className="text-sm text-blue-700 mb-4">Rebuild Discovery Queue from unmatched logs.</p>
                            <button
                                onClick={() => discoveryMutation.mutate()}
                                disabled={discoveryMutation.isPending || !!discoveryTaskId}
                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 w-full disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                            >
                                {discoveryMutation.isPending ? 'Starting...' : discoveryTaskId ? 'Running...' : 'Run Discovery'}
                            </button>

                            {/* Progress */}
                            {discoveryTaskId && discoveryStatus?.status === 'running' && (
                                <TaskProgress taskId={discoveryTaskId} onComplete={() => setDiscoveryTaskId(null)} />
                            )}

                            {/* Success Wizard */}
                            {discoveryTaskId && discoveryStatus?.status === 'completed' && (
                                <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-4">
                                    <div className="flex items-start gap-3">
                                        <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                                        <div className="flex-1">
                                            <h4 className="font-semibold text-green-900 mb-1">Discovery Complete!</h4>
                                            <p className="text-sm text-green-700 mb-3">
                                                Queue rebuilt with <strong>{discoveryStatus.total.toLocaleString()}</strong> items.
                                            </p>
                                            <div className="flex gap-2 flex-wrap">
                                                <Link
                                                    to="/verification"
                                                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 font-medium transition-colors"
                                                >
                                                    Review Queue
                                                </Link>
                                                <button
                                                    onClick={() => setDiscoveryTaskId(null)}
                                                    className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300 font-medium transition-colors"
                                                >
                                                    Dismiss
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Scan Logs */}
                        <div className="p-4 border rounded-lg bg-gray-50 hover:bg-gray-100 transition">
                            <div className="flex items-center gap-3 mb-2">
                                <Activity className="w-5 h-5 text-blue-600" />
                                <h3 className="font-medium">Scan Logs</h3>
                            </div>
                            <p className="text-sm text-gray-500 mb-4">Promote new logs to Library Tracks.</p>
                            <button
                                onClick={() => scanMutation.mutate()}
                                disabled={scanMutation.isPending || !!scanTaskId}
                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 w-full disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {scanMutation.isPending ? 'Starting...' : scanTaskId ? 'Running...' : 'Trigger Scan'}
                            </button>

                            {/* Progress */}
                            {scanTaskId && scanStatus?.status === 'running' && (
                                <TaskProgress taskId={scanTaskId} onComplete={() => setScanTaskId(null)} />
                            )}

                            {/* Success Wizard */}
                            {scanTaskId && scanStatus?.status === 'completed' && (
                                <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-4">
                                    <div className="flex items-start gap-3">
                                        <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                                        <div className="flex-1">
                                            <h4 className="font-semibold text-green-900 mb-1">Scan Complete!</h4>
                                            <p className="text-sm text-green-700 mb-3">
                                                Processed <strong>{scanStatus.total.toLocaleString()}</strong> items.
                                            </p>
                                            <div className="flex gap-2 flex-wrap">
                                                <Link
                                                    to="/library"
                                                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 font-medium transition-colors"
                                                >
                                                    View Library
                                                </Link>
                                                <button
                                                    onClick={() => setScanTaskId(null)}
                                                    className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300 font-medium transition-colors"
                                                >
                                                    Dismiss
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Match Tuner */}
                        <div className="p-4 border rounded-lg bg-gray-50 hover:bg-gray-100 transition">
                            <div className="flex items-center gap-3 mb-2">
                                <Settings className="w-5 h-5 text-purple-600" />
                                <h3 className="font-medium">Match Tuner</h3>
                            </div>
                            <p className="text-sm text-gray-500 mb-4">Calibrate match intelligence and thresholds.</p>
                            <a
                                href="/admin/tuner"
                                className="block text-center px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 w-full"
                            >
                                Open Tuner
                            </a>
                        </div>
                    </div>
                )}

                {activeTab === 'ingestion' && (
                    <div className="space-y-6">
                        {/* CSV Upload */}
                        <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
                            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                                <Upload className="w-5 h-5 text-blue-600" />
                                Single CSV Upload
                            </h2>
                            <div className="flex gap-4 items-center">
                                <input
                                    type="file"
                                    accept=".csv"
                                    onChange={handleFileChange}
                                    className="block w-full text-sm text-gray-600
                                    file:mr-4 file:py-2 file:px-4
                                    file:rounded-full file:border-0
                                    file:text-sm file:font-semibold
                                    file:bg-blue-600 file:text-white
                                    hover:file:bg-blue-700 transition"
                                />
                                <button
                                    onClick={handleUpload}
                                    disabled={!file || importMutation.isPending}
                                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition font-medium"
                                >
                                    {importMutation.isPending ? 'Uploading...' : 'Upload'}
                                </button>
                            </div>
                        </div>

                        {/* Legacy Bulk Import (Server-Side) */}
                        <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
                            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                                <FolderSync className="w-5 h-5 text-green-600" />
                                Bulk Import (Server-Side)
                            </h2>
                            <p className="text-gray-600 mb-4 text-sm font-medium">
                                Recursively import all CSV files from a folder on the server.
                            </p>

                            {/* Error Display */}
                            {bulkImportError && (
                                <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
                                    <div className="flex items-start gap-3">
                                        <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                                        <div className="flex-1">
                                            <h4 className="font-semibold text-red-900 mb-1">Import Failed</h4>
                                            <p className="text-sm text-red-700 mb-2">{bulkImportError}</p>
                                            <div className="text-xs text-red-600 bg-red-100 rounded px-2 py-1 font-mono">
                                                💡 Tip: Make sure the path exists on the server and is accessible
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => setBulkImportError(null)}
                                            className="text-red-400 hover:text-red-600 transition-colors"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                </div>
                            )}

                            <div className="flex gap-4 flex-col md:flex-row">
                                <input
                                    type="text"
                                    value={legacyPath}
                                    onChange={(e) => {
                                        setLegacyPath(e.target.value);
                                        setBulkImportError(null); // Clear error when user types
                                    }}
                                    className="bg-white border border-gray-300 rounded-lg px-4 py-2 flex-grow text-gray-900 focus:ring-2 focus:ring-indigo-500 transition-all font-mono text-sm"
                                    placeholder="e.g. D:\Music\Imports"
                                />
                                <button
                                    onClick={handleLegacyImport}
                                    disabled={!legacyPath || legacyImportMutation.isPending || !!importTaskId}
                                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 shadow-sm transition-all font-medium whitespace-nowrap"
                                >
                                    {legacyImportMutation.isPending ? 'Starting...' : 'Start Bulk Import'}
                                </button>
                            </div>
                        </div>

                        {/* Progress & Success Wizard */}
                        {importTaskId && importStatus?.status === 'running' && (
                            <div className="bg-gray-50 p-6 rounded-lg border border-gray-200">
                                <h2 className="text-lg font-bold text-gray-900 mb-4">Import Progress</h2>
                                <TaskProgress taskId={importTaskId} onComplete={() => setImportTaskId(null)} />
                            </div>
                        )}

                        {/* Success Wizard */}
                        {importTaskId && importStatus?.status === 'completed' && (
                            <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                                <div className="flex items-start gap-4">
                                    <CheckCircle className="w-8 h-8 text-green-600 flex-shrink-0 mt-1" />
                                    <div className="flex-1">
                                        <h3 className="text-xl font-bold text-green-900 mb-2">
                                            Import Complete! 🎉
                                        </h3>
                                        <p className="text-green-700 mb-4">
                                            Successfully imported <strong>{importStatus.total.toLocaleString()}</strong> broadcast logs.
                                        </p>
                                        <div className="flex gap-3 flex-wrap">
                                            <Link
                                                to="/stations"
                                                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
                                            >
                                                <Radio className="w-4 h-4" />
                                                View Station Hub
                                            </Link>
                                            <button
                                                onClick={() => {
                                                    setImportTaskId(null);
                                                    setFile(null);
                                                }}
                                                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 font-medium transition-colors"
                                            >
                                                Import Another CSV
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Sync Files */}
                        <div className="p-4 border rounded-lg bg-gray-50 hover:bg-gray-100 transition">
                            <div className="flex items-center gap-3 mb-2">
                                <FolderSync className="w-5 h-5 text-green-600" />
                                <h3 className="font-medium">Sync Files</h3>
                            </div>
                            <p className="text-sm text-gray-500 mb-4">Scan local Music Directory for matches.</p>
                            <button
                                onClick={() => syncMutation.mutate(getSetting('music_dir'))}
                                disabled={syncMutation.isPending || !!syncTaskId}
                                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 w-full disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {syncMutation.isPending ? 'Starting...' : syncTaskId ? 'Running...' : 'Start Sync'}
                            </button>

                            {/* Progress */}
                            {syncTaskId && syncStatus?.status === 'running' && (
                                <TaskProgress taskId={syncTaskId} onComplete={() => setSyncTaskId(null)} />
                            )}

                            {/* Success Wizard */}
                            {syncTaskId && syncStatus?.status === 'completed' && (
                                <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-4">
                                    <div className="flex items-start gap-3">
                                        <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                                        <div className="flex-1">
                                            <h4 className="font-semibold text-green-900 mb-1">Sync Complete!</h4>
                                            <p className="text-sm text-green-700 mb-3">
                                                Synced <strong>{syncStatus.total.toLocaleString()}</strong> files.
                                            </p>
                                            <div className="flex gap-2 flex-wrap">
                                                <Link
                                                    to="/library"
                                                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 font-medium transition-colors"
                                                >
                                                    View Library
                                                </Link>
                                                <button
                                                    onClick={() => setSyncTaskId(null)}
                                                    className="px-3 py-1.5 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300 font-medium transition-colors"
                                                >
                                                    Dismiss
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'system' && (
                    <div className="space-y-6">
                        <h2 className="text-xl font-semibold mb-4">System Configuration</h2>

                        {/* Settings */}
                        <div className="max-w-2xl">
                            {isLoading ? <p>Loading settings...</p> : (
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Music Directory</label>
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                defaultValue={getSetting('music_dir') || 'D:\\Media\\Music'}
                                                onBlur={(e) => saveSettingMutation.mutate({ key: 'music_dir', value: e.target.value })}
                                                className="flex-1 p-2 border rounded-md"
                                                placeholder="D:\Music"
                                            />
                                            <button className="px-3 py-2 bg-gray-200 rounded text-sm">Save</button>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-1">Path where local MP3/FLAC files are stored.</p>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">AcoustID API Key</label>
                                        <div className="flex gap-2">
                                            <input
                                                type="password"
                                                defaultValue={getSetting('acoustid_key')}
                                                onBlur={(e) => saveSettingMutation.mutate({ key: 'acoustid_key', value: e.target.value })}
                                                className="flex-1 p-2 border rounded-md"
                                            />
                                            <button className="px-3 py-2 bg-gray-200 rounded text-sm">Save</button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Health Status */}
                        <div className="p-4 border rounded-lg bg-gray-50">
                            <h3 className="font-medium mb-3 flex items-center gap-2">
                                <Activity className="w-5 h-5 text-green-600" />
                                System Health
                            </h3>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-gray-600">Backend Status:</span>
                                    <span className="text-green-600 font-medium">● Online</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-600">Database:</span>
                                    <span className="text-green-600 font-medium">● Connected</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-600">Vector Search:</span>
                                    <span className="text-green-600 font-medium">● Ready</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div >
    );
}
