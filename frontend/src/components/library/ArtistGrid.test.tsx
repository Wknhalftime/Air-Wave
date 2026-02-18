/**
 * @vitest-environment jsdom
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ArtistGrid } from './ArtistGrid';

function renderWithRouter(ui: React.ReactElement) {
    return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const mockArtists = [
    {
        id: 1,
        name: 'Artist One',
        work_count: 3,
        recording_count: 10,
        avatar_url: null,
    },
    {
        id: 2,
        name: 'Artist Two',
        work_count: 1,
        recording_count: 2,
        avatar_url: null,
    },
];

describe('ArtistGrid', () => {
    it('shows loading skeleton when isLoading is true', () => {
        renderWithRouter(<ArtistGrid artists={[]} isLoading={true} />);
        expect(screen.queryByText('No artists found')).not.toBeInTheDocument();
        expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    });

    it('shows empty state when artists is empty and not loading', () => {
        renderWithRouter(<ArtistGrid artists={[]} isLoading={false} />);
        expect(screen.getByText('No artists found')).toBeInTheDocument();
        expect(screen.getByText(/Try adjusting your search/)).toBeInTheDocument();
    });

    it('renders artist cards when artists provided', () => {
        renderWithRouter(<ArtistGrid artists={mockArtists} isLoading={false} />);
        expect(screen.getByText('Artist One')).toBeInTheDocument();
        expect(screen.getByText('Artist Two')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /artist one/i })).toHaveAttribute(
            'href',
            '/library/artists/1'
        );
        expect(screen.getByRole('link', { name: /artist two/i })).toHaveAttribute(
            'href',
            '/library/artists/2'
        );
    });

    it('handles undefined artists as empty', () => {
        renderWithRouter(<ArtistGrid artists={undefined as unknown as typeof mockArtists} isLoading={false} />);
        expect(screen.getByText('No artists found')).toBeInTheDocument();
    });
});
