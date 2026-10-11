import { useEffect, useState } from "react";
import { ChevronRight, ArrowLeft, Store, MapPin, AlertTriangle, Users } from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import api from "../lib/api";

// One measure, ranked → one hue. Identity is carried by the row label, never by colour.
const BAR = "hsl(265, 89%, 66%)";

const rand = (v) => `R${Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (v) => `${Math.round((v || 0) * 100)}%`;

function Crumb({ label, onClick, last }) {
  return (
    <span className="flex items-center gap-1 min-w-0">
      {onClick && !last ? (
        <button onClick={onClick} className="text-primary hover:underline truncate">{label}</button>
      ) : (
        <span className="font-medium truncate">{label}</span>
      )}
      {!last && <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
    </span>
  );
}

function Summary({ node, kFloor }) {
  const c = node.coverage || {};
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          ["Spend", rand(node.spend)],
          ["Units", Number(node.units).toLocaleString()],
          ["Receipts", node.receipts],
          ["Shoppers", node.customers],
        ].map(([k, v]) => (
          <div key={k} className="p-3 bg-black/20 rounded-lg border border-white/5">
            <p className="text-xs text-muted-foreground">{k}</p>
            <p className="font-mono font-bold text-sm">{v}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Brand identified on {pct(c.brand)} of lines &middot; pack size on {pct(c.pack)}
        {c.price_conflicts > 0 && (
          <> &middot; {c.price_conflicts} line{c.price_conflicts > 1 ? "s" : ""} where total &ne; qty &times; price (smaller value counted)</>
        )}
      </p>
      {node.thin && (
        <p className="text-xs text-amber-300/90 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5" />
          Only {node.customers} shopper{node.customers === 1 ? "" : "s"} — under the {kFloor}-shopper floor, so this reflects individual habits, not a market.
        </p>
      )}
    </div>
  );
}

function Rows({ rows, onPick, kFloor }) {
  const max = Math.max(...rows.map((r) => r.spend), 0) || 1;
  return (
    <div className="space-y-1.5">
      {rows.map((r) => {
        const body = (
          <>
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex items-center gap-2">
                <span className="text-sm font-medium truncate">{r.name}</span>
                {r.brand_type === "house" && <Badge variant="outline" className="text-[10px] border-white/15 shrink-0">house brand</Badge>}
                {r.thin && <Badge variant="outline" className="text-[10px] border-amber-400/30 text-amber-300/90 shrink-0">thin</Badge>}
              </div>
              <div className="text-right shrink-0">
                <span className="font-mono font-bold text-sm">{rand(r.spend)}</span>
                <span className="text-xs text-muted-foreground ml-2">{pct(r.share)}</span>
              </div>
            </div>
            <div className="h-1.5 mt-1.5 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(100 * r.spend) / max}%`, background: BAR }} />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {r.lines} lines &middot; {Number(r.units).toLocaleString()} units &middot; {r.receipts} receipts &middot; {r.customers} shopper{r.customers === 1 ? "" : "s"}
              {r.coverage && r.coverage.brand < 1 && r.brands && <> &middot; brand known {pct(r.coverage.brand)}</>}
            </p>
          </>
        );
        const cls = `w-full text-left p-3 rounded-lg border border-white/5 bg-black/20 ${r.thin ? "opacity-60" : ""}`;
        return onPick ? (
          <button key={r.name} onClick={() => onPick(r.name)} title={`Drill into ${r.name}${r.thin ? ` (under ${kFloor} shoppers)` : ""}`}
            className={`${cls} hover:border-primary/40 hover:bg-primary/5 transition-colors group`}>
            {body}
          </button>
        ) : (
          <div key={r.name} className={cls}>{body}</div>
        );
      })}
    </div>
  );
}

