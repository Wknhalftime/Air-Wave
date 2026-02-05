import type { QueueItem } from '../../types';
import { Check, X, AlertCircle, CheckCircle2, Search } from 'lucide-react';
import { renderDiff } from '../../utils/diff';

interface FocusCardProps {
    item: QueueItem;
    isActive: boolean;
    onAction: (action: 'link' | 'skip' | 'publish') => void;
    onSearch?: () => void;
    disabled?: boolean;
}

export default function FocusCard({ item, isActive, onAction, onSearch, disabled }: FocusCardProps) {
    const apiArtist = item.suggested_recording?.work?.artist?.name || "Unknown";
    const apiTitle = item.suggested_recording?.title || "Unknown";

    return (
        <div
            className={`
                bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden
                w-full max-w-2xl mx-auto
                transform transition-all duration-300
                will-change-transform will-change-opacity
                ${isActive ? 'opacity-100 scale-100 shadow-2xl z-10' : 'opacity-0 scale-95 z-0 absolute top-0 left-0 right-0 mx-auto'}
            `}
            style={{
                transform: isActive ? 'translate3d(0,0,0) scale(1)' : 'translate3d(0,20px,0) scale(0.95)',
            }}
        >
            {/* Header / Context */}
            <div className="bg-gray-50 border-b border-gray-100 px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <span className="bg-white border border-gray-200 px-2 py-0.5 rounded shadow-sm">
                        {item.count} detections
                    </span>
                    <span>{item.signature.substring(0, 12)}...</span>
                </div>
                {item.suggested_recording ? (
                    <div className="flex items-center gap-1 text-green-600 bg-green-50 px-2 py-1 rounded text-xs font-bold">
                        <AlertCircle className="w-3 h-3" />
                        <span>Match Found</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-1 text-amber-600 bg-amber-50 px-2 py-1 rounded text-xs font-bold">
                        <AlertCircle className="w-3 h-3" />
                        <span>Unmatched</span>
                    </div>
                )}
            </div>

            {/* Main Content Area */}
            <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8 items-start relative">

                {/* INCOMING */}
                <div className="space-y-3 relative z-10">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="w-1 h-5 bg-orange-500 rounded-full"></div>
                        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Incoming Signal</span>
                    </div>
                    <div>
                        <div className="font-bold text-gray-900 text-2xl leading-tight font-mono break-words">{item.raw_title}</div>
                        <div className="text-lg text-gray-600 mt-1 font-mono break-words">{item.raw_artist}</div>
                    </div>
                </div>

                {/* Divider (Desktop) */}
                <div className="hidden md:block absolute left-1/2 top-8 bottom-8 w-px bg-gray-100 -ml-px"></div>

                {/* SUGGESTION */}
                <div className="space-y-3 relative z-10 w-full min-w-0">
                    <div className="flex items-center gap-2 mb-4">
                        <div className={`w-1 h-5 rounded-full ${item.suggested_recording ? 'bg-green-500' : 'bg-gray-300'}`}></div>
                        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                            {item.suggested_recording ? "Suggested Library Match" : "Suggestion"}
                        </span>
                    </div>
                    {item.suggested_recording ? (
                        <div className="w-full min-w-0">
                            {/* Title Diff */}
                            <div className="mb-2 w-full">
                                <span className="text-xs text-gray-400 font-medium block mb-0.5">Title</span>
                                <div className="font-bold text-gray-900 text-2xl leading-tight font-sans break-words">
                                    {renderDiff(item.raw_title, apiTitle, "Title")}
                                </div>
                            </div>

                            {/* Artist Diff */}
                            <div className="w-full">
                                <span className="text-xs text-gray-400 font-medium block mb-0.5">Artist</span>
                                <div className="text-lg text-gray-600 mt-1 font-sans break-words">
                                    {renderDiff(item.raw_artist, apiArtist, "Artist")}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="h-24 flex items-center justify-center border-2 border-dashed border-gray-100 rounded-lg bg-gray-50/50">
                            <span className="text-gray-400 italic text-sm">No confident match found</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Actions Footer */}
            <div className="bg-gray-50 border-t border-gray-200 p-4 grid grid-cols-4 gap-3">
                <button
                    onClick={() => onAction('skip')}
                    disabled={disabled}
                    className="flex flex-col items-center justify-center gap-1 py-3 px-2 rounded-lg text-gray-600 hover:bg-white hover:text-red-600 hover:shadow border border-transparent hover:border-gray-200 transition-all active:scale-95 group"
                    title="Shortcut: N"
                >
                    <X className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    <span className="text-xs font-bold uppercase tracking-wide">Skip</span>
                </button>

                {item.suggested_recording ? (
                    <button
                        onClick={() => onAction('link')}
                        disabled={disabled}
                        className="flex flex-col items-center justify-center gap-1 py-3 px-2 rounded-lg bg-green-600 text-white hover:bg-green-500 shadow-sm hover:shadow-md transition-all active:scale-95 group"
                        title="Shortcut: Y"
                    >
                        <Check className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        <span className="text-xs font-bold uppercase tracking-wide">Link</span>
                    </button>
                ) : (
                    <button
                        onClick={onSearch}
                        disabled={disabled || !onSearch}
                        className="flex flex-col items-center justify-center gap-1 py-3 px-2 rounded-lg text-gray-600 hover:bg-white hover:text-purple-600 hover:shadow border border-transparent hover:border-gray-200 transition-all active:scale-95 group disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Shortcut: S"
                    >
                        <Search className="w-6 h-6 group-hover:scale-110 transition-transform" />
                        <span className="text-xs font-bold uppercase tracking-wide">Search</span>
                    </button>
                )}

                <button
                    onClick={() => onAction('publish')}
                    disabled={disabled}
                    className="flex flex-col items-center justify-center gap-1 py-3 px-2 rounded-lg text-gray-600 hover:bg-white hover:text-blue-600 hover:shadow border border-transparent hover:border-gray-200 transition-all active:scale-95 group"
                    title="Shortcut: P"
                >
                    <CheckCircle2 className="w-6 h-6 group-hover:scale-110 transition-transform" />
                    <span className="text-xs font-bold uppercase tracking-wide">Publish</span>
                </button>
            </div>
        </div>
    );
}
