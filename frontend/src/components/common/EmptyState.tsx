import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
    icon?: LucideIcon;
    title: string;
    description?: string;
    action?: ReactNode;
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
    return (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200 border-dashed">
            {Icon && (
                <div className="flex justify-center mb-4">
                    <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center">
                        <Icon className="w-8 h-8 text-gray-400" />
                    </div>
                </div>
            )}
            <h3 className="text-lg font-medium text-gray-900 mb-1">{title}</h3>
            {description && (
                <p className="text-gray-500 text-sm max-w-md mx-auto">{description}</p>
            )}
            {action && <div className="mt-6">{action}</div>}
        </div>
    );
}

