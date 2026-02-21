import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetcher } from '../lib/api';

// =============================================================================
// TypeScript Interfaces (matching backend Pydantic schemas)
// =============================================================================

interface RecordingInfo {
    id: number;
    title: string;
    version_type: string | null;
}

interface WorkInfo {
    id: number;
    title: string;
}

interface StationInfo {
    id: number;
    callsign: string;
    format_code: string | null;
}

// Station Preferences
export interface StationPreference {
    id: number;
    station_id: number;
    work_id: number;
    preferred_recording_id: number;
    priority: number;
    station: StationInfo | null;
    work: WorkInfo | null;
    preferred_recording: RecordingInfo | null;
}

export interface StationPreferenceCreate {
    station_id: number;
    work_id: number;
    preferred_recording_id: number;
    priority?: number;
}

// Format Preferences
export interface FormatPreference {
    id: number;
    format_code: string;
    work_id: number;
    preferred_recording_id: number;
    exclude_tags: string[];
    priority: number;
    work: WorkInfo | null;
    preferred_recording: RecordingInfo | null;
}

export interface FormatPreferenceCreate {
    format_code: string;
    work_id: number;
    preferred_recording_id: number;
    exclude_tags?: string[];
    priority?: number;
}

// Work Defaults
export interface WorkDefault {
    work_id: number;
    default_recording_id: number;
    work: WorkInfo | null;
    default_recording: RecordingInfo | null;
}

export interface WorkDefaultCreate {
    work_id: number;
    default_recording_id: number;
}

// =============================================================================
// Station Preferences Hooks
// =============================================================================

export function useStationPreferences(stationId?: number, workId?: number) {
    const params = new URLSearchParams();
    if (stationId) params.append('station_id', stationId.toString());
    if (workId) params.append('work_id', workId.toString());

    return useQuery({
        queryKey: ['preferences', 'stations', stationId, workId],
        queryFn: () => fetcher<StationPreference[]>(`/preferences/stations?${params.toString()}`),
    });
}

export function useCreateStationPreference() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: StationPreferenceCreate) =>
            fetcher<StationPreference>('/preferences/stations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'stations'] });
        },
    });
}

export function useDeleteStationPreference() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: number) =>
            fetcher<void>(`/preferences/stations/${id}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'stations'] });
        },
    });
}

// =============================================================================
// Format Preferences Hooks
// =============================================================================

export function useFormatPreferences(formatCode?: string, workId?: number) {
    const params = new URLSearchParams();
    if (formatCode) params.append('format_code', formatCode);
    if (workId) params.append('work_id', workId.toString());

    return useQuery({
        queryKey: ['preferences', 'formats', formatCode, workId],
        queryFn: () => fetcher<FormatPreference[]>(`/preferences/formats?${params.toString()}`),
    });
}

export function useCreateFormatPreference() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: FormatPreferenceCreate) =>
            fetcher<FormatPreference>('/preferences/formats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'formats'] });
            queryClient.invalidateQueries({ queryKey: ['preferences', 'formatCodes'] });
        },
    });
}

export function useDeleteFormatPreference() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: number) =>
            fetcher<void>(`/preferences/formats/${id}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'formats'] });
        },
    });
}

// =============================================================================
// Work Default Hooks
// =============================================================================

export function useWorkDefaults(workId?: number) {
    const params = new URLSearchParams();
    if (workId) params.append('work_id', workId.toString());

    return useQuery({
        queryKey: ['preferences', 'defaults', workId],
        queryFn: () => fetcher<WorkDefault[]>(`/preferences/defaults?${params.toString()}`),
    });
}

export function useCreateWorkDefault() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: WorkDefaultCreate) =>
            fetcher<WorkDefault>('/preferences/defaults', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'defaults'] });
        },
    });
}

export function useDeleteWorkDefault() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (workId: number) =>
            fetcher<void>(`/preferences/defaults/${workId}`, { method: 'DELETE' }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['preferences', 'defaults'] });
        },
    });
}

// =============================================================================
// Utility Hooks
// =============================================================================

export function useFormatCodes() {
    return useQuery({
        queryKey: ['preferences', 'formatCodes'],
        queryFn: () => fetcher<string[]>('/preferences/formats/codes'),
    });
}
