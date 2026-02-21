import { ArtistCard } from './ArtistCard';
import { isVariousArtist } from '../../utils/format';

interface ArtistStats {
    id: number;
    name: string;
    work_count: number;
    recording_count: number;
    avatar_url: string | null;
}

interface ArtistGridProps {
    artists: ArtistStats[];
    isLoading?: boolean;
}

export function ArtistGrid({ artists, isLoading }: ArtistGridProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
                {[...Array(12)].map((_, i) => (
                    <div
                        key={i}
                        className="animate-pulse bg-white p-6 rounded-xl border border-gray-100 flex flex-col items-center"
                    >
                        <div className="w-32 h-32 rounded-full bg-gray-200 mb-4" />
                        <div className="h-4 bg-gray-200 w-3/4 mb-2 rounded" />
                        <div className="h-3 bg-gray-200 w-1/2 rounded" />
                    </div>
                ))}
            </div>
        );
    }

    if (!artists || artists.length === 0) {
        return (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200 border-dashed">
                <h3 className="text-lg font-medium text-gray-900">No artists found</h3>
                <p className="text-gray-500 mt-1">Try adjusting your search terms.</p>
            </div>
        );
    }

    const visibleArtists = artists.filter((a) => !isVariousArtist(a.name));
    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
            {visibleArtists.map((artist) => (
                <ArtistCard key={artist.id} artist={artist} />
            ))}
        </div>
    );
}
