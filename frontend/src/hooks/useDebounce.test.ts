/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebounce } from './useDebounce';

describe('useDebounce', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('returns initial value immediately', () => {
        const { result } = renderHook(() => useDebounce('hello', 500));
        expect(result.current).toBe('hello');
    });

    it('updates to new value after delay', () => {
        const { result, rerender } = renderHook(
            ({ value, delay }) => useDebounce(value, delay),
            { initialProps: { value: 'first', delay: 500 } }
        );
        expect(result.current).toBe('first');

        rerender({ value: 'second', delay: 500 });
        expect(result.current).toBe('first');

        act(() => {
            vi.advanceTimersByTime(500);
        });
        expect(result.current).toBe('second');
    });

    it('uses default delay of 500ms when delay not provided', () => {
        const { result, rerender } = renderHook(
            ({ value }) => useDebounce(value),
            { initialProps: { value: 'a' } }
        );
        rerender({ value: 'b' });
        act(() => {
            vi.advanceTimersByTime(499);
        });
        expect(result.current).toBe('a');
        act(() => {
            vi.advanceTimersByTime(1);
        });
        expect(result.current).toBe('b');
    });

    it('cancels previous timer when value changes before delay', () => {
        const { result, rerender } = renderHook(
            ({ value }) => useDebounce(value, 500),
            { initialProps: { value: 'one' } }
        );
        rerender({ value: 'two' });
        act(() => {
            vi.advanceTimersByTime(200);
        });
        rerender({ value: 'three' });
        act(() => {
            vi.advanceTimersByTime(500);
        });
        expect(result.current).toBe('three');
    });

    it('handles number values', () => {
        const { result, rerender } = renderHook(
            ({ value }) => useDebounce(value, 100),
            { initialProps: { value: 42 } }
        );
        expect(result.current).toBe(42);
        rerender({ value: 99 });
        act(() => {
            vi.advanceTimersByTime(100);
        });
        expect(result.current).toBe(99);
    });
});
