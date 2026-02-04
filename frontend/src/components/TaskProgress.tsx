import { useTaskProgress } from '../hooks/useTaskProgress';
import { Loader, CheckCircle, XCircle, Activity } from 'lucide-react';

interface TaskProgressProps {
    taskId: string | null;
    onComplete?: () => void;
}

export function TaskProgress({ taskId, onComplete }: TaskProgressProps) {
    const { status, isConnected, error } = useTaskProgress(taskId);

    // Call onComplete callback when task finishes
    if (status?.status === 'completed' && onComplete) {
        setTimeout(onComplete, 1000); // Delay to show completion state
    }

    if (!taskId) {
        return null;
    }

    if (error && onComplete) {
        // Automatically clear stale tasks/errors after 3 seconds
        setTimeout(onComplete, 3000);
    }

    if (error) {
        return (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg animate-shake">
                <div className="flex items-center gap-2">
                    <XCircle className="w-4 h-4 text-red-600" />
                    <span className="text-sm text-red-700 font-medium">{error}</span>
                </div>
                <p className="text-xs text-red-400 mt-1 ml-6">Resetting state in 3s...</p>
            </div>
        );
    }

    if (!status) {
        return (
            <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2">
                    <Loader className="w-4 h-4 text-gray-500 animate-spin" />
                    <span className="text-sm text-gray-600">Connecting...</span>
                </div>
            </div>
        );
    }

    const progressPercentage = Math.round(status.progress * 100);
    const isComplete = status.status === 'completed';
    const isFailed = status.status === 'failed';

    return (
        <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    {isComplete ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : isFailed ? (
                        <XCircle className="w-5 h-5 text-red-600" />
                    ) : (
                        <Activity className="w-5 h-5 text-indigo-600 animate-pulse" />
                    )}
                    <span className="text-sm font-medium text-gray-900">
                        {isComplete ? 'Completed' : isFailed ? 'Failed' : 'Processing'}
                    </span>
                </div>
                <span className="text-sm font-semibold text-gray-700">
                    {progressPercentage}%
                </span>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2 overflow-hidden">
                <div
                    className={`h-2 rounded-full transition-all duration-300 ${isComplete
                        ? 'bg-green-600'
                        : isFailed
                            ? 'bg-red-600'
                            : 'bg-indigo-600'
                        }`}
                    style={{ width: `${progressPercentage}%` }}
                />
            </div>

            {/* Status Message */}
            <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600 truncate flex-1">{status.message}</span>
                <span className="text-gray-500 ml-2 whitespace-nowrap">
                    {status.current} / {status.total}
                </span>
            </div>

            {/* Error Message */}
            {isFailed && status.error && (
                <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-700">
                    {status.error}
                </div>
            )}

            {/* Connection Status */}
            {isConnected && !isComplete && !isFailed && (
                <div className="mt-2 flex items-center gap-1 text-xs text-gray-400">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span>Live updates</span>
                </div>
            )}
        </div>
    );
}
