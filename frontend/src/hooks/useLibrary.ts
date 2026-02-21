import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';

// ============================================================================
// TypeScript Interfaces (matching backend Pydantic schemas)
// ============================================================================

/**
 * Detailed artist information for artist detail page header.
 * Matches backend schema: ArtistDetail
 */
export interface ArtistDetail {
    id: number;
    name: string;
    musicbrainz_id: string | null;
    work_count: number | null;
    recording_count: number | null;
}

/**
 * Work summary for display in artist detail page grid.
 * Matches backend schema: WorkListItem
 */
export interface WorkListItem {
    id: number;
    title: string;
    artist_names: string; // Comma-separated artist names (e.g., "Queen, David Bowie")
    recording_count: number;
    duration_total: number | null; // Total duration of all recordings in seconds
    year: number | null; // Year of first recording (optional)
}

/**
 * Detailed work information for work detail page header.
 * Matches backend schema: WorkDetail
 */
export interface WorkDetail {
    id: number;
    title: string;
    artist_id: number | null;
    artist_name: string | null; // Primary artist name
    artist_names: string; // All artist names (e.g., "Queen, David Bowie")
    is_instrumental: boolean;
    recording_count: number | null;
}

/**
 * Recording information for display in work detail page table.
 * Matches backend schema: RecordingListItem
 */
export interface RecordingListItem {
    id: number;
    title: string;
    artist_display: string; // Artist name(s) for this recording
    duration: number | null; // Duration in seconds
    version_type: string | null; // Live, Remix, etc.
    work_title: string; // Work title for the "Work" column
    is_verified: boolean; // Matched/Unmatched status
    has_file: boolean; // Whether recording has associated library file
    filename: string | null; // Filename (not full path) from first library file
}

// ============================================================================
// React Query Hooks
// ============================================================================

/**
 * Hook to fetch a single artist with aggregated stats.
 * Endpoint: GET /api/v1/library/artists/{artist_id}
 */
export function useArtist(artistId: number | null) {
    return useQuery({
        queryKey: ['library', 'artist', artistId],
        queryFn: () => fetcher<ArtistDetail>(`/library/artists/${artistId}`),
        enabled: artistId !== null,
    });
}

/**
 * Hook to fetch works for an artist (including collaborations).
 * Endpoint: GET /api/v1/library/artists/{artist_id}/works
 */
export interface UseArtistWorksParams {
    artistId: number | null;
    skip?: number;
    limit?: number;
}

export function useArtistWorks({ artistId, skip = 0, limit = 24 }: UseArtistWorksParams) {
    return useQuery({
        queryKey: ['library', 'artist', artistId, 'works', skip, limit],
        queryFn: () =>
            fetcher<WorkListItem[]>(
                `/library/artists/${artistId}/works?skip=${skip}&limit=${limit}`
            ),
        enabled: artistId !== null,
        placeholderData: (previousData) => previousData,
    });
}

/**
 * Hook to fetch a single work with artist details.
 * Endpoint: GET /api/v1/library/works/{work_id}
 */
export function useWork(workId: number | null) {
    return useQuery({
        queryKey: ['library', 'work', workId],
        queryFn: () => fetcher<WorkDetail>(`/library/works/${workId}`),
        enabled: workId !== null,
    });
}

/**
 * Hook to fetch recordings for a work with optional filters.
 * Endpoint: GET /api/v1/library/works/{work_id}/recordings
 */
export interface UseWorkRecordingsParams {
    workId: number | null;
    skip?: number;
    limit?: number;
    status?: 'all' | 'matched' | 'unmatched'; // Filter by verification status
    source?: 'all' | 'library' | 'metadata'; // Filter by file presence
}

export function useWorkRecordings({
    workId,
    skip = 0,
    limit = 100,
    status = 'all',
    source = 'all',
}: UseWorkRecordingsParams) {
    const params = new URLSearchParams({
        skip: skip.toString(),
        limit: limit.toString(),
    });

    if (status !== 'all') {
        params.append('status', status);
    }

    if (source !== 'all') {
        params.append('source', source);
    }

    return useQuery({
        queryKey: ['library', 'work', workId, 'recordings', skip, limit, status, source],
        queryFn: () =>
            fetcher<RecordingListItem[]>(
                `/library/works/${workId}/recordings?${params.toString()}`
            ),
        enabled: workId !== null,
        placeholderData: (previousData) => previousData,
    });
}

