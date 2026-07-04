import { Link, Route, Routes } from "react-router-dom";
import DisclaimerBanner from "./components/DisclaimerBanner";
import Dashboard from "./pages/Dashboard";
import TickerDetailPage from "./pages/TickerDetail";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-surface">
        <div className="mx-auto flex max-w-6xl items-baseline gap-3 px-4 py-3">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            InvTrack
          </Link>
          <span className="text-sm text-ink-2">
            congressional + insider + fundamentals research dashboard
          </span>
        </div>
      </header>
      <DisclaimerBanner />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ticker/:ticker" element={<TickerDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
