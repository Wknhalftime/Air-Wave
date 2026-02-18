/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Library from './Library';
import * as useArtistsModule from '../hooks/useArtists';

const mockUseArtists = vi.spyOn(useArtistsModule, 'useArtists');

function renderLibrary() {
    return render(
        <MemoryRouter>
            <Library />
        </MemoryRouter>
    );
}

describe('Library', () => {
    it('renders Library heading and search placeholder', () => {
        mockUseArtists.mockReturnValue({
            data: [],
            isLoading: false,
            error: null,
            isPlaceholderData: false,
        } as ReturnType<typeof useArtistsModule.useArtists>);

        renderLibrary();
        expect(screen.getByText('Library')).toBeInTheDocument();
        expect(screen.getByText(/browse by artist/i)).toBeInTheDocument();
        expect(screen.getByPlaceholderText(/find artist/i)).toBeInTheDocument();
    });

    it('shows onboarding alert when no artists and not loading', () => {
        mockUseArtists.mockReturnValue({
            data: [],
            isLoading: false,
            error: null,
            isPlaceholderData: false,
        } as ReturnType<typeof useArtistsModule.useArtists>);

        renderLibrary();
        expect(screen.getByText(/your library is empty/i)).toBeInTheDocument();
    });

    it('shows artist grid when artists loaded', () => {
        mockUseArtists.mockReturnValue({
            data: [
                {
                    id: 1,
                    name: 'Test Artist',
                    work_count: 2,
                    recording_count: 5,
                    avatar_url: null,
                },
            ],
            isLoading: false,
            error: null,
            isPlaceholderData: false,
        } as ReturnType<typeof useArtistsModule.useArtists>);

        renderLibrary();
        expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('shows error message when error is set', () => {
        mockUseArtists.mockReturnValue({
            data: undefined,
            isLoading: false,
            error: new Error('Network error'),
            isPlaceholderData: false,
        } as ReturnType<typeof useArtistsModule.useArtists>);

        renderLibrary();
        expect(screen.getByText(/error loading artists/i)).toBeInTheDocument();
    });

    it('calls useArtists with search when user types', () => {
        mockUseArtists.mockReturnValue({
            data: [],
            isLoading: false,
            error: null,
            isPlaceholderData: false,
        } as ReturnType<typeof useArtistsModule.useArtists>);

        renderLibrary();
        const input = screen.getByPlaceholderText(/find artist/i);
        fireEvent.change(input, { target: { value: 'beatles' } });
        expect(mockUseArtists).toHaveBeenCalledWith(
            expect.objectContaining({
                search: 'beatles',
                page: 1,
                limit: 24,
            })
        );
    });
});
