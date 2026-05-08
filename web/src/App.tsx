import { Routes, Route, Link, useLocation } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import WorkoutList from "./components/WorkoutList";
import WorkoutDetail from "./components/WorkoutDetail";
import DropZone from "./components/DropZone";
import { db } from "./store/db";
import { useState, useEffect } from "react";

function App() {
  const [hasData, setHasData] = useState(false);
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
          <DropZone onImport={handleImport} />
          {hasData && (
            <button className="btn-clear" onClick={handleClear} title="Clear all data">
              ✕ Clear
            </button>
          )}
        </div>
      </header>

      <main>
        {!hasData ? (
          <div className="empty-state">
            <h2>Welcome to OrangeJuicer 🍊</h2>
            <p>
              Export your workout data from the CLI:
              <code>python main.py export --full -o workouts.json</code>
            </p>
            <p>Then drag &amp; drop the JSON file above to get started.</p>
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
