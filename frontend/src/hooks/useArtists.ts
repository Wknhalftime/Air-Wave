import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';

export interface ArtistStats {
    id: number;
    name: string;
    work_count: number;
    recording_count: number;
    avatar_url: string | null;
}

interface UseArtistsParams {
    page: number;
    limit: number;
    search: string;
}

export function useArtists({ page, limit, search }: UseArtistsParams) {
    return useQuery({
        queryKey: ['library', 'artists', search, page],
        queryFn: () =>
            fetcher<ArtistStats[]>(
                `/library/artists?search=${encodeURIComponent(search)}&skip=${(page - 1) * limit}&limit=${limit}`
            ),
        placeholderData: (previousData) => previousData,
    });
}
