import { Link } from 'react-router-dom';
import { Music, Clock } from 'lucide-react';
import type { WorkListItem } from '../../hooks/useLibrary';
import { toTitleCase, formatArtistForDisplay } from '../../utils/format';

interface WorkRowProps {
    work: WorkListItem;
    /** When true, hide duration and year columns (e.g. on artist page) */
    compact?: boolean;
}

export default function WorkRow({ work, compact = false }: WorkRowProps) {
    const formatDuration = (seconds: number | null) => {
        if (!seconds) return '-';
        const mins = Math.floor(seconds / 60);
        const hours = Math.floor(mins / 60);
        const remainingMins = mins % 60;

        if (hours > 0) {
            return `${hours}h ${remainingMins}m`;
        }
        return `${mins}m`;
    };

    return (
        <tr className="hover:bg-gray-50 transition-colors group">
            <td className="px-6 py-4">
                <Link
                    to={`/library/works/${work.id}`}
                    className="text-sm font-medium text-gray-900 group-hover:text-indigo-600 transition-colors"
                >
                    {toTitleCase(work.title)}
                </Link>
            </td>
            <td className="px-6 py-4">
                <div className="text-sm text-gray-600">{formatArtistForDisplay(work.artist_names)}</div>
            </td>
            <td className="px-6 py-4">
                <div className="flex items-center gap-1.5 text-sm text-gray-600">
                    <Music className="w-3.5 h-3.5 text-gray-400" />
                    <span className="font-medium">{work.recording_count}</span>
                    <span className="text-gray-400">
                        {work.recording_count === 1 ? 'recording' : 'recordings'}
                    </span>
                </div>
            </td>
            {!compact && (
                <>
                    <td className="px-6 py-4">
                        <div className="flex items-center gap-1.5 text-sm text-gray-600">
                            <Clock className="w-3.5 h-3.5 text-gray-400" />
                            <span className="font-mono">{formatDuration(work.duration_total)}</span>
                        </div>
                    </td>
                    <td className="px-6 py-4">
                        {work.year ? (
                            <span className="text-xs text-gray-500 font-medium bg-gray-50 px-2 py-1 rounded">
                                {work.year}
                            </span>
                        ) : (
                            <span className="text-gray-400">-</span>
                        )}
                    </td>
                </>
            )}
        </tr>
    );
}
