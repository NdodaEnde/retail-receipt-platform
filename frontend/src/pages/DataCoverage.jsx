import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Progress } from "../components/ui/progress";
import { Badge } from "../components/ui/badge";
import { Gauge, RefreshCw, AlertTriangle } from "lucide-react";
import api from "../lib/api";

// The ontology auditing its own honesty: a declared insight is only as real as
// the coverage of the properties it reads. Green = ready, amber = partial,
// red = the gate blocking that part of the intelligence roadmap.
const tone = (pct) =>
  pct >= 80
    ? { bar: "bg-green-400", text: "text-green-400" }
    : pct >= 50
      ? { bar: "bg-yellow-400", text: "text-yellow-400" }
      : { bar: "bg-red-400", text: "text-red-400" };

export default function DataCoverage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshedAt, setRefreshedAt] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get("/analytics/ontology-coverage");
      setRows(res.data.data || []);
      setRefreshedAt(new Date());
    } catch (err) {
      console.error("Failed to fetch coverage:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const worst = [...rows].sort((a, b) => a.pct - b.pct).slice(0, 3);

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6 pb-24">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Gauge className="w-6 h-6 text-primary" />
          Data Coverage
        </h1>
        <p className="text-muted-foreground mt-1">
          How much of the data each declared insight needs actually exists. An insight is only
          as real as the coverage of what it reads.
        </p>
      </motion.div>

      {!loading && worst.length > 0 && (
        <Card className="glass border-white/10 border-l-4 border-l-red-400/70">
          <CardContent className="p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
            <div className="text-sm">
              <p className="font-semibold mb-1">Biggest gates right now</p>
              <p className="text-muted-foreground">
                {worst.map((w, i) => (
                  <span key={w.property}>
                    {i > 0 && " · "}
                    {w.label} <span className={tone(w.pct).text}>({w.pct}%)</span>
                  </span>
                ))}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="glass border-white/10">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Coverage by declared property</CardTitle>
          <button
            onClick={fetchData}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </CardHeader>
        <CardContent className="space-y-5">
          {loading && rows.length === 0 ? (
            [...Array(6)].map((_, i) => (
              <div key={i} className="h-12 bg-white/5 rounded animate-pulse" />
            ))
          ) : rows.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">No coverage data available.</p>
          ) : (
            rows.map((r, i) => {
              const t = tone(r.pct);
              return (
                <motion.div
                  key={r.property}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="space-y-1.5"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="flex items-baseline gap-2 min-w-0">
                      <span className="font-medium text-sm">{r.label}</span>
                      <code className="text-[10px] text-muted-foreground truncate">{r.property}</code>
                    </div>
                    <span className={`font-mono text-sm ${t.text}`}>
                      {r.covered}/{r.total} · {r.pct}%
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden">
                    <div className={`h-full rounded-full ${t.bar}`} style={{ width: `${r.pct}%` }} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Unlocks: {r.gates}
                  </p>
                </motion.div>
              );
            })
          )}
        </CardContent>
      </Card>

      {refreshedAt && (
        <p className="text-xs text-muted-foreground text-center">
          Live counts from production · refreshed {refreshedAt.toLocaleTimeString("en-ZA")}
        </p>
      )}
    </div>
  );
}
