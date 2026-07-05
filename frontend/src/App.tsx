import { Link, NavLink, Route, Routes } from "react-router-dom";
import DisclaimerBanner from "./components/DisclaimerBanner";
import Dashboard from "./pages/Dashboard";
import ScreenerPage from "./pages/Screener";
import TickerDetailPage from "./pages/TickerDetail";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2 py-1 text-sm ${isActive ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"}`;

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-baseline gap-3 px-4 py-3">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            InvTrack
          </Link>
          <nav className="flex items-baseline gap-1">
            <NavLink to="/" end className={navClass}>
              Dashboard
            </NavLink>
            <NavLink to="/screener" className={navClass}>
              Screener
            </NavLink>
          </nav>
          <span className="ml-auto hidden text-sm text-ink-2 sm:inline">
            congressional + insider + fundamentals research
          </span>
        </div>
      </header>
      <DisclaimerBanner />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/screener" element={<ScreenerPage />} />
          <Route path="/ticker/:ticker" element={<TickerDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
