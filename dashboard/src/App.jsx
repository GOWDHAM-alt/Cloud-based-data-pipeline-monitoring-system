import { useCallback, useEffect, useState } from "react";
import { getSummary, getRuns, getRun, getAlerts, getInfra } from "./api";
import "./App.css";

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "-");

function duration(start, end) {
  if (!start || !end) return "-";
  return `${Math.round((new Date(end) - new Date(start)) / 1000)}s`;
}

function Badge({ value }) {
  return <span className={`badge ${value}`}>{value}</span>;
}

function Card({ label, value, tone }) {
  return (
    <div className={`card ${tone || ""}`}>
      <div className="card-value">{value ?? "-"}</div>
      <div className="card-label">{label}</div>
    </div>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [infra, setInfra] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [updated, setUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, r, a, i] = await Promise.all([
        getSummary(),
        getRuns(),
        getAlerts(),
        getInfra(),
      ]);
      setSummary(s);
      setRuns(r);
      setAlerts(a);
      setInfra(i);
      setError(null);
      setUpdated(new Date());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    getRun(selected)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [selected, runs]);

  const runAlerts = selected ? alerts.filter((a) => a.run_id === selected) : [];

  return (
    <div className="page">
      <header>
        <h1>Pipeline Monitor</h1>
        <span className="muted">
          {updated ? `Updated ${updated.toLocaleTimeString()}` : "Loading..."}
        </span>
      </header>

      {error && <div className="error">Cannot reach the API: {error}</div>}

      <section className="cards">
        <Card label="Total runs" value={summary?.total_runs} />
        <Card label="Success" value={summary?.success} tone="ok" />
        <Card label="Failed" value={summary?.failed} tone="bad" />
        <Card label="Running" value={summary?.running} />
        <Card label="Recent alerts" value={alerts.length} tone="warn" />
      </section>

      <div className="grid">
        <section className="panel">
          <h2>Recent runs</h2>
          <table>
            <thead>
              <tr>
                <th>Pipeline</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Records out</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.run_id}
                  className={r.run_id === selected ? "selected" : "clickable"}
                  onClick={() => setSelected(r.run_id === selected ? null : r.run_id)}
                >
                  <td>{r.pipeline}</td>
                  <td><Badge value={r.status} /></td>
                  <td>{fmt(r.started_at)}</td>
                  <td>{duration(r.started_at, r.ended_at)}</td>
                  <td>{r.records_out ?? "-"}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr><td colSpan="5" className="muted">No runs yet</td></tr>
              )}
            </tbody>
          </table>
        </section>

        <section className="panel">
          <h2>Alerts</h2>
          {alerts.length === 0 && <p className="muted">No alerts</p>}
          <ul className="alerts">
            {alerts.map((a) => (
              <li key={a.id}>
                <Badge value={a.severity} />
                <div>
                  <div>{a.message}</div>
                  <div className="muted small">
                    {a.rule}{a.stage ? ` · ${a.stage}` : ""} · {fmt(a.created_at)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {detail && (
        <section className="panel">
          <h2>Run detail: {detail.run.pipeline}</h2>
          <p className="muted small">{detail.run.run_id}</p>

          <h3>Stages</h3>
          <table>
            <thead>
              <tr>
                <th>Stage</th><th>Status</th><th>Duration</th>
                <th>In</th><th>Out</th><th>Error</th>
              </tr>
            </thead>
            <tbody>
              {detail.stages.map((s) => (
                <tr key={s.stage}>
                  <td>{s.stage}</td>
                  <td><Badge value={s.status} /></td>
                  <td>{duration(s.started_at, s.ended_at)}</td>
                  <td>{s.records_in ?? "-"}</td>
                  <td>{s.records_out ?? "-"}</td>
                  <td>{s.error_message || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Data quality</h3>
          {detail.quality.length === 0 ? (
            <p className="muted">No measurements</p>
          ) : (
            <table>
              <thead>
                <tr><th>Stage</th><th>Metric</th><th>Value</th></tr>
              </thead>
              <tbody>
                {detail.quality.map((q, i) => (
                  <tr key={i}>
                    <td>{q.stage}</td>
                    <td>{q.metric}</td>
                    <td>{q.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Events</h3>
          {detail.events.length === 0 ? (
            <p className="muted">No events</p>
          ) : (
            <ul className="alerts">
              {detail.events.map((e, i) => (
                <li key={i}>
                  <Badge value={e.level} />
                  <div>
                    <div>{e.message}</div>
                    <div className="muted small">
                      {e.stage || "-"} · {fmt(e.timestamp)}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <h3>Alerts for this run</h3>
          {runAlerts.length === 0 ? (
            <p className="muted">None</p>
          ) : (
            <ul className="alerts">
              {runAlerts.map((a) => (
                <li key={a.id}>
                  <Badge value={a.severity} />
                  <div>{a.message}</div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="panel">
        <h2>Latest infrastructure metrics</h2>
        {infra.length === 0 ? (
          <p className="muted">No metrics yet</p>
        ) : (
          <table>
            <thead>
              <tr><th>Host</th><th>Time</th><th>CPU %</th><th>Memory %</th></tr>
            </thead>
            <tbody>
              {infra.map((m, i) => (
                <tr key={i}>
                  <td>{m.host}</td>
                  <td>{fmt(m.timestamp)}</td>
                  <td>{m.cpu_percent}</td>
                  <td>{m.memory_percent}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}