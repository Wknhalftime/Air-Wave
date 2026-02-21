import { useState, useEffect, useRef } from 'react';
import { Search, X, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { toTitleCase, formatArtistForDisplay } from '../../utils/format';
import { fetcher } from '../../lib/api';

// Constants
const SEARCH_DEBOUNCE_MS = 300;  // Delay before triggering search API call

interface SearchResult {
    id: number;  // Recording ID
    work_id: number;  // Phase 4: Work ID for identity layer
    artist: string;
    title: string;
    album: string | null;
    status: 'Gold' | 'Silver' | 'Bronze';
    type: 'track';
}

interface SearchResponse {
    tracks: SearchResult[];
    logs: unknown[];
}

interface SearchDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    onSelect: (recording: SearchResult) => void;
    initialQuery?: string;
}

export default function SearchDrawer({ isOpen, onClose, onSelect, initialQuery = '' }: SearchDrawerProps) {
    const [query, setQuery] = useState(initialQuery);
    const [debouncedQuery, setDebouncedQuery] = useState(initialQuery);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [includeBronze, setIncludeBronze] = useState(false);  // Default to Gold/Silver only
    const inputRef = useRef<HTMLInputElement>(null);
    const resultsRef = useRef<SearchResult[]>([]);  // Store results in ref for keyboard handler

    // Debounce search query
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(query.trim());  // Trim here to maintain query key consistency
        }, SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [query]);

    // Focus input when drawer opens
    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    // Update query when drawer opens with new initialQuery
    // Only update query state - let debounce effect handle debouncedQuery to prevent race condition
    useEffect(() => {
        if (isOpen) {
            setQuery(initialQuery);
            setSelectedIndex(0);
        }
    }, [isOpen, initialQuery]);

    // Fetch search results
    const searchParams = new URLSearchParams({
        q: debouncedQuery,
        type: 'track',
        include_bronze: includeBronze.toString(),
    });

    const { data, isLoading, isError, error } = useQuery({
        queryKey: ['search', debouncedQuery, includeBronze],  // Include bronze in cache key
        queryFn: () => fetcher<SearchResponse>(`/search/?${searchParams}`),
        enabled: debouncedQuery.length >= 2,
    });

    // Log errors to console for debugging
    useEffect(() => {
        if (isError) {
            console.error('Search API error:', error);
        }
    }, [isError, error]);

    const results = data?.tracks || [];

    // Update results ref when data changes
    useEffect(() => {
        resultsRef.current = results;
    }, [results]);

    // Keyboard navigation - optimized to only re-attach when drawer opens/closes
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            const currentResults = resultsRef.current;

            if (e.key === 'Escape') {
                onClose();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex((prev) => Math.min(prev + 1, currentResults.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex((prev) => Math.max(prev - 1, 0));
            } else if (e.key === 'Enter') {
                const selected = currentResults[selectedIndex];
                if (selected) {
                    e.preventDefault();
                    onSelect(selected);
                    onClose();
                }
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onSelect, onClose, selectedIndex]);  // Reduced dependencies

    // Reset selected index when results change
    useEffect(() => {
        setSelectedIndex(0);
    }, [results]);

    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/20 z-40 transition-opacity"
                onClick={onClose}
            />

            {/* Drawer */}
            <div className="fixed right-0 top-0 bottom-0 w-[400px] bg-white shadow-2xl z-50 flex flex-col">
                {/* Header */}
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-lg font-bold text-gray-900">Search Library</h2>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-gray-100 rounded transition-colors"
                        title="Close (Esc)"
                    >
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                {/* Search Input */}
                <div className="p-4 border-b border-gray-200">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search by artist or title..."
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                        Use ↑/↓ to navigate, Enter to select, Esc to close
                    </p>
                    <label className="flex items-center gap-2 mt-3 text-sm text-gray-600 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={includeBronze}
                            onChange={(e) => setIncludeBronze(e.target.checked)}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        Include unverified recordings (Bronze)
                    </label>
                </div>

                {/* Results */}
                <div className="flex-1 overflow-y-auto">
                    {isLoading && debouncedQuery.length >= 2 && (
                        <div className="flex items-center justify-center py-12" role="status" aria-live="polite">
                            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" aria-hidden="true" />
                            <span className="sr-only">Searching...</span>
                        </div>
                    )}

                    {isError && debouncedQuery.length >= 2 && (
                        <div className="flex items-center justify-center py-12 text-red-500 text-sm">
                            Search failed. Please try again.
                        </div>
                    )}

                    {!isLoading && !isError && debouncedQuery.length < 2 && (
                        <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                            Type at least 2 characters to search
                        </div>
                    )}

                    {!isLoading && !isError && debouncedQuery.length >= 2 && results.length === 0 && (
                        <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                            No results found
                        </div>
                    )}

                    {results.length > 0 && (
                        <div className="divide-y divide-gray-100">
                            {results.map((result, index) => (
                                <button
                                    key={result.id}
                                    onClick={() => {
                                        onSelect(result);
                                        onClose();
                                    }}
                                    className={`w-full text-left p-4 transition-colors ${index === selectedIndex
                                        ? 'bg-blue-50 border-l-4 border-blue-500'
                                        : 'hover:bg-gray-50'
                                        }`}
                                >
                                    <div className="font-semibold text-gray-900">{toTitleCase(result.title)}</div>
                                    <div className="text-sm text-gray-600 mt-1">{formatArtistForDisplay(result.artist)}</div>
                                    <div className="flex items-center gap-2 mt-2">
                                        <span
                                            className={`text-xs px-2 py-0.5 rounded font-medium ${result.status === 'Gold'
                                                ? 'bg-yellow-100 text-yellow-800'
                                                : 'bg-gray-100 text-gray-700'
                                                }`}
                                        >
                                            {result.status}
                                        </span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

