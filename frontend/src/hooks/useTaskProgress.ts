import { useState, useEffect, useRef } from 'react';

export interface TaskStatus {
    task_id: string;
    task_type: string;
    status: 'running' | 'completed' | 'failed';
    progress: number;
    current: number;
    total: number;
    message: string;
    started_at: string;
    completed_at?: string;
    error?: string;
}

export function useTaskProgress(taskId: string | null) {
    const [status, setStatus] = useState<TaskStatus | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (!taskId) {
            setStatus(null);
            setIsConnected(false);
            return;
        }

        // Small delay to ensure backend task is created first
        const connectionTimer = setTimeout(() => {
            const url = `/api/v1/admin/tasks/${taskId}/stream`;
            console.log('[TaskProgress] Connecting to SSE:', url);

            // Create EventSource connection
            const eventSource = new EventSource(url);
            eventSourceRef.current = eventSource;

            eventSource.onopen = () => {
                console.log('[TaskProgress] SSE connection opened');
                setIsConnected(true);
                setError(null);
            };

            eventSource.onmessage = (event) => {
                console.log('[TaskProgress] SSE message received:', event.data);
                try {
                    const data = JSON.parse(event.data);

                    if (data.error) {
                        console.error('[TaskProgress] Error from server:', data.error);
                        setError(data.error);
                        setIsConnected(false);
                        eventSource.close();
                        return;
                    }

                    if (data.connected) {
                        console.log('[TaskProgress] Initial connection confirmed');
                        // Initial connection message
                        return;
                    }

                    console.log('[TaskProgress] Task status update:', data);
                    setStatus(data as TaskStatus);

                    // Close connection when task completes
                    if (data.status === 'completed' || data.status === 'failed') {
                        console.log('[TaskProgress] Task finished, closing connection');
                        setIsConnected(false);
                        eventSource.close();
                    }
                } catch (err) {
                    console.error('Failed to parse task status:', err, 'Raw data:', event.data);
                }
            };

            eventSource.onerror = (e) => {
                console.error('[TaskProgress] EventSource error:', e);
                console.error('[TaskProgress] EventSource readyState:', eventSource.readyState);
                setError('Connection lost');
                setIsConnected(false);
                eventSource.close();
            };
        }, 200); // 200ms delay to let API endpoint return and pre-create task

        // Cleanup on unmount or taskId change
        return () => {
            console.log('[TaskProgress] Cleaning up SSE connection');
            clearTimeout(connectionTimer);
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
            }
        };
    }, [taskId]);

    return { status, isConnected, error };
}
