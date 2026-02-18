/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ArtistCard } from './ArtistCard';

function renderArtistCard(artist: {
    id: number;
    name: string;
    work_count: number;
    recording_count: number;
    avatar_url: string | null;
}) {
    return render(
        <MemoryRouter>
            <ArtistCard artist={artist} />
        </MemoryRouter>
    );
}

describe('ArtistCard', () => {
    it('renders artist name and counts', () => {
        renderArtistCard({
            id: 1,
            name: 'The Beatles',
            work_count: 12,
            recording_count: 48,
            avatar_url: null,
        });
        expect(screen.getByText('The Beatles')).toBeInTheDocument();
        expect(screen.getByText('12')).toBeInTheDocument();
        expect(screen.getByText('48')).toBeInTheDocument();
    });

    it('links to artist detail page', () => {
        renderArtistCard({
            id: 42,
            name: 'Queen',
            work_count: 5,
            recording_count: 20,
            avatar_url: null,
        });
        const link = screen.getByRole('link', { name: /queen/i });
        expect(link).toHaveAttribute('href', '/library/artists/42');
    });

    it('shows first letter when no avatar', () => {
        renderArtistCard({
            id: 1,
            name: 'Nirvana',
            work_count: 0,
            recording_count: 0,
            avatar_url: null,
        });
        expect(screen.getByText('N')).toBeInTheDocument();
    });

    it('shows avatar image when avatar_url provided', () => {
        renderArtistCard({
            id: 1,
            name: 'Artist With Avatar',
            work_count: 1,
            recording_count: 1,
            avatar_url: 'https://example.com/avatar.jpg',
        });
        const img = screen.getByRole('img', { name: 'Artist With Avatar' });
        expect(img).toHaveAttribute('src', 'https://example.com/avatar.jpg');
    });
});
