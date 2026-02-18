import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import Library from './pages/Library';
import ArtistDetail from './pages/ArtistDetail';
import WorkDetail from './pages/WorkDetail';
import History from './pages/History';
import Analytics from './pages/Analytics';
import Admin from './pages/Admin';
import { MatchTuner } from './pages/admin/MatchTuner';
import Search from './pages/Search';
import Verification from './pages/Verification';
import Stations from './pages/Stations';
import StationDetail from './pages/StationDetail';
import Identity from './pages/Identity';
import Reports from './pages/Reports';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/library" element={<Library />} />
            <Route path="/library/artists/:id" element={<ArtistDetail />} />
            <Route path="/library/works/:id" element={<WorkDetail />} />
            <Route path="/stations" element={<Stations />} />
            <Route path="/stations/:id" element={<StationDetail />} />
            <Route path="/identity" element={<Identity />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/history" element={<History />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="/admin/tuner" element={<MatchTuner />} />
            <Route path="/search" element={<Search />} />
            <Route path="/verification" element={<Verification />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
