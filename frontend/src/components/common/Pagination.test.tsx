/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Pagination from './Pagination';

describe('Pagination', () => {
    it('renders current page number', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={3}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        expect(screen.getAllByText('Page 3')).toHaveLength(2); // One in info, one in middle
    });

    it('disables Previous button on first page', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={1}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        const prevButton = screen.getByRole('button', { name: /previous/i });
        expect(prevButton).toBeDisabled();
    });

    it('enables Previous button when not on first page', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        const prevButton = screen.getByRole('button', { name: /previous/i });
        expect(prevButton).not.toBeDisabled();
    });

    it('disables Next button when hasNextPage is false', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={5}
                onPageChange={onPageChange}
                hasNextPage={false}
            />
        );

        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).toBeDisabled();
    });

    it('enables Next button when hasNextPage is true', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={1}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).not.toBeDisabled();
    });

    it('calls onPageChange with decremented page when Previous is clicked', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={3}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        const prevButton = screen.getByRole('button', { name: /previous/i });
        fireEvent.click(prevButton);

        expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it('calls onPageChange with incremented page when Next is clicked', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        const nextButton = screen.getByRole('button', { name: /next/i });
        fireEvent.click(nextButton);

        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('disables both buttons when isLoading is true', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                onPageChange={onPageChange}
                hasNextPage={true}
                isLoading={true}
            />
        );

        const prevButton = screen.getByRole('button', { name: /previous/i });
        const nextButton = screen.getByRole('button', { name: /next/i });

        expect(prevButton).toBeDisabled();
        expect(nextButton).toBeDisabled();
    });

    it('displays item count information when provided', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                onPageChange={onPageChange}
                hasNextPage={true}
                totalItems={100}
                itemsPerPage={25}
            />
        );

        expect(screen.getByText(/Showing/)).toBeInTheDocument();
        expect(screen.getByText(/26/)).toBeInTheDocument(); // Start of page 2
        expect(screen.getByText(/50/)).toBeInTheDocument(); // End of page 2
        expect(screen.getByText(/100/)).toBeInTheDocument(); // Total
    });

    it('displays simple page number when item counts not provided', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={5}
                onPageChange={onPageChange}
                hasNextPage={true}
            />
        );

        expect(screen.getAllByText('Page 5')).toHaveLength(2); // One in info, one in middle
        expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    });
});

