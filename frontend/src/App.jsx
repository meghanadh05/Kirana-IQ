import { useEffect, useState } from 'react';
import { getHealth } from './services/api.js';

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="shell">
      <header className="header">
        <h1>Kirana-IQ</h1>
        <p>AI-powered inventory forecasting for small retail stores</p>
      </header>

      <main className="panel">
        <h2>Backend status</h2>
        {error && <p className="status status--error">Cannot reach API: {error}</p>}
        {!error && !health && <p className="status">Checking…</p>}
        {health && (
          <dl className="facts">
            <div><dt>API</dt><dd>{health.status}</dd></div>
            <div><dt>Database</dt><dd>{health.database}</dd></div>
            <div><dt>Version</dt><dd>{health.version}</dd></div>
            <div><dt>Environment</dt><dd>{health.environment}</dd></div>
          </dl>
        )}
      </main>

      <footer className="footer">
        Phase 1 scaffold — products, forecasting and inventory pages come next.
      </footer>
    </div>
  );
}
