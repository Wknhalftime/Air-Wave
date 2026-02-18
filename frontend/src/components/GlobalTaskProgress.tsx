import { useState, useEffect } from 'react';
import { useTaskProgress } from '../hooks/useTaskProgress';
import { fetcher } from '../lib/api';
import { Upload, FolderSync, Activity, X, CheckCircle, XCircle, Loader, StopCircle } from 'lucide-react';

interface ActiveTask {
    key: string;
    taskId: string;
    type: 'import' | 'sync' | 'scan' | 'discovery';
}

const TASK_KEYS = [
    { key: 'airwave_import_task_id', type: 'import' as const },
    { key: 'airwave_sync_task_id', type: 'sync' as const },
    { key: 'airwave_scan_task_id', type: 'scan' as const },
    { key: 'airwave_discovery_task_id', type: 'discovery' as const },
];

const TASK_CONFIG: Record<'import' | 'sync' | 'scan' | 'discovery', { icon: typeof Activity; label: string; color: string }> = {
    import: {
        icon: Upload,
        label: 'Import',
        color: 'blue',
    },
    sync: {
        icon: FolderSync,
        label: 'Sync',
        color: 'green',
    },
    scan: {
        icon: Activity,
        label: 'Scan',
        color: 'purple',
    },
    discovery: {
        icon: Activity,
        label: 'Discovery',
        color: 'indigo',
    },
};

function TaskProgressBar({ taskKey, taskId, type, onDismiss }: {
    taskKey: string;
    taskId: string;
    type: 'import' | 'sync' | 'scan' | 'discovery';
    onDismiss: () => void;
}) {
    const { status, error } = useTaskProgress(taskId);
    const [isCancelling, setIsCancelling] = useState(false);
    const config = TASK_CONFIG[type];
    const Icon = config.icon;

    // Clear "Cancelling..." when backend reports cancelled
    useEffect(() => {
        if (status?.status === 'cancelled') {
            setIsCancelling(false);
        }
    }, [status?.status]);

    // Auto-dismiss after 5 seconds on completion or cancellation
    useEffect(() => {
        if (status?.status === 'completed' || status?.status === 'failed' || status?.status === 'cancelled') {
            const timer = setTimeout(() => {
                localStorage.removeItem(taskKey);
                onDismiss();
            }, 5000);
            return () => clearTimeout(timer);
        }
    }, [status?.status, taskKey, onDismiss]);

    const handleCancel = async () => {
        if (!taskId || status?.status !== 'running') return;
        setIsCancelling(true);
        try {
            await fetcher(`/admin/tasks/${taskId}/cancel`, { method: 'POST' });
        } catch (err) {
            console.error('Failed to cancel task:', err);
            setIsCancelling(false);
        }
    };

    if (error) {
        return (
            <div className="p-2 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                        <span className="text-xs text-red-700 truncate">{error}</span>
                    </div>
                    <button
                        onClick={onDismiss}
                        className="ml-2 text-red-400 hover:text-red-600 flex-shrink-0"
                    >
                        <X className="w-3 h-3" />
                    </button>
                </div>
            </div>
        );
    }

    if (!status) {
        return (
            <div className="p-2 bg-gray-50 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-2">
                    <Loader className="w-4 h-4 text-gray-500 animate-spin flex-shrink-0" />
                    <span className="text-xs text-gray-600">Connecting...</span>
                </div>
            </div>
        );
    }

    const progressPercentage = Math.round(status.progress * 100);
    const isComplete = status.status === 'completed';
    const isFailed = status.status === 'failed';
    const isCancelled = status.status === 'cancelled';
    const isRunning = status.status === 'running';

    const colorClasses: Record<string, { bg: string; text: string; icon: string }> = {
        blue: {
            bg: 'bg-blue-600',
            text: 'text-blue-700',
            icon: 'text-blue-600',
        },
        green: {
            bg: 'bg-green-600',
            text: 'text-green-700',
            icon: 'text-green-600',
        },
        purple: {
            bg: 'bg-purple-600',
            text: 'text-purple-700',
            icon: 'text-purple-600',
        },
        indigo: {
            bg: 'bg-indigo-600',
            text: 'text-indigo-700',
            icon: 'text-indigo-600',
        },
    };

    const colors = colorClasses[config.color] ?? colorClasses.blue;

    return (
        <div className="p-2 bg-white border border-gray-200 rounded-lg shadow-sm">
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    {isComplete ? (
                        <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
                    ) : isFailed ? (
                        <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                    ) : isCancelled ? (
                        <StopCircle className="w-4 h-4 text-orange-600 flex-shrink-0" />
                    ) : (
                        <Icon className={`w-4 h-4 ${colors.icon} flex-shrink-0`} />
                    )}
                    <span className={`text-xs font-medium ${isCancelled ? 'text-orange-700' : colors.text} truncate`}>
                        {config.label}
                    </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-semibold text-gray-700">
                        {progressPercentage}%
                    </span>
                    {isRunning && !isCancelling && (
                        <button
                            onClick={handleCancel}
                            className="text-xs text-red-600 hover:text-red-800 font-medium"
                            title="Cancel task"
                        >
                            Cancel
                        </button>
                    )}
                    {isCancelling && (
                        <span className="text-xs text-orange-600 font-medium">Cancelling...</span>
                    )}
                    <button
                        onClick={onDismiss}
                        className="text-gray-400 hover:text-gray-600"
                        title="Dismiss"
                    >
                        <X className="w-3 h-3" />
                    </button>
                </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-1.5 mb-1 overflow-hidden">
                <div
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                        isComplete ? 'bg-green-600' : isFailed ? 'bg-red-600' : isCancelled ? 'bg-orange-600' : colors.bg
                    }`}
                    style={{ width: `${progressPercentage}%` }}
                />
            </div>

            {/* Status Message */}
            <div className="text-xs text-gray-600 truncate">
                {status.message}
            </div>
        </div>
    );
}

export function GlobalTaskProgress() {
    const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);

    // Poll localStorage for active tasks
    useEffect(() => {
        const checkTasks = () => {
            const tasks: ActiveTask[] = [];
            TASK_KEYS.forEach(({ key, type }) => {
                const taskId = localStorage.getItem(key);
                if (taskId) {
                    tasks.push({ key, taskId, type });
                }
            });
            setActiveTasks(tasks);
        };

        // Initial check
        checkTasks();

        // Poll every 500ms to detect new tasks
        const interval = setInterval(checkTasks, 500);
        return () => clearInterval(interval);
    }, []);

    const handleDismiss = (key: string) => {
        localStorage.removeItem(key);
        setActiveTasks(prev => prev.filter(task => task.key !== key));
    };

    if (activeTasks.length === 0) {
        return null;
    }

    return (
        <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {activeTasks.map(task => (
                <TaskProgressBar
                    key={task.key}
                    taskKey={task.key}
                    taskId={task.taskId}
                    type={task.type}
                    onDismiss={() => handleDismiss(task.key)}
                />
            ))}
        </div>
    );
}

