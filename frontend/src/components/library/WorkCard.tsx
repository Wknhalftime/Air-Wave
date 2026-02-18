import { Link } from 'react-router-dom';
import { Music, Clock } from 'lucide-react';
import type { WorkListItem } from '../../hooks/useLibrary';

interface WorkCardProps {
    work: WorkListItem;
}

export default function WorkCard({ work }: WorkCardProps) {
    const formatDuration = (seconds: number | null) => {
        if (!seconds) return null;
        const mins = Math.floor(seconds / 60);
        const hours = Math.floor(mins / 60);
        const remainingMins = mins % 60;
        
        if (hours > 0) {
            return `${hours}h ${remainingMins}m`;
        }
        return `${mins}m`;
    };

    return (
        <Link
            to={`/library/works/${work.id}`}
            className="group bg-white p-6 rounded-lg border border-gray-100 hover:border-indigo-200 hover:shadow-md transition-all duration-200"
        >
            <div className="flex items-start justify-between mb-3">
                <h3 className="text-lg font-semibold text-gray-900 group-hover:text-indigo-600 transition-colors line-clamp-2 flex-1">
                    {work.title}
                </h3>
                {work.year && (
                    <span className="ml-2 text-xs text-gray-500 font-medium bg-gray-50 px-2 py-1 rounded">
                        {work.year}
                    </span>
                )}
            </div>
            
            <p className="text-sm text-gray-600 mb-4 line-clamp-1">
                {work.artist_names}
            </p>
            
            <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                    <Music className="w-3.5 h-3.5" />
                    <span className="font-medium">{work.recording_count}</span>
                    <span className="text-gray-400">
                        {work.recording_count === 1 ? 'recording' : 'recordings'}
                    </span>
                </span>
                
                {work.duration_total && (
                    <span className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5" />
                        <span className="font-medium">{formatDuration(work.duration_total)}</span>
                    </span>
                )}
            </div>
        </Link>
    );
}

