/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskProgress } from './TaskProgress';
import * as useTaskProgressModule from '../hooks/useTaskProgress';

const mockUseTaskProgress = vi.spyOn(useTaskProgressModule, 'useTaskProgress');

describe('TaskProgress', () => {
    it('renders nothing when taskId is null', () => {
        mockUseTaskProgress.mockReturnValue({
            status: null,
            isConnected: false,
            error: null,
        });

        const { container } = render(<TaskProgress taskId={null} />);
        expect(container.firstChild).toBeNull();
    });

    it('shows connecting state when status is null', () => {
        mockUseTaskProgress.mockReturnValue({
            status: null,
            isConnected: false,
            error: null,
        });

        render(<TaskProgress taskId="task-123" />);
        expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    });

    it('shows error state when error is set', () => {
        mockUseTaskProgress.mockReturnValue({
            status: null,
            isConnected: false,
            error: 'Connection lost',
        });

        render(<TaskProgress taskId="task-123" />);
        expect(screen.getByText('Connection lost')).toBeInTheDocument();
    });

    it('shows running state with progress and Cancel button', () => {
        mockUseTaskProgress.mockReturnValue({
            status: {
                task_id: 'task-123',
                task_type: 'scan',
                status: 'running',
                progress: 0.5,
                current: 50,
                total: 100,
                message: 'Scanning files...',
                started_at: new Date().toISOString(),
            },
            isConnected: true,
            error: null,
        });

        render(<TaskProgress taskId="task-123" />);
        expect(screen.getByText('Processing')).toBeInTheDocument();
        expect(screen.getByText('50%')).toBeInTheDocument();
        expect(screen.getByText('Scanning files...')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('shows completed state', () => {
        mockUseTaskProgress.mockReturnValue({
            status: {
                task_id: 'task-123',
                task_type: 'scan',
                status: 'completed',
                progress: 1,
                current: 100,
                total: 100,
                message: 'Done',
                started_at: new Date().toISOString(),
                completed_at: new Date().toISOString(),
            },
            isConnected: false,
            error: null,
        });

        render(<TaskProgress taskId="task-123" />);
        expect(screen.getByText('Completed')).toBeInTheDocument();
        expect(screen.getByText('100%')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument();
    });

    it('shows failed state with error message', () => {
        mockUseTaskProgress.mockReturnValue({
            status: {
                task_id: 'task-123',
                task_type: 'scan',
                status: 'failed',
                progress: 0.3,
                current: 30,
                total: 100,
                message: 'Scan failed',
                started_at: new Date().toISOString(),
                completed_at: new Date().toISOString(),
                error: 'Disk read error',
            },
            isConnected: false,
            error: null,
        });

        render(<TaskProgress taskId="task-123" />);
        expect(screen.getByText('Failed')).toBeInTheDocument();
        expect(screen.getByText('Disk read error')).toBeInTheDocument();
    });
});
