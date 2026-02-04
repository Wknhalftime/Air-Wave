import { clsx } from 'clsx';

interface CircularProgressProps {
    value: number; // 0-100
    size?: number;
    strokeWidth?: number;
    className?: string;
}

export function CircularProgress({
    value,
    size = 120,
    strokeWidth = 8,
    className
}: CircularProgressProps) {
    // 0 = Red, 70 = Yellow, 90 = Green
    const colorClass = value >= 90
        ? 'text-green-600'
        : value >= 70
            ? 'text-yellow-600'
            : 'text-red-600';

    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (value / 100) * circumference;

    return (
        <div className={clsx("relative flex items-center justify-center", className)} style={{ width: size, height: size }}>
            <svg
                width={size}
                height={size}
                viewBox={`0 0 ${size} ${size}`}
                className="transform -rotate-90"
            >
                {/* Background Circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    strokeWidth={strokeWidth}
                    className="fill-none stroke-gray-200"
                />
                {/* Progress Circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    strokeWidth={strokeWidth}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    className={clsx("fill-none transition-all duration-1000 ease-out", colorClass)}
                />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className={clsx("font-bold text-2xl", colorClass)}>{Math.round(value)}%</span>
            </div>
        </div>
    );
}
