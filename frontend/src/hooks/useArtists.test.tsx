/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useArtists } from './useArtists';

const createWrapper = () => {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
        },
    });
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        );
    };
};

describe('useArtists', () => {
    beforeEach(() => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                json: () =>
                    Promise.resolve([
                        {
                            id: 1,
                            name: 'Mock Artist',
                            work_count: 2,
                            recording_count: 8,
                            avatar_url: null,
                        },
                    ]),
            })
        );
    });

    it('fetches artists and returns data', async () => {
        const { result } = renderHook(
            () => useArtists({ page: 1, limit: 24, search: '' }),
            { wrapper: createWrapper() }
        );

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toHaveLength(1);
        expect(result.current.data?.[0].name).toBe('Mock Artist');
        expect(result.current.data?.[0].work_count).toBe(2);
        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('/library/artists'),
            undefined
        );
    });

    it('includes search and pagination in request', async () => {
        const { result } = renderHook(
            () => useArtists({ page: 2, limit: 10, search: 'beatles' }),
            { wrapper: createWrapper() }
        );

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        expect(fetch).toHaveBeenCalledWith(
            expect.stringMatching(/search=beatles.*skip=10.*limit=10/),
            undefined
        );
    });
});
