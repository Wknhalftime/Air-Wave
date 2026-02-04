import { useQuery } from '@tanstack/react-query';
import { fetcher } from '../lib/api';
import { Radio, Signal } from 'lucide-react';
import { Link } from 'react-router-dom';
import { CircularProgress } from '../components/CircularProgress';

interface Station {
  id: number;
  callsign: string;
  total_logs: number;
  matched_logs: number;
  match_rate: number;
}

export default function Stations() {
  const { data: stations, isLoading } = useQuery({
    queryKey: ['stations'],
    queryFn: () => fetcher<Station[]>('/stations/')
  });

  if (isLoading) return <div className="text-gray-500">Loading stations...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Station Hub</h1>
          <p className="text-gray-500 mt-1">Monitor matching performance across all broadcast sources.</p>
        </div>
        <div className="bg-indigo-50 text-indigo-700 px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
          <Signal className="w-4 h-4" />
          {stations?.length || 0} Active Stations
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {stations?.map((station) => (
          <Link
            key={station.id}
            to={`/stations/${station.id}`}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow relative overflow-hidden group"
          >
            <div className="absolute top-0 right-0 p-4 opacity-50 text-gray-100 group-hover:text-gray-200 transition-colors">
              <Radio size={100} strokeWidth={1} />
            </div>

            <div className="relative z-10 flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{station.callsign}</h2>
                <div className="mt-4 space-y-1 text-sm text-gray-600">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    On-Air
                  </div>
                  <div>{station.total_logs.toLocaleString()} Total Logs</div>
                  <div>{station.matched_logs.toLocaleString()} Matched</div>
                </div>
              </div>

              <CircularProgress value={station.match_rate} size={80} strokeWidth={6} />
            </div>
          </Link>
        ))}

        {(!stations || stations.length === 0) && (
          <div className="col-span-full py-12 text-center text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-300">
            <Radio className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <h3 className="text-lg font-medium text-gray-900">No Stations Found</h3>
            <p>Import broadcast logs to populate this dashboard.</p>
          </div>
        )}
      </div>
    </div>
  );
}