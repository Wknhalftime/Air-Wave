import { useEffect } from 'react';
import { Undo, X } from 'lucide-react';

interface UndoBannerProps {
    summary: string;
    onUndo: () => void;
    onDismiss: () => void;
}

export default function UndoBanner({ summary, onUndo, onDismiss }: UndoBannerProps) {
    useEffect(() => {
        const timer = setTimeout(() => onDismiss(), 30000);
        return () => clearTimeout(timer);
    }, [onDismiss]);

    return (
        <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50 animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="bg-gray-900 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-4 min-w-[320px] max-w-lg">
                <div className="flex-1 text-sm font-medium truncate">
                    {summary}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={onUndo}
                        className="text-blue-400 hover:text-blue-300 font-semibold text-sm flex items-center gap-1.5 px-2 py-1 rounded hover:bg-white/10 transition-colors"
                    >
                        <Undo size={14} />
                        Undo
                    </button>
                    <button
                        onClick={onDismiss}
                        className="text-gray-400 hover:text-white p-1 rounded hover:bg-white/10 transition-colors"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
}
