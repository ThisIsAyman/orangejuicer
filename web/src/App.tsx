import { Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import WorkoutList from "./components/WorkoutList";
import WorkoutDetail from "./components/WorkoutDetail";
import DropZone from "./components/DropZone";
import LoginPanel from "./components/LoginPanel";
import SyncPanel from "./components/SyncPanel";
import { db } from "./store/db";
import { isLoggedIn } from "./otf/auth";
import { useState, useEffect } from "react";

function App() {
  const [hasData, setHasData] = useState(false);
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [refreshKey, setRefreshKey] = useState(0);
  const location = useLocation();

  useEffect(() => {
    db.workouts.count().then((c) => setHasData(c > 0));
  }, [refreshKey, location]);

  const handleImport = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleClear = async () => {
    await db.delete();
    await db.open();
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="logo">
          🍊 OrangeJuicer
        </Link>
        <nav>
          <Link to="/" className={location.pathname === "/" ? "active" : ""}>
            Dashboard
          </Link>
          <Link
            to="/workouts"
            className={location.pathname.startsWith("/workouts") ? "active" : ""}
          >
            Workouts
          </Link>
        </nav>
        <div className="header-actions">
          {loggedIn ? (
            <SyncPanel
              onSynced={handleImport}
              onLoggedOut={() => setLoggedIn(false)}
            />
          ) : (
            <DropZone onImport={handleImport} />
          )}
          {hasData && (
            <button className="btn-clear" onClick={handleClear} title="Clear all data">
              ✕ Clear
            </button>
          )}
        </div>
      </header>

      <main>
        {!loggedIn && !hasData ? (
          <div className="empty-state">
            <h2>Welcome to OrangeJuicer 🍊</h2>
            <p>Sign in to pull your OrangeTheory data straight into this browser:</p>
            <LoginPanel onLoggedIn={() => setLoggedIn(true)} />
            <p className="empty-or">— or —</p>
            <p>
              Export your workout data from the CLI
              (<code>python main.py export --full -o workouts.json</code>)
              and drag &amp; drop the JSON file above.
            </p>
          </div>
        ) : (
          <Routes>
            <Route path="/" element={<Dashboard key={refreshKey} />} />
            <Route path="/workouts" element={<WorkoutList key={refreshKey} />} />
            <Route path="/workouts/:id" element={<WorkoutDetail />} />
          </Routes>
        )}
      </main>
    </div>
  );
}

export default App;