function Split({ title, icon: Icon, rows, keyName }) {
  const shown = rows.slice(0, 8);
  return (
    <div className="p-3 bg-black/20 rounded-lg border border-white/5">
      <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5" /> {title}
      </p>
      <div className="space-y-1.5">
        {shown.map((r) => (
          <div key={r[keyName]} className={r.thin ? "opacity-60" : ""}>
            <div className="flex justify-between text-xs gap-2">
              <span className="truncate">{r[keyName]}</span>
              <span className="font-mono shrink-0">{pct(r.share)}</span>
            </div>
            <div className="h-1 mt-0.5 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${100 * r.share}%`, background: BAR }} />
            </div>
          </div>
        ))}
        {rows.length > shown.length && <p className="text-[11px] text-muted-foreground">+{rows.length - shown.length} more</p>}
      </div>
    </div>
  );
}

function Products({ products }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground border-b border-white/10">
            <th className="py-2 pr-2">Product</th>
            <th className="py-2 pr-2">Pack</th>
            <th className="py-2 pr-2 text-right">Units</th>
            <th className="py-2 pr-2 text-right">Avg / unit</th>
            <th className="py-2 pr-2 text-right">Spend</th>
            <th className="py-2 text-right">Shoppers</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p, i) => (
            <tr key={i} className="border-b border-white/5">
              <td className="py-2 pr-2">
                {p.name}
                {p.conflicts > 0 && <span title="OCR total disagreed with qty × price — smaller value counted"><AlertTriangle className="inline w-3 h-3 ml-1 text-amber-300/80" /></span>}
              </td>
              <td className="py-2 pr-2 text-muted-foreground">{p.pack || "—"}</td>
              <td className="py-2 pr-2 text-right font-mono">{Number(p.units).toLocaleString()}</td>
              <td className="py-2 pr-2 text-right font-mono">{p.avg_unit_price != null ? rand(p.avg_unit_price) : "—"}</td>
              <td className="py-2 pr-2 text-right font-mono font-bold">{rand(p.spend)}</td>
              <td className="py-2 text-right font-mono">{p.customers}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CategoryDrilldown({ category, onBack }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [sub, setSub] = useState(null);
  const [brand, setBrand] = useState(null);

  useEffect(() => {
    let live = true;
    setData(null); setError(null); setSub(null); setBrand(null);
    api.get("/analytics/category-drilldown", { params: { category } })
      .then((res) => live && setData(res.data))
      .catch((err) => { console.error("Failed to fetch category drill-down:", err); live && setError("Couldn't load this category."); });
    return () => { live = false; };
  }, [category]);

  const subNode = data && sub ? data.subcategories.find((s) => s.name === sub) : null;
  const brandNode = subNode && brand ? subNode.brands.find((b) => b.name === brand) : null;
  const node = brandNode || subNode || data;
  const kFloor = data?.k_floor || 5;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm flex-wrap">
        <Button variant="ghost" size="sm" onClick={onBack} className="h-7 px-2 -ml-2">
          <ArrowLeft className="w-4 h-4 mr-1" /> All categories
        </Button>
        <Crumb label={category} onClick={() => { setSub(null); setBrand(null); }} last={!sub} />
        {sub && <Crumb label={sub} onClick={() => setBrand(null)} last={!brand} />}
        {brand && <Crumb label={brand} last />}
      </div>

      {error && <p className="text-sm text-red-400 py-6 text-center">{error}</p>}
      {!data && !error && <p className="text-sm text-muted-foreground py-8 text-center">Loading {category}…</p>}

      {node && (
        <>
          <Summary node={node} kFloor={kFloor} />
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                {brandNode ? "Products & pack sizes" : subNode ? "Brands — tap to see products" : "Types — tap to see brands"}
              </p>
              {brandNode ? (
                <Products products={brandNode.products} />
              ) : (
                <Rows rows={subNode ? subNode.brands : data.subcategories}
                  onPick={subNode ? setBrand : setSub} kFloor={kFloor} />
              )}
            </div>
            <div className="space-y-3">
              <Split title="Where it's bought (chain)" icon={Store} rows={node.chains} keyName="chain" />
              <Split title="Shoppers' suburb" icon={MapPin} rows={node.suburbs} keyName="suburb" />
              <p className="text-[11px] text-muted-foreground flex items-start gap-1.5">
                <Users className="w-3.5 h-3.5 shrink-0 mt-px" />
                Submitted spend by KlpIT shoppers, not total market sales. Dimmed rows have fewer than {kFloor} shoppers.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
