import { useRef } from 'react';
import { TransitionGroup, CSSTransition } from 'react-transition-group';
import type { QueueItem } from '../../types';
import FocusCard from './FocusCard';
import './FocusDeck.css';

interface FocusDeckProps {
    items: QueueItem[];
    onAction: (item: QueueItem, action: 'link' | 'skip' | 'publish') => void;
    onSearch?: (item: QueueItem) => void;
    processingId: string | null;
}

// Separate component to handle the nodeRef required by CSSTransition in strict mode
const FocusDeckItem = ({ item, index, isActive, isNext, onAction, onSearch, processingId, ...props }: any) => {
    const nodeRef = useRef(null);
    return (
        <CSSTransition
            nodeRef={nodeRef}
            timeout={300}
            classNames={isActive ? "card-primary" : "card-secondary"}
            {...props}
        >
            <div
                ref={nodeRef}
                className={`absolute top-0 left-0 right-0 w-full transition-all duration-300 ${!isActive && !isNext ? 'hidden' : ''}`}
                style={{
                    zIndex: 10 - index,
                }}
            >
                <FocusCard
                    item={item}
                    isActive={isActive}
                    onAction={(action) => onAction(item, action)}
                    onSearch={onSearch ? () => onSearch(item) : undefined}
                    disabled={!!processingId}
                />
            </div>
        </CSSTransition>
    );
};

export default function FocusDeck({ items, onAction, onSearch, processingId }: FocusDeckProps) {
    if (!items || items.length === 0) {
        return (
            <div className="text-center py-20 text-gray-400 flex flex-col items-center">
                <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                    <span className="text-3xl">🎉</span>
                </div>
                <h2 className="text-xl font-medium text-gray-600">All caught up!</h2>
                <p>The discovery queue is empty.</p>
            </div>
        );
    }

    // Slice 0,2 for the stack visual
    const stackItems = items.slice(0, 2);

    return (
        <div className="relative w-full max-w-2xl mx-auto h-[500px] perspective-1000">
            <TransitionGroup component={null}>
                {stackItems.map((item, index) => (
                    <FocusDeckItem
                        key={item.signature}
                        item={item}
                        index={index}
                        isActive={index === 0}
                        isNext={index === 1}
                        onAction={onAction}
                        onSearch={onSearch}
                        processingId={processingId}
                    />
                ))}
            </TransitionGroup>
        </div>
    );
}
