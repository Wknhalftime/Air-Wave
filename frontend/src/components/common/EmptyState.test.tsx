/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Inbox } from 'lucide-react';
import EmptyState from './EmptyState';

describe('EmptyState', () => {
    it('renders title', () => {
        render(<EmptyState title="No items found" />);

        expect(screen.getByText('No items found')).toBeInTheDocument();
    });

    it('renders description when provided', () => {
        render(
            <EmptyState
                title="No items found"
                description="Try adjusting your filters"
            />
        );

        expect(screen.getByText('Try adjusting your filters')).toBeInTheDocument();
    });

    it('does not render description when not provided', () => {
        render(<EmptyState title="No items found" />);

        expect(screen.queryByText(/Try/)).not.toBeInTheDocument();
    });

    it('renders icon when provided', () => {
        const { container } = render(
            <EmptyState icon={Inbox} title="No items found" />
        );

        // Check that an SVG element exists (Lucide icons render as SVG)
        const svg = container.querySelector('svg');
        expect(svg).toBeInTheDocument();
    });

    it('does not render icon when not provided', () => {
        const { container } = render(<EmptyState title="No items found" />);

        const svg = container.querySelector('svg');
        expect(svg).not.toBeInTheDocument();
    });

    it('renders action element when provided', () => {
        render(
            <EmptyState
                title="No items found"
                action={<button>Add Item</button>}
            />
        );

        expect(screen.getByRole('button', { name: 'Add Item' })).toBeInTheDocument();
    });

    it('does not render action when not provided', () => {
        render(<EmptyState title="No items found" />);

        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('renders all props together', () => {
        const { container } = render(
            <EmptyState
                icon={Inbox}
                title="Empty Library"
                description="Start by adding some music files"
                action={<button>Browse Files</button>}
            />
        );

        expect(screen.getByText('Empty Library')).toBeInTheDocument();
        expect(screen.getByText('Start by adding some music files')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Browse Files' })).toBeInTheDocument();
        expect(container.querySelector('svg')).toBeInTheDocument();
    });
});

