import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";

const STAGES = ["ingestion", "transformation", "validation", "storage"];
const COLORS = {
  ingestion: "#3b82f6",
  transformation: "#10b981",
  validation: "#f59e0b",
  storage: "#8b5cf6",
};

const timeLabel = (iso) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function Box({ title, children }) {
  return (
    <div className="chart-box">
      <h3>{title}</h3>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function Charts({ trends, alerts, infra }) {
  if (!trends.length) {
    return <p className="muted">Charts appear once runs have been reported.</p>;
  }

  const rows = trends.map((t) => ({
    name: timeLabel(t.started_at),
    duration: t.duration_seconds,
    records_in: t.records_in,
    records_out: t.records_out,
    completeness: t.completeness,
    validity: t.validity,
    ...t.stage_durations,
  }));

  const counts = {};
  alerts.forEach((a) => {
    counts[a.rule] = (counts[a.rule] || 0) + 1;
  });
  const byRule = Object.entries(counts).map(([rule, count]) => ({ rule, count }));

  const resource = [...infra].reverse().map((m) => ({
    name: timeLabel(m.timestamp),
    cpu: m.cpu_percent,
    memory: m.memory_percent,
  }));

  return (
    <section className="charts">
      <Box title="Run duration (s)">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Line type="monotone" dataKey="duration" stroke="#3b82f6" isAnimationActive={false} />
        </LineChart>
      </Box>

      <Box title="Stage duration per run (s)">
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Legend />
          {STAGES.map((s) => (
            <Bar key={s} dataKey={s} stackId="a" fill={COLORS[s]} isAnimationActive={false} />
          ))}
        </BarChart>
      </Box>

      <Box title="Data quality">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis domain={[0, 1]} fontSize={11} />
          <Tooltip />
          <Legend />
          <ReferenceLine
            y={0.95}
            stroke="#b91c1c"
            strokeDasharray="4 4"
            label={{ value: "completeness limit", fontSize: 10, fill: "#b91c1c" }}
          />
          <Line type="monotone" dataKey="completeness" stroke="#10b981" isAnimationActive={false} />
          <Line type="monotone" dataKey="validity" stroke="#f59e0b" isAnimationActive={false} />
        </LineChart>
      </Box>

      <Box title="Records in vs out">
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis fontSize={11} />
          <Tooltip />
          <Legend />
          <Bar dataKey="records_in" fill="#94a3b8" isAnimationActive={false} />
          <Bar dataKey="records_out" fill="#3b82f6" isAnimationActive={false} />
        </BarChart>
      </Box>

      <Box title="Alerts by rule">
        <BarChart data={byRule} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" allowDecimals={false} fontSize={11} />
          <YAxis type="category" dataKey="rule" width={130} fontSize={11} />
          <Tooltip />
          <Bar dataKey="count" fill="#f59e0b" isAnimationActive={false} />
        </BarChart>
      </Box>

      <Box title="CPU and memory (%)">
        <LineChart data={resource}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={11} />
          <YAxis domain={[0, 100]} fontSize={11} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="cpu" stroke="#ef4444" dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="memory" stroke="#6366f1" dot={false} isAnimationActive={false} />
        </LineChart>
      </Box>
    </section>
  );
}