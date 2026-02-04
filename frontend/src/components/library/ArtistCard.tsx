import { Music, Disc } from 'lucide-react';

interface ArtistStats {
    id: number;
    name: string;
    work_count: number;
    recording_count: number;
    avatar_url: string | null;
}

interface ArtistCardProps {
    artist: ArtistStats;
}

export function ArtistCard({ artist }: ArtistCardProps) {
    return (
        <div className="group relative flex flex-col items-center p-6 bg-white rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer border border-gray-100">
            <div className="w-32 h-32 rounded-full bg-gray-100 mb-4 overflow-hidden flex items-center justify-center text-3xl font-bold text-gray-400 group-hover:bg-indigo-50 group-hover:text-indigo-500 transition-colors">
                {artist.avatar_url ? (
                    <img
                        src={artist.avatar_url}
                        alt={artist.name}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    artist.name.charAt(0).toUpperCase()
                )}
            </div>
            <h3
                className="text-lg font-semibold text-gray-900 text-center truncate w-full px-2"
                title={artist.name}
            >
                {artist.name}
            </h3>
            <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                    <Music className="w-3 h-3" /> {artist.work_count}
                </span>
                <span className="flex items-center gap-1">
                    <Disc className="w-3 h-3" /> {artist.recording_count}
                </span>
            </div>
        </div>
    );
}
