import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sliders, Radio, Music, ListMusic, Plus, Trash2, AlertCircle } from 'lucide-react';
import { fetcher } from '../lib/api';
import {
    useStationPreferences,
    useCreateStationPreference,
    useDeleteStationPreference,
    useFormatPreferences,
    useCreateFormatPreference,
    useDeleteFormatPreference,
    useWorkDefaults,
    useCreateWorkDefault,
    useDeleteWorkDefault,
    useFormatCodes,
    type StationPreference,
    type FormatPreference,
    type WorkDefault,
} from '../hooks/usePreferences';

interface Station {
    id: number;
    callsign: string;
    format_code: string | null;
}

interface Work {
    id: number;
    title: string;
}

interface Recording {
    id: number;
    title: string;
    version_type: string | null;
    work_id: number;
}

export default function Preferences() {
    const [activeTab, setActiveTab] = useState<'station' | 'format' | 'default'>('station');

    return (
        <div className="space-y-6 animate-fade-in">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
                <Sliders className="w-8 h-8 text-gray-600" />
                Recording Preferences
            </h1>

            <p className="text-gray-600">
                Configure which recording version should be used for broadcasts based on station, format, or work defaults.
            </p>

            {/* Tabs */}
            <div className="flex space-x-4 border-b border-gray-200">
                <button
                    onClick={() => setActiveTab('station')}
                    className={`pb-2 px-4 font-medium transition-colors flex items-center gap-2 ${activeTab === 'station'
                        ? 'border-b-2 border-indigo-600 text-indigo-600'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <Radio className="w-4 h-4" />
                    Station
                </button>
                <button
                    onClick={() => setActiveTab('format')}
                    className={`pb-2 px-4 font-medium transition-colors flex items-center gap-2 ${activeTab === 'format'
                        ? 'border-b-2 border-indigo-600 text-indigo-600'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <Music className="w-4 h-4" />
                    Format
                </button>
                <button
                    onClick={() => setActiveTab('default')}
                    className={`pb-2 px-4 font-medium transition-colors flex items-center gap-2 ${activeTab === 'default'
                        ? 'border-b-2 border-indigo-600 text-indigo-600'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <ListMusic className="w-4 h-4" />
                    Work Defaults
                </button>
            </div>

            {/* Content */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 min-h-[400px]">
                {activeTab === 'station' && <StationPreferencesTab />}
                {activeTab === 'format' && <FormatPreferencesTab />}
                {activeTab === 'default' && <WorkDefaultsTab />}
            </div>
        </div>
    );
}

// =============================================================================
// Station Preferences Tab
// =============================================================================

function StationPreferencesTab() {
    const [showForm, setShowForm] = useState(false);
    const [filterStationId, setFilterStationId] = useState<number | undefined>();

    const { data: stations } = useQuery({
        queryKey: ['stations'],
        queryFn: () => fetcher<Station[]>('/stations'),
    });

    const { data: preferences, isLoading } = useStationPreferences(filterStationId);
    const deletePreference = useDeleteStationPreference();

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Station Preferences</h2>
                    <p className="text-sm text-gray-500 mt-1">
                        Set specific recording preferences for individual stations.
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    <Plus className="w-4 h-4" />
                    Add Preference
                </button>
            </div>

            {/* Filter */}
            <div className="flex items-center gap-4">
                <label className="text-sm font-medium text-gray-700">Filter by Station:</label>
                <select
                    value={filterStationId || ''}
                    onChange={(e) => setFilterStationId(e.target.value ? Number(e.target.value) : undefined)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
                >
                    <option value="">All Stations</option>
                    {stations?.map((station) => (
                        <option key={station.id} value={station.id}>
                            {station.callsign} {station.format_code ? `(${station.format_code})` : ''}
                        </option>
                    ))}
                </select>
            </div>

            {/* Form Modal */}
            {showForm && (
                <StationPreferenceForm
                    stations={stations || []}
                    onClose={() => setShowForm(false)}
                />
            )}

            {/* Preferences List */}
            {isLoading ? (
                <div className="text-center py-8 text-gray-500">Loading preferences...</div>
            ) : preferences?.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                    No station preferences configured yet.
                </div>
            ) : (
                <div className="space-y-3">
                    {preferences?.map((pref) => (
                        <div
                            key={pref.id}
                            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
                        >
                            <div className="flex-1">
                                <div className="flex items-center gap-3">
                                    <span className="font-medium text-indigo-600">
                                        {pref.station?.callsign || `Station #${pref.station_id}`}
                                    </span>
                                    <span className="text-gray-400">→</span>
                                    <span className="font-medium">
                                        {pref.work?.title || `Work #${pref.work_id}`}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-500 mt-1">
                                    Preferred: {pref.preferred_recording?.title || 'Unknown'}
                                    {pref.preferred_recording?.version_type && (
                                        <span className="ml-1 text-gray-400">
                                            ({pref.preferred_recording.version_type})
                                        </span>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => deletePreference.mutate(pref.id)}
                                disabled={deletePreference.isPending}
                                className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function StationPreferenceForm({
    stations,
    onClose,
}: {
    stations: Station[];
    onClose: () => void;
}) {
    const [stationId, setStationId] = useState<number | ''>('');
    const [workId, setWorkId] = useState<number | ''>('');
    const [recordingId, setRecordingId] = useState<number | ''>('');
    const [error, setError] = useState<string | null>(null);

    const createPreference = useCreateStationPreference();

    const { data: recordings } = useQuery({
        queryKey: ['work', workId, 'recordings'],
        queryFn: () => fetcher<Recording[]>(`/library/works/${workId}/recordings`),
        enabled: !!workId,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!stationId || !workId || !recordingId) {
            setError('Please fill in all fields');
            return;
        }

        try {
            await createPreference.mutateAsync({
                station_id: stationId as number,
                work_id: workId as number,
                preferred_recording_id: recordingId as number,
            });
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to create preference');
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
                <h3 className="text-lg font-semibold mb-4">Add Station Preference</h3>

                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Station
                        </label>
                        <select
                            value={stationId}
                            onChange={(e) => setStationId(Number(e.target.value))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            required
                        >
                            <option value="">Select a station...</option>
                            {stations.map((station) => (
                                <option key={station.id} value={station.id}>
                                    {station.callsign}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Work ID
                        </label>
                        <input
                            type="number"
                            value={workId}
                            onChange={(e) => {
                                setWorkId(Number(e.target.value));
                                setRecordingId('');
                            }}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            placeholder="Enter work ID"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Preferred Recording
                        </label>
                        <select
                            value={recordingId}
                            onChange={(e) => setRecordingId(Number(e.target.value))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            disabled={!workId || !recordings}
                            required
                        >
                            <option value="">Select a recording...</option>
                            {recordings?.map((rec) => (
                                <option key={rec.id} value={rec.id}>
                                    {rec.title}
                                    {rec.version_type ? ` (${rec.version_type})` : ''}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={createPreference.isPending}
                            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                        >
                            {createPreference.isPending ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// =============================================================================
// Format Preferences Tab
// =============================================================================

function FormatPreferencesTab() {
    const [showForm, setShowForm] = useState(false);
    const [filterFormat, setFilterFormat] = useState<string | undefined>();

    const { data: formatCodes } = useFormatCodes();
    const { data: preferences, isLoading } = useFormatPreferences(filterFormat);
    const deletePreference = useDeleteFormatPreference();

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Format Preferences</h2>
                    <p className="text-sm text-gray-500 mt-1">
                        Set recording preferences based on station format (AC, CHR, ROCK, etc.).
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    <Plus className="w-4 h-4" />
                    Add Preference
                </button>
            </div>

            {/* Filter */}
            <div className="flex items-center gap-4">
                <label className="text-sm font-medium text-gray-700">Filter by Format:</label>
                <select
                    value={filterFormat || ''}
                    onChange={(e) => setFilterFormat(e.target.value || undefined)}
                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500"
                >
                    <option value="">All Formats</option>
                    {formatCodes?.map((code) => (
                        <option key={code} value={code}>
                            {code}
                        </option>
                    ))}
                </select>
            </div>

            {/* Form Modal */}
            {showForm && (
                <FormatPreferenceForm
                    formatCodes={formatCodes || []}
                    onClose={() => setShowForm(false)}
                />
            )}

            {/* Preferences List */}
            {isLoading ? (
                <div className="text-center py-8 text-gray-500">Loading preferences...</div>
            ) : preferences?.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                    No format preferences configured yet.
                </div>
            ) : (
                <div className="space-y-3">
                    {preferences?.map((pref) => (
                        <div
                            key={pref.id}
                            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
                        >
                            <div className="flex-1">
                                <div className="flex items-center gap-3">
                                    <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded font-medium text-sm">
                                        {pref.format_code}
                                    </span>
                                    <span className="text-gray-400">→</span>
                                    <span className="font-medium">
                                        {pref.work?.title || `Work #${pref.work_id}`}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-500 mt-1">
                                    Preferred: {pref.preferred_recording?.title || 'Unknown'}
                                    {pref.preferred_recording?.version_type && (
                                        <span className="ml-1 text-gray-400">
                                            ({pref.preferred_recording.version_type})
                                        </span>
                                    )}
                                    {pref.exclude_tags.length > 0 && (
                                        <span className="ml-2 text-orange-600">
                                            Excludes: {pref.exclude_tags.join(', ')}
                                        </span>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => deletePreference.mutate(pref.id)}
                                disabled={deletePreference.isPending}
                                className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function FormatPreferenceForm({
    formatCodes,
    onClose,
}: {
    formatCodes: string[];
    onClose: () => void;
}) {
    const [formatCode, setFormatCode] = useState('');
    const [workId, setWorkId] = useState<number | ''>('');
    const [recordingId, setRecordingId] = useState<number | ''>('');
    const [excludeTags, setExcludeTags] = useState('');
    const [error, setError] = useState<string | null>(null);

    const createPreference = useCreateFormatPreference();

    const { data: recordings } = useQuery({
        queryKey: ['work', workId, 'recordings'],
        queryFn: () => fetcher<Recording[]>(`/library/works/${workId}/recordings`),
        enabled: !!workId,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formatCode || !workId || !recordingId) {
            setError('Please fill in all required fields');
            return;
        }

        try {
            await createPreference.mutateAsync({
                format_code: formatCode,
                work_id: workId as number,
                preferred_recording_id: recordingId as number,
                exclude_tags: excludeTags ? excludeTags.split(',').map((t) => t.trim()) : [],
            });
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to create preference');
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
                <h3 className="text-lg font-semibold mb-4">Add Format Preference</h3>

                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Format Code
                        </label>
                        <input
                            type="text"
                            value={formatCode}
                            onChange={(e) => setFormatCode(e.target.value.toUpperCase())}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            placeholder="e.g., AC, CHR, ROCK"
                            list="format-codes"
                            required
                        />
                        <datalist id="format-codes">
                            {formatCodes.map((code) => (
                                <option key={code} value={code} />
                            ))}
                        </datalist>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Work ID
                        </label>
                        <input
                            type="number"
                            value={workId}
                            onChange={(e) => {
                                setWorkId(Number(e.target.value));
                                setRecordingId('');
                            }}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            placeholder="Enter work ID"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Preferred Recording
                        </label>
                        <select
                            value={recordingId}
                            onChange={(e) => setRecordingId(Number(e.target.value))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            disabled={!workId || !recordings}
                            required
                        >
                            <option value="">Select a recording...</option>
                            {recordings?.map((rec) => (
                                <option key={rec.id} value={rec.id}>
                                    {rec.title}
                                    {rec.version_type ? ` (${rec.version_type})` : ''}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Exclude Tags (optional)
                        </label>
                        <input
                            type="text"
                            value={excludeTags}
                            onChange={(e) => setExcludeTags(e.target.value)}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            placeholder="e.g., explicit, live (comma separated)"
                        />
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={createPreference.isPending}
                            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                        >
                            {createPreference.isPending ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// =============================================================================
// Work Defaults Tab
// =============================================================================

function WorkDefaultsTab() {
    const [showForm, setShowForm] = useState(false);

    const { data: defaults, isLoading } = useWorkDefaults();
    const deleteDefault = useDeleteWorkDefault();

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Work Defaults</h2>
                    <p className="text-sm text-gray-500 mt-1">
                        Set the default recording for a work when no station or format preference applies.
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    <Plus className="w-4 h-4" />
                    Add Default
                </button>
            </div>

            {/* Form Modal */}
            {showForm && <WorkDefaultForm onClose={() => setShowForm(false)} />}

            {/* Defaults List */}
            {isLoading ? (
                <div className="text-center py-8 text-gray-500">Loading defaults...</div>
            ) : defaults?.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                    No work defaults configured yet.
                </div>
            ) : (
                <div className="space-y-3">
                    {defaults?.map((def) => (
                        <div
                            key={def.work_id}
                            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
                        >
                            <div className="flex-1">
                                <div className="font-medium">
                                    {def.work?.title || `Work #${def.work_id}`}
                                </div>
                                <div className="text-sm text-gray-500 mt-1">
                                    Default: {def.default_recording?.title || 'Unknown'}
                                    {def.default_recording?.version_type && (
                                        <span className="ml-1 text-gray-400">
                                            ({def.default_recording.version_type})
                                        </span>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => deleteDefault.mutate(def.work_id)}
                                disabled={deleteDefault.isPending}
                                className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function WorkDefaultForm({ onClose }: { onClose: () => void }) {
    const [workId, setWorkId] = useState<number | ''>('');
    const [recordingId, setRecordingId] = useState<number | ''>('');
    const [error, setError] = useState<string | null>(null);

    const createDefault = useCreateWorkDefault();

    const { data: recordings } = useQuery({
        queryKey: ['work', workId, 'recordings'],
        queryFn: () => fetcher<Recording[]>(`/library/works/${workId}/recordings`),
        enabled: !!workId,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!workId || !recordingId) {
            setError('Please fill in all fields');
            return;
        }

        try {
            await createDefault.mutateAsync({
                work_id: workId as number,
                default_recording_id: recordingId as number,
            });
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to create default');
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
                <h3 className="text-lg font-semibold mb-4">Set Work Default Recording</h3>

                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Work ID
                        </label>
                        <input
                            type="number"
                            value={workId}
                            onChange={(e) => {
                                setWorkId(Number(e.target.value));
                                setRecordingId('');
                            }}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            placeholder="Enter work ID"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Default Recording
                        </label>
                        <select
                            value={recordingId}
                            onChange={(e) => setRecordingId(Number(e.target.value))}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2"
                            disabled={!workId || !recordings}
                            required
                        >
                            <option value="">Select a recording...</option>
                            {recordings?.map((rec) => (
                                <option key={rec.id} value={rec.id}>
                                    {rec.title}
                                    {rec.version_type ? ` (${rec.version_type})` : ''}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={createDefault.isPending}
                            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                        >
                            {createDefault.isPending ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
