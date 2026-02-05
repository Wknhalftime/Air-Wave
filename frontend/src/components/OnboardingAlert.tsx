import { useState } from 'react';
import { Link } from 'react-router-dom';
import { X, AlertCircle, Upload, FolderSync } from 'lucide-react';

interface OnboardingAlertProps {
    type: 'empty-library' | 'no-stations' | 'no-bridges';
    onDismiss?: () => void;
}

export function OnboardingAlert({ type, onDismiss }: OnboardingAlertProps) {
    const [isDismissed, setIsDismissed] = useState(false);

    const handleDismiss = () => {
        setIsDismissed(true);
        if (onDismiss) {
            onDismiss();
        }
    };

    if (isDismissed) {
        return null;
    }

    const config = {
        'empty-library': {
            icon: FolderSync,
            title: 'Your library is empty',
            message: 'Sync your music directory to get started and match broadcast logs to your local files.',
            cta: {
                text: 'Sync Files Now',
                to: '/admin',
                hash: '#status',
            },
            color: 'blue',
        },
        'no-stations': {
            icon: Upload,
            title: 'No stations found',
            message: 'Import a CSV file containing broadcast logs to begin tracking radio station playlists.',
            cta: {
                text: 'Import CSV',
                to: '/admin',
                hash: '#import',
            },
            color: 'indigo',
        },
        'no-bridges': {
            icon: AlertCircle,
            title: 'No identity bridges found',
            message: 'Run "Scan Logs" from the Admin page to create identity bridges for your matched logs.',
            cta: {
                text: 'Go to Admin',
                to: '/admin',
                hash: '#status',
            },
            color: 'purple',
        },
    };

    const alert = config[type];
    const Icon = alert.icon;

    const colorClasses = {
        blue: {
            bg: 'bg-blue-50',
            border: 'border-blue-200',
            icon: 'text-blue-600',
            text: 'text-blue-900',
            subtext: 'text-blue-700',
            button: 'bg-blue-600 hover:bg-blue-700',
            closeButton: 'text-blue-400 hover:text-blue-600',
        },
        indigo: {
            bg: 'bg-indigo-50',
            border: 'border-indigo-200',
            icon: 'text-indigo-600',
            text: 'text-indigo-900',
            subtext: 'text-indigo-700',
            button: 'bg-indigo-600 hover:bg-indigo-700',
            closeButton: 'text-indigo-400 hover:text-indigo-600',
        },
        purple: {
            bg: 'bg-purple-50',
            border: 'border-purple-200',
            icon: 'text-purple-600',
            text: 'text-purple-900',
            subtext: 'text-purple-700',
            button: 'bg-purple-600 hover:bg-purple-700',
            closeButton: 'text-purple-400 hover:text-purple-600',
        },
    };

    const colors = colorClasses[alert.color as keyof typeof colorClasses];

    return (
        <div className={`${colors.bg} border ${colors.border} rounded-lg p-4 mb-6`}>
            <div className="flex items-start gap-4">
                <Icon className={`w-6 h-6 ${colors.icon} flex-shrink-0 mt-0.5`} />
                <div className="flex-1">
                    <h3 className={`font-semibold ${colors.text} mb-1`}>
                        {alert.title}
                    </h3>
                    <p className={`text-sm ${colors.subtext} mb-3`}>
                        {alert.message}
                    </p>
                    <Link
                        to={`${alert.cta.to}${alert.cta.hash || ''}`}
                        className={`inline-flex items-center gap-2 px-4 py-2 ${colors.button} text-white text-sm rounded-lg font-medium transition-colors`}
                    >
                        {alert.cta.text}
                    </Link>
                </div>
                <button
                    onClick={handleDismiss}
                    className={`${colors.closeButton} flex-shrink-0 transition-colors`}
                    aria-label="Dismiss"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}

