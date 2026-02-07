/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import StationDetail from './StationDetail';

const mockHealth = {
    station: { id: 1, callsign: 'KEXP' },
    recent_batches: [],
    unmatched_tracks: [],
};

function renderStationDetail() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(['stations', '1', 'health'], mockHealth);
    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={['/stations/1']}>
                <Routes>
                    <Route path="/stations/:id" element={<StationDetail />} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>
    );
}

describe('StationDetail M3U export', () => {
    beforeEach(() => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                blob: () => Promise.resolve(new Blob(['#EXTM3U'])),
                headers: {
                    get: (name: string) =>
                        name === 'Content-Disposition' ? 'attachment; filename="airwave_playlist.m3u"' :
                        name === 'X-Airwave-M3U-Included' ? '5' :
                        name === 'X-Airwave-M3U-Skipped' ? '0' : null,
                },
            })
        );
    });

    it('calls export API with station_id and matched_only when Export M3U is clicked', async () => {
        renderStationDetail();
        const button = screen.getByRole('button', { name: /export m3u/i });
        fireEvent.click(button);
        await waitFor(() => {
            expect(fetch).toHaveBeenCalled();
        });
        const exportCalls = (fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
            (call) => typeof call[0] === 'string' && (call[0] as string).includes('/export/m3u')
        );
        expect(exportCalls.length).toBeGreaterThanOrEqual(1);
        const url = exportCalls[0][0] as string;
        expect(url).toContain('/export/m3u');
        expect(url).toContain('station_id=1');
        expect(url).toContain('matched_only=true');
    });
});
