import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Upload, Settings, Activity, FolderSync } from 'lucide-react';
import { TaskProgress } from '../components/TaskProgress';

interface SystemSetting {
    key: string;
    value: string;
    description: string;
}

export default function Admin() {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState<'status' | 'import' | 'settings'>('status');

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

    // --- Import Tab ---
    const [file, setFile] = useState<File | null>(null);
    const [legacyPath, setLegacyPath] = useState("D:\\PythonStuff\\airwave-original\\data\\imports");

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
            return fetcher<{ status: string, task_id: string }>('/admin/import-folder', {
                method: 'POST',
                body: JSON.stringify({ path: legacyPath }),
                headers: { 'Content-Type': 'application/json' }
            });
        },
        onSuccess: (data) => setImportTaskId(data.task_id)
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

    // --- Settings Tab ---
    const { data: settings, isLoading } = useQuery<SystemSetting[]>({
        queryKey: ['admin', 'settings'],
        queryFn: () => fetcher('/admin/settings')
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
                    onClick={() => setActiveTab('status')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'status' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    System Status
                </button>
                <button
                    onClick={() => setActiveTab('import')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'import' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    Data Import
                </button>
                <button
                    onClick={() => setActiveTab('settings')}
                    className={`pb-2 px-4 font-medium transition-colors ${activeTab === 'settings' ? 'border-b-2 border-indigo-600 text-indigo-600' : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    Settings
                </button>
            </div>

            {/* Content */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 min-h-[400px]">

                {activeTab === 'status' && (
                    <div className="space-y-6">
                        <h2 className="text-xl font-semibold mb-4">Operations</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                                <TaskProgress taskId={scanTaskId} onComplete={() => setScanTaskId(null)} />
                            </div>

                            <TaskProgress taskId={scanTaskId} onComplete={() => setScanTaskId(null)} />
                        </div>

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
                            <TaskProgress taskId={syncTaskId} onComplete={() => setSyncTaskId(null)} />
                        </div>

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

                {activeTab === 'import' && (
                    <div className="space-y-6">
                        {/* CSV Upload */}
                        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                                <Upload className="w-5 h-5 text-blue-500" />
                                Single CSV Upload
                            </h2>
                            <div className="flex gap-4 items-center">
                                <input
                                    type="file"
                                    accept=".csv"
                                    onChange={handleFileChange}
                                    className="block w-full text-sm text-gray-400
                                    file:mr-4 file:py-2 file:px-4
                                    file:rounded-full file:border-0
                                    file:text-sm file:font-semibold
                                    file:bg-blue-600 file:text-white
                                    hover:file:bg-blue-700"
                                />
                                <button
                                    onClick={handleUpload}
                                    disabled={!file || importMutation.isPending}
                                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                                >
                                    {importMutation.isPending ? 'Uploading...' : 'Upload'}
                                </button>
                            </div>
                        </div>

                        {/* Legacy Bulk Import (Server-Side) */}
                        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                                <FolderSync className="w-5 h-5 text-green-500" />
                                Bulk Import (Server-Side)
                            </h2>
                            <p className="text-gray-400 mb-4 text-sm">
                                Recursively import all CSV files from a folder on the server.
                            </p>
                            <div className="flex gap-4 flex-col md:flex-row">
                                <input
                                    type="text"
                                    value={legacyPath}
                                    onChange={(e) => setLegacyPath(e.target.value)}
                                    className="bg-gray-700 border border-gray-600 rounded px-3 py-2 flex-grow text-white"
                                    placeholder="D:\OriginalData\Imports"
                                />
                                <button
                                    onClick={handleLegacyImport}
                                    disabled={legacyImportMutation.isPending || !!importTaskId}
                                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 whitespace-nowrap"
                                >
                                    {legacyImportMutation.isPending ? 'Starting...' : 'Start Bulk Import'}
                                </button>
                            </div>
                        </div>

                        {/* Progress */}
                        {importTaskId && (
                            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                                <h2 className="text-lg font-bold mb-4">Import Progress</h2>
                                <TaskProgress taskId={importTaskId} onComplete={() => setImportTaskId(null)} />
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'settings' && (
                    <div className="space-y-6 max-w-2xl">
                        <h2 className="text-xl font-semibold mb-4">Configuration</h2>
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
                )}
            </div>
        </div >
    );
}
