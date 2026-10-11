import { useEffect, useState } from "react";
import { ChevronDown, MapPinned, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import api from "../lib/api";

const SEGMENT_COLORS = ["hsl(265, 89%, 66%)", "hsl(150, 100%, 45%)", "hsl(300, 100%, 55%)", "hsl(190, 100%, 50%)"];
const OTHER_COLOR = "hsl(0, 0%, 35%)";

const rand = (v) => `R${Math.round(v).toLocaleString("en-ZA")}`;
const pct = (v) => `${Math.round(v * 100)}%`;
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Top 4 branches as coloured segments, the rest as one grey "other" segment.
function ShareBar({ split }) {
  const top = split.slice(0, 4);
  const other = split.slice(4).reduce((s, x) => s + x.share, 0);
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-full bg-white/5" aria-hidden="true">
      {top.map((s, i) => (
        <div key={s.shop_id || s.name} style={{ width: pct(s.share), background: SEGMENT_COLORS[i] }} title={`${s.name} ${pct(s.share)}`} />
      ))}
      {other > 0 && <div style={{ width: pct(other), background: OTHER_COLOR }} title={`Other branches ${pct(other)}`} />}
    </div>
  );
}

function SuburbRow({ s, kFloor }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-xl bg-white/5 p-4 ${s.thin ? "opacity-50" : ""}`} data-testid="wallet-suburb">
      <button onClick={() => setOpen(!open)} className="w-full text-left space-y-3" aria-expanded={open}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <span className="font-heading text-lg font-semibold">{s.suburb}</span>
            {s.locality && s.locality !== s.suburb && <span className="ml-2 text-sm text-muted-foreground">{s.locality}</span>}
            {s.thin && <Badge variant="outline" className="ml-2 border-yellow-500/40 text-yellow-500">under {kFloor} customers — internal only</Badge>}
          </div>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span>{plural(s.customers, "customer")}</span>
            <span>{plural(s.receipts, "receipt")}</span>
            <span className="font-mono font-semibold text-foreground">{rand(s.spend)}</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
          </div>
        </div>
        <ShareBar split={s.split} />
        {s.leader && (
          <p className="text-sm text-muted-foreground">
            Leader: <span className="text-foreground font-medium">{s.leader.name}</span> · {pct(s.leader.share)} of spend
          </p>
        )}
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            {s.chains.map((c) => (
              <Badge key={c.chain} variant="secondary" className="font-normal">{c.chain} · {pct(c.share)}</Badge>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr><th className="py-1 pr-3 font-medium">Branch</th><th className="pr-3 font-medium">Chain</th><th className="pr-3 font-medium text-right">Receipts</th><th className="pr-3 font-medium text-right">Customers</th><th className="pr-3 font-medium text-right">Spend</th><th className="font-medium text-right">Share</th></tr>
              </thead>
              <tbody>
                {s.split.map((b) => (
                  <tr key={b.shop_id || b.name} className="border-t border-white/5">
                    <td className="py-1.5 pr-3">{b.name}</td>
                    <td className="pr-3 text-muted-foreground">{b.chain}</td>
                    <td className="pr-3 text-right font-mono">{b.receipts}</td>
                    <td className="pr-3 text-right font-mono">{b.customers}</td>
                    <td className="pr-3 text-right font-mono">{rand(b.spend)}</td>
                    <td className="text-right font-mono">{pct(b.share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const VIEWS = {
  home: {
    label: "Home area",
    blurb: "Grouped by the home area each customer chose to tell us (asked once, optional). This is where people live — so it shows which branches win each area's spend, including spend that leaves the area.",
    empty: "No customer has shared a home area yet. The bot asks after registration, and existing customers after their next receipt.",
    unassigned: (d) => `${d.unassigned} receipts from customers without an area`,
  },
  upload: {
    label: "Where receipts are sent from",
    blurb: "Grouped by the suburb each receipt was sent from. Many are sent at the till, so this often matches the shop's own suburb rather than where the customer lives.",
    empty: "No receipts have a suburb yet. Run the suburb backfill.",
    unassigned: (d) => `${d.unassigned} located receipts without a suburb yet`,
  },
};

const SETUP = {
  "007": <>Run <code className="font-mono">backend/migrations/007_wallet_share.sql</code> in the Supabase SQL editor, then <code className="font-mono">python scripts/backfill_suburbs.py --apply</code>.</>,
  "008": <>Run <code className="font-mono">backend/migrations/008_home_area.sql</code> in the Supabase SQL editor. Customers are then asked for their area as they use KlpIT.</>,
};

// Admin-only: share of wallet by suburb (ontology: suburbWalletShare). Two groupings, both kept.
export default function WalletShareTab() {
  const [by, setBy] = useState("home");
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    api.get(`/analytics/wallet-share?by=${by}`)
      .then((res) => setData(res.data))
      .catch((e) => { console.error("Failed to fetch wallet share:", e); setError(true); });
  }, [by]);

  const view = VIEWS[by];
  return (
    <Card className="glass-card rounded-2xl" data-testid="wallet-share">
      <CardHeader className="space-y-3">
        <CardTitle className="font-heading flex items-center gap-2">
          <MapPinned className="w-5 h-5 text-primary" />
          Share of wallet by suburb
        </CardTitle>
        <div className="inline-flex w-fit rounded-lg bg-white/5 p-1 text-sm" role="tablist" aria-label="Group suburbs by">
          {Object.entries(VIEWS).map(([key, v]) => (
            <button
              key={key}
              role="tab"
              aria-selected={by === key}
              onClick={() => setBy(key)}
              data-testid={`wallet-by-${key}`}
              className={`rounded-md px-3 py-1.5 transition-colors ${by === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">
          {view.blurb} Personal data, so this view is for staff only. It shows spend submitted to KlpIT, not a suburb's full wallet.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-red-400">Couldn't load suburb data.</p>}
        {!data && !error && <p className="text-sm text-muted-foreground">Loading…</p>}
        {data?.migration_needed && (
          <div className="flex gap-3 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm" data-testid="wallet-migration-needed">
            <AlertTriangle className="w-5 h-5 shrink-0 text-yellow-500" />
            <p>Not set up yet. {SETUP[data.migration_needed] || SETUP["007"]}</p>
          </div>
        )}
        {data && !data.migration_needed && (
          <>
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge variant="outline">{data.suburbs.length} suburbs</Badge>
              <Badge variant="outline">{data.suburbs.filter((s) => s.thin).length} with fewer than {data.k_floor} customers (dimmed)</Badge>
              {by === "home" && data.customers_total != null && (
                <Badge variant="outline" data-testid="wallet-area-coverage">{data.customers_with_area} of {data.customers_total} customers have shared an area</Badge>
              )}
              {data.unassigned > 0 && <Badge variant="outline">{view.unassigned(data)}</Badge>}
            </div>
            {data.suburbs.length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="wallet-empty">{view.empty}</p>
            ) : (
              <div className="space-y-3">
                {data.suburbs.map((s) => <SuburbRow key={s.suburb} s={s} kFloor={data.k_floor} />)}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
