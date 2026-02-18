/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WorkCard from './WorkCard';
import type { WorkListItem } from '../../hooks/useLibrary';

function renderWorkCard(work: WorkListItem) {
    return render(
        <MemoryRouter>
            <WorkCard work={work} />
        </MemoryRouter>
    );
}

describe('WorkCard', () => {
    it('renders work title and artist names', () => {
        const work: WorkListItem = {
            id: 1,
            title: 'Bohemian Rhapsody',
            artist_names: 'Queen',
            recording_count: 5,
            duration_total: 354,
            year: 1975,
        };

        renderWorkCard(work);

        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
        expect(screen.getByText('Queen')).toBeInTheDocument();
    });

    it('displays recording count correctly', () => {
        const work: WorkListItem = {
            id: 2,
            title: 'Test Work',
            artist_names: 'Test Artist',
            recording_count: 3,
            duration_total: null,
            year: null,
        };

        renderWorkCard(work);

        expect(screen.getByText('3')).toBeInTheDocument();
        expect(screen.getByText('recordings')).toBeInTheDocument();
    });

    it('displays singular "recording" for count of 1', () => {
        const work: WorkListItem = {
            id: 3,
            title: 'Single Recording Work',
            artist_names: 'Artist',
            recording_count: 1,
            duration_total: null,
            year: null,
        };

        renderWorkCard(work);

        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('recording')).toBeInTheDocument();
    });

    it('formats duration in minutes when less than 1 hour', () => {
        const work: WorkListItem = {
            id: 4,
            title: 'Short Work',
            artist_names: 'Artist',
            recording_count: 2,
            duration_total: 1800, // 30 minutes
            year: null,
        };

        renderWorkCard(work);

        expect(screen.getByText('30m')).toBeInTheDocument();
    });

    it('formats duration in hours and minutes when over 1 hour', () => {
        const work: WorkListItem = {
            id: 5,
            title: 'Long Work',
            artist_names: 'Artist',
            recording_count: 10,
            duration_total: 7200, // 2 hours
            year: null,
        };

        renderWorkCard(work);

        expect(screen.getByText('2h 0m')).toBeInTheDocument();
    });

    it('displays year badge when available', () => {
        const work: WorkListItem = {
            id: 6,
            title: 'Classic Work',
            artist_names: 'Classic Artist',
            recording_count: 1,
            duration_total: null,
            year: 1969,
        };

        renderWorkCard(work);

        expect(screen.getByText('1969')).toBeInTheDocument();
    });

    it('does not display year badge when year is null', () => {
        const work: WorkListItem = {
            id: 7,
            title: 'Modern Work',
            artist_names: 'Modern Artist',
            recording_count: 1,
            duration_total: null,
            year: null,
        };

        renderWorkCard(work);

        expect(screen.queryByText(/\d{4}/)).not.toBeInTheDocument();
    });

    it('links to correct work detail page', () => {
        const work: WorkListItem = {
            id: 42,
            title: 'Test Work',
            artist_names: 'Test Artist',
            recording_count: 1,
            duration_total: null,
            year: null,
        };

        renderWorkCard(work);

        const link = screen.getByRole('link');
        expect(link).toHaveAttribute('href', '/library/works/42');
    });

    it('handles multi-artist works', () => {
        const work: WorkListItem = {
            id: 8,
            title: 'Under Pressure',
            artist_names: 'Queen, David Bowie',
            recording_count: 2,
            duration_total: 248,
            year: 1981,
        };

        renderWorkCard(work);

        expect(screen.getByText('Under Pressure')).toBeInTheDocument();
        expect(screen.getByText('Queen, David Bowie')).toBeInTheDocument();
    });
});

