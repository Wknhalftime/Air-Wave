import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderDiff, normalizeForMatch } from './diff';

describe('Diff Utility', () => {
    describe('normalizeForMatch', () => {
        it('should lowercase strings', () => {
            expect(normalizeForMatch('Beatles')).toBe('beatles');
        });

        it('should collapse whitespace', () => {
            expect(normalizeForMatch('The   Beatles')).toBe('the beatles');
        });

        it('should trim whitespace', () => {
            expect(normalizeForMatch('  Beatles  ')).toBe('beatles');
        });

        it('should handle empty/null', () => {
            expect(normalizeForMatch('')).toBe('');
            // @ts-ignore
            expect(normalizeForMatch(null)).toBe('');
        });
    });

    describe('renderDiff', () => {
        // Case 1: Identical Strings
        it('renders green check for identical strings', () => {
            const { container } = render(renderDiff('Beatles', 'Beatles', 'Test'));
            expect(container.querySelector('.text-green-500')).toBeTruthy(); // Check icon
            expect(screen.getByText('Beatles')).toBeTruthy();
        });

        // Case 5 & 6: Case/Whitespace Insensitive (Ignored)
        it('renders green check for case/whitespace variants', () => {
            const { container } = render(renderDiff('The  Beatles', 'the beatles', 'Test'));
            expect(container.querySelector('.text-green-500')).toBeTruthy();
            expect(screen.queryByText('inserted:')).toBeNull();
        });

        // Case 3: Single Character Difference
        it('highlights single character difference', () => {
            // Beatles -> Beatls. 'e' is removed.
            render(renderDiff('Beatles', 'Beatls', 'Test'));
            // Matches specific span with text 'e'
            const deleted = screen.getByText('e');
            expect(deleted.className).toContain('bg-red-50');
        });

        // Case 4: Multiple Differences
        it('highlights multiple differences', () => {
            render(renderDiff('The Beatles', 'Beatles', 'Test'));
            // Use getAllByText to handle potential collisions with sr-only text
            // Pick the last one which is usually the visual one, or check classes on all
            const matches = screen.getAllByText(/The/);
            const visualMatch = matches.find(el => el.className.includes('bg-red-50'));
            expect(visualMatch).toBeTruthy();
        });

        // Case 8: Special Characters
        it('highlights special character differences', () => {
            render(renderDiff('AC-DC', 'AC/DC', 'Test'));
            const matches = screen.getAllByText('-');
            const visualMatch = matches.find(el => el.className.includes('bg-red-50'));
            expect(visualMatch).toBeTruthy();

            const matchesSlash = screen.getAllByText('/');
            const visualInserted = matchesSlash.find(el => el.className.includes('bg-amber-100'));
            expect(visualInserted).toBeTruthy();
        });

        // Case 7: Empty Strings
        it('handles empty strings gracefully', () => {
            render(renderDiff('', '', 'Test'));
            const empties = screen.getAllByText('(Empty)');
            expect(empties.length).toBeGreaterThan(0);
        });

        // Fail Gracefully
        it('fails gracefully on error', () => {
            // @ts-ignore force error
            render(renderDiff(null, null, 'Test'));
            const empties = screen.getAllByText('(Empty)');
            expect(empties.length).toBeGreaterThan(0);
        });
    });
});
