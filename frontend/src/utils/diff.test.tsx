/**
 * @vitest-environment jsdom
 */
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
        // Component does not render deletions (removed parts return null). Verify diff is detected.
        it('highlights single character difference', () => {
            // Beatles -> Beatls. 'e' is removed (not shown); we see "Beatl" + "s"
            render(renderDiff('Beatles', 'Beatls', 'Test'));
            expect(screen.getByText('Beatl')).toBeTruthy();
            expect(screen.getByText('s')).toBeTruthy();
            expect(screen.getByText(/Difference detected for Test/)).toBeTruthy();
        });

        // Case 4: Multiple Differences
        // Component does not render deletions. "The " is removed; we see "Beatles"
        it('highlights multiple differences', () => {
            render(renderDiff('The Beatles', 'Beatles', 'Test'));
            expect(screen.getByText(/Library Match: Beatles/)).toBeTruthy();
        });

        // Case 8: Special Characters
        // AC-DC -> AC/DC: '-' removed (not shown), '/' added (amber highlight)
        it('highlights special character differences', () => {
            render(renderDiff('AC-DC', 'AC/DC', 'Test'));
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
