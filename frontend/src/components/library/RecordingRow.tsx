import { Clock, CheckCircle, XCircle, FileAudio } from 'lucide-react';
import type { RecordingListItem } from '../../hooks/useLibrary';

interface RecordingRowProps {
    recording: RecordingListItem;
}

export default function RecordingRow({ recording }: RecordingRowProps) {
    const formatDuration = (seconds: number | null) => {
        if (!seconds) return '-';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <tr className="hover:bg-gray-50 transition-colors">
            <td className="px-6 py-4">
                <div className="text-sm font-medium text-gray-900">
                    {recording.title}
                </div>
            </td>
            <td className="px-6 py-4">
                <div className="text-sm text-gray-600">
                    {recording.artist_display}
                </div>
            </td>
            <td className="px-6 py-4">
                <div className="flex items-center gap-1.5 text-sm text-gray-600">
                    <Clock className="w-3.5 h-3.5 text-gray-400" />
                    <span className="font-mono">{formatDuration(recording.duration)}</span>
                </div>
            </td>
            <td className="px-6 py-4">
                <div className="text-sm text-gray-600">
                    {recording.version_type || (
                        <span className="text-gray-400">-</span>
                    )}
                </div>
            </td>
            <td className="px-6 py-4">
                {recording.is_verified ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-50 text-green-700 rounded-md text-xs font-medium">
                        <CheckCircle className="w-3.5 h-3.5" />
                        Matched
                    </span>
                ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-yellow-50 text-yellow-700 rounded-md text-xs font-medium">
                        <XCircle className="w-3.5 h-3.5" />
                        Unmatched
                    </span>
                )}
            </td>
            <td className="px-6 py-4">
                {recording.has_file ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md text-xs font-medium">
                        <FileAudio className="w-3.5 h-3.5" />
                        Library
                    </span>
                ) : (
                    <span className="text-gray-500 text-xs font-medium">
                        Metadata
                    </span>
                )}
            </td>
        </tr>
    );
}

