import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
    currentPage: number;
    onPageChange: (page: number) => void;
    hasNextPage: boolean;
    isLoading?: boolean;
    totalItems?: number;
    itemsPerPage?: number;
}

export default function Pagination({
    currentPage,
    onPageChange,
    hasNextPage,
    isLoading = false,
    totalItems,
    itemsPerPage,
}: PaginationProps) {
    const handlePrevious = () => {
        if (currentPage > 1 && !isLoading) {
            onPageChange(currentPage - 1);
        }
    };

    const handleNext = () => {
        if (hasNextPage && !isLoading) {
            onPageChange(currentPage + 1);
        }
    };

    const showingFrom = totalItems !== undefined && itemsPerPage !== undefined
        ? (currentPage - 1) * itemsPerPage + 1
        : null;
    
    const showingTo = totalItems !== undefined && itemsPerPage !== undefined
        ? Math.min(currentPage * itemsPerPage, totalItems)
        : null;

    return (
        <div className="flex items-center justify-between mt-6">
            {/* Info text */}
            <div className="text-sm text-gray-600">
                {showingFrom !== null && showingTo !== null && totalItems !== undefined ? (
                    <span>
                        Showing <span className="font-medium">{showingFrom}</span> to{' '}
                        <span className="font-medium">{showingTo}</span> of{' '}
                        <span className="font-medium">{totalItems}</span> results
                    </span>
                ) : (
                    <span>Page {currentPage}</span>
                )}
            </div>

            {/* Pagination buttons */}
            <div className="flex items-center gap-2">
                <button
                    onClick={handlePrevious}
                    disabled={currentPage === 1 || isLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
                    aria-label="Previous page"
                >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                </button>
                
                <div className="px-4 py-2 text-sm font-medium text-gray-700">
                    Page {currentPage}
                </div>
                
                <button
                    onClick={handleNext}
                    disabled={!hasNextPage || isLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
                    aria-label="Next page"
                >
                    Next
                    <ChevronRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}

