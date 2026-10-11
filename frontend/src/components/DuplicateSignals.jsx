import { useEffect, useState } from "react";
import { Copy, Users, Repeat, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import api from "../lib/api";

const KIND_LABEL = { same_image: "same photo", same_transaction: "same slip number", same_content: "same items & total" };
const fmt = (ts) => (ts ? new Date(ts).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");

// Admin-only (P-class: phone numbers). Who shares slips with whom — a cluster is a set of
// phones linked by slips that were entered more than once.
export default function DuplicateSignals() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/fraud/duplicates")
      .then((res) => setData(res.data))
      .catch((err) => { console.error("Failed to fetch duplicate signals:", err); setData({ error: true }); });
  }, []);

  const resends = data?.phones?.reduce((n, p) => n + p.resends, 0) || 0;
  const cross = data?.phones?.reduce((n, p) => n + p.cross_customer, 0) || 0;

  return (
    <Card className="glass-card rounded-2xl">
      <CardHeader>
        <CardTitle className="font-heading flex items-center gap-2">
          <Copy className="w-5 h-5 text-primary" />
          Shared slips
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          The same slip sent more than once (last 90 days). A resend by the same person is answered politely and not saved;
          a copy from someone else is kept out of the draw and lands in the review list above.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {!data && <p className="text-sm text-muted-foreground">Loading…</p>}
        {data?.error && <p className="text-sm text-red-400">Couldn't load shared-slip data.</p>}
        {data?.migration_needed && (
          <p className="text-sm text-amber-300/90 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Run migration 009 to start collecting shared-slip data.
          </p>
        )}
        {data && !data.error && !data.migration_needed && (
          <>
            <div className="grid grid-cols-3 gap-2">
              {[["Resends (same person)", resends, Repeat], ["Copies from others", cross, Copy], ["Linked groups", data.clusters.length, Users]].map(([k, v, Icon]) => (
                <div key={k} className="p-3 bg-black/20 rounded-lg border border-white/5">
                  <p className="text-xs text-muted-foreground flex items-center gap-1.5"><Icon className="w-3.5 h-3.5" />{k}</p>
                  <p className="font-mono font-bold text-lg">{v}</p>
                </div>
              ))}
            </div>

            {data.clusters.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Phones linked by shared slips</p>
                {data.clusters.map((c, i) => (
                  <div key={i} className="p-3 bg-black/20 rounded-lg border border-white/5 flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="border-orange-400/40 text-orange-300">{c.size} phones · {c.shared_slips} copies</Badge>
                    {c.phones.map((p) => <span key={p} className="font-mono text-xs">{p}</span>)}
                  </div>
                ))}
              </div>
            )}

            {data.recent.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-white/10">
                      <th className="py-2 pr-2">When</th>
                      <th className="py-2 pr-2">Sent by</th>
                      <th className="py-2 pr-2">Original from</th>
                      <th className="py-2 pr-2">Matched on</th>
                      <th className="py-2">Shop / amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent.map((s, i) => (
                      <tr key={i} className="border-b border-white/5">
                        <td className="py-2 pr-2 whitespace-nowrap">{fmt(s.created_at)}</td>
                        <td className="py-2 pr-2 font-mono text-xs">{s.customer_phone}</td>
                        <td className="py-2 pr-2 font-mono text-xs">
                          {s.kind === "resend" ? <span className="text-muted-foreground">same person</span> : s.matched_phone}
                        </td>
                        <td className="py-2 pr-2">{KIND_LABEL[s.match_kind] || s.match_kind}</td>
                        <td className="py-2 text-muted-foreground">
                          {s.details?.shop_name || "—"}{s.details?.amount ? ` · R${Number(s.details.amount).toFixed(2)}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No shared slips yet.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
