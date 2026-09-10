import { useState, useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Popup, CircleMarker, Polyline, useMap } from "react-leaflet";
import { Card, CardContent } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Store, MapPin, Route, Flame, Lock, ShieldCheck } from "lucide-react";
import axios from "axios";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { API } from "../App";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";

// ── palettes ────────────────────────────────────────────────────────────────
// Branches are coloured by owning chain; trips by the basket's dominant category.
const CHAIN_COLORS = {
  "Shoprite Group": "#ef4444", "Pick n Pay Group": "#3b82f6", "Woolworths": "#111827",
  "SPAR": "#16a34a", "Makro": "#f59e0b", "Clicks": "#db2777", "Dis-Chem": "#0891b2",
};
const OTHER_CHAIN = "#8b5cf6";
const CATEGORY_COLORS = {
  "Staples & Grocery": "#f59e0b", "Dairy & Eggs": "#60a5fa", "Meat & Poultry": "#ef4444",
  "Fresh Produce": "#22c55e", "Bread & Bakery": "#d97706", "Beverages": "#06b6d4",
  "Snacks & Sweets": "#ec4899", "Cleaning & Household": "#a3e635", "Toiletries & Health": "#c084fc",
  "Dining & Takeaways": "#fb923c", "Alcohol": "#7c3aed", "Other": "#9ca3af",
};
const TRUSTED = new Set(["verified", "rooftop", "street", "suburb"]);
const chainColor = (c) => CHAIN_COLORS[c] || OTHER_CHAIN;
const catColor = (c) => CATEGORY_COLORS[c] || CATEGORY_COLORS.Other;

// Quadratic-bezier arc between two points (lat/lng space is fine at city scale).
function arcPoints(a, b, bend = 0.18, steps = 24) {
  const [alat, alng] = a, [blat, blng] = b;
  const mlat = (alat + blat) / 2, mlng = (alng + blng) / 2;
  const dlat = blat - alat, dlng = blng - alng;
  const clat = mlat - dlng * bend, clng = mlng + dlat * bend;   // control point, perpendicular
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps, u = 1 - t;
    pts.push([u * u * alat + 2 * u * t * clat + t * t * blat, u * u * alng + 2 * u * t * clng + t * t * blng]);
  }
  return pts;
}

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    const b = L.latLngBounds(points);
    if (b.isValid()) map.fitBounds(b.pad(0.15), { maxZoom: 13 });
  }, [points, map]);
  return null;
}

const Chip = ({ active, onClick, icon: Icon, children, disabled }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border transition-colors
      ${active ? "bg-primary/20 border-primary/40 text-foreground" : "glass border-white/10 text-muted-foreground hover:text-foreground"}
      ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
  >
    <Icon className="w-4 h-4" />
    {children}
  </button>
);

export default function MapView() {
  const { session } = useAuth();
  const isAdmin = !!session;

  const [shops, setShops] = useState([]);
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBranches, setShowBranches] = useState(true);
  const [showTrips, setShowTrips] = useState(true);
  const [showSpend, setShowSpend] = useState(false);
  const [chain, setChain] = useState("all");
  const [category, setCategory] = useState("all");
  const [trustedOnly, setTrustedOnly] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        if (isAdmin) {
          const [s, r] = await Promise.all([api.get("/map/shops/detail"), api.get("/map/receipts")]);
          setShops(s.data.shops || []);
          setTrips(r.data.receipts || []);
        } else {
          const s = await axios.get(`${API}/map/shops`);
          setShops(s.data.shops || []);
          setTrips([]);
        }
      } catch (err) {
        console.error("Failed to fetch map data:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isAdmin]);

  const chains = useMemo(() => [...new Set(shops.map(s => s.chain).filter(Boolean))].sort(), [shops]);
  const categories = useMemo(() => [...new Set(trips.map(t => t.category).filter(Boolean))].sort(), [trips]);

  const visibleShops = useMemo(() => shops.filter(s =>
    (chain === "all" || s.chain === chain) &&
    (!trustedOnly || !isAdmin || TRUSTED.has(s.precision) || s.precision === "legacy")
  ), [shops, chain, trustedOnly, isAdmin]);

  const visibleTrips = useMemo(() => trips.filter(t =>
    t.upload_latitude != null && t.shop_latitude != null &&
    (chain === "all" || t.chain === chain) &&
    (category === "all" || t.category === category) &&
    (!trustedOnly || TRUSTED.has(t.precision))
  ), [trips, chain, category, trustedOnly]);

  const spendPoints = useMemo(() => trips.filter(t =>
    t.upload_latitude != null &&
    (chain === "all" || t.chain === chain) &&
    (category === "all" || t.category === category)
  ), [trips, chain, category]);

  const tripStats = useMemo(() => {
    const d = visibleTrips.map(t => parseFloat(t.distance_km)).filter(x => !isNaN(x)).sort((a, b) => a - b);
    if (!d.length) return null;
    return {
      count: visibleTrips.length,
      avg: d.reduce((a, b) => a + b, 0) / d.length,
      median: d[Math.floor(d.length / 2)],
      spend: visibleTrips.reduce((a, t) => a + (t.amount || 0), 0),
    };
  }, [visibleTrips]);

  const boundsPoints = useMemo(() => {
    const pts = [];
    if (showBranches) visibleShops.forEach(s => pts.push([s.latitude, s.longitude]));
    if (isAdmin && (showTrips || showSpend)) visibleTrips.forEach(t => pts.push([t.upload_latitude, t.upload_longitude]));
    return pts;
  }, [visibleShops, visibleTrips, showBranches, showTrips, showSpend, isAdmin]);

  const maxCount = Math.max(1, ...visibleShops.map(s => s.receipt_count || 0));

  return (
    <div className="min-h-screen" data-testid="map-view">
      <div className="p-6 pt-8 pb-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 mb-5">
            <div>
              <h1 className="font-heading text-3xl font-bold tracking-tight mb-1">Activity Map</h1>
              <p className="text-muted-foreground">
                {isAdmin ? "Branches, shopping trips and spend density" : "Verified retail branches on the platform"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Chip active={showBranches} onClick={() => setShowBranches(v => !v)} icon={Store}>Branches</Chip>
              <Chip active={isAdmin && showTrips} onClick={() => setShowTrips(v => !v)} icon={Route} disabled={!isAdmin}>Trips</Chip>
              <Chip active={isAdmin && showSpend} onClick={() => setShowSpend(v => !v)} icon={Flame} disabled={!isAdmin}>Spend density</Chip>
              <Chip active={trustedOnly} onClick={() => setTrustedOnly(v => !v)} icon={ShieldCheck}>Trusted locations</Chip>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-5">
            <Select value={chain} onValueChange={setChain}>
              <SelectTrigger className="w-[190px] glass border-white/10"><SelectValue placeholder="Chain" /></SelectTrigger>
              <SelectContent className="glass border-white/10">
                <SelectItem value="all">All chains</SelectItem>
                {chains.map(c => (
                  <SelectItem key={c} value={c}>
                    <span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ background: chainColor(c) }} />{c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isAdmin && (
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-[210px] glass border-white/10"><SelectValue placeholder="Category" /></SelectTrigger>
                <SelectContent className="glass border-white/10">
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map(c => (
                    <SelectItem key={c} value={c}>
                      <span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ background: catColor(c) }} />{c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Stats */}
          <div className={`grid gap-4 mb-6 ${isAdmin ? "grid-cols-2 md:grid-cols-4" : "grid-cols-1 md:grid-cols-2"}`}>
            <Card className="stat-card-purple rounded-2xl"><CardContent className="p-4 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center"><Store className="w-6 h-6 text-primary" /></div>
              <div><p className="font-mono text-2xl font-bold">{visibleShops.length}</p><p className="text-xs text-muted-foreground">Branches</p></div>
            </CardContent></Card>
            {isAdmin ? (
              <>
                <Card className="stat-card-green rounded-2xl"><CardContent className="p-4 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-secondary/20 flex items-center justify-center"><Route className="w-6 h-6 text-secondary" /></div>
                  <div><p className="font-mono text-2xl font-bold">{tripStats?.count ?? 0}</p><p className="text-xs text-muted-foreground">Trips</p></div>
                </CardContent></Card>
                <Card className="glass rounded-2xl"><CardContent className="p-4 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center"><MapPin className="w-6 h-6 text-accent" /></div>
                  <div>
                    <p className="font-mono text-2xl font-bold">{tripStats ? `${tripStats.median.toFixed(1)} km` : "—"}</p>
                    <p className="text-xs text-muted-foreground">Median trip{tripStats ? ` · avg ${tripStats.avg.toFixed(1)} km` : ""}</p>
                  </div>
                </CardContent></Card>
                <Card className="glass rounded-2xl"><CardContent className="p-4 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-yellow-400/20 flex items-center justify-center"><Flame className="w-6 h-6 text-yellow-400" /></div>
                  <div><p className="font-mono text-2xl font-bold">R{tripStats ? Math.round(tripStats.spend).toLocaleString("en-ZA") : 0}</p><p className="text-xs text-muted-foreground">Spend on map</p></div>
                </CardContent></Card>
              </>
            ) : (
              <Card className="glass rounded-2xl"><CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center"><Lock className="w-6 h-6 text-muted-foreground" /></div>
                <div><p className="text-sm font-medium">Trips & spend density</p><p className="text-xs text-muted-foreground">Admin sign-in required — customer locations are personal data</p></div>
              </CardContent></Card>
            )}
          </div>
        </div>
      </div>

      <div className="px-6 pb-24">
        <div className="max-w-6xl mx-auto">
          <Card className="glass-card overflow-hidden rounded-2xl">
            <div className="h-[560px] relative" data-testid="map-container">
              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-card">
                  <div className="text-center">
                    <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-muted-foreground">Loading map data...</p>
                  </div>
                </div>
              ) : (
                <MapContainer center={[-28.48, 24.67]} zoom={5} style={{ height: "100%", width: "100%" }} className="rounded-2xl">
                  {/* Key-free OSM tiles; index.css already inverts .leaflet-tile-pane for
                      the dark theme (CARTO's dark basemap needs an API key now). */}
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <FitBounds points={boundsPoints} />

                  {/* Spend density: soft discs at upload points, area ∝ amount */}
                  {isAdmin && showSpend && spendPoints.map(t => (
                    <CircleMarker
                      key={`s-${t.id}`}
                      center={[t.upload_latitude, t.upload_longitude]}
                      radius={6 + Math.sqrt(t.amount || 0) * 0.9}
                      pathOptions={{ fillColor: "#facc15", fillOpacity: 0.16, color: "#facc15", opacity: 0.25, weight: 1 }}
                      interactive={false}
                    />
                  ))}

                  {/* Trips: customer -> branch arcs, colour by category, weight by amount */}
                  {isAdmin && showTrips && visibleTrips.map(t => (
                    <Polyline
                      key={`t-${t.id}`}
                      positions={arcPoints([t.upload_latitude, t.upload_longitude], [t.shop_latitude, t.shop_longitude])}
                      pathOptions={{
                        color: catColor(t.category),
                        weight: 1.2 + Math.min(3, Math.sqrt(t.amount || 0) / 8),
                        opacity: t.fraud_flag === "valid" ? 0.7 : 0.35,
                        dashArray: t.fraud_flag === "valid" ? null : "4 6",
                      }}
                    >
                      <Popup>
                        <div className="p-1 min-w-[190px] text-sm">
                          <div className="font-semibold mb-1">{t.shop_name || "Shop"}</div>
                          <div className="flex justify-between text-xs"><span>Basket</span><span style={{ color: catColor(t.category) }}>{t.category}</span></div>
                          <div className="flex justify-between text-xs"><span>Amount</span><span className="font-mono">R{t.amount.toFixed(2)}</span></div>
                          <div className="flex justify-between text-xs"><span>Trip</span><span className="font-mono">{t.distance_km != null ? `${Number(t.distance_km).toFixed(1)} km` : "—"}</span></div>
                          <div className="flex justify-between text-xs"><span>Location</span><span>{t.precision}{t.fraud_flag !== "valid" ? ` · ${t.fraud_flag}` : ""}</span></div>
                        </div>
                      </Popup>
                    </Polyline>
                  ))}

                  {/* Branches: colour by chain, size by receipt count (admin) */}
                  {showBranches && visibleShops.map(s => (
                    <CircleMarker
                      key={s.id}
                      center={[s.latitude, s.longitude]}
                      radius={isAdmin ? 5 + 9 * Math.sqrt((s.receipt_count || 0) / maxCount) : 6}
                      pathOptions={{ fillColor: chainColor(s.chain), fillOpacity: 0.85, color: "#ffffff", weight: 1.2, opacity: 0.9 }}
                    >
                      <Popup>
                        <div className="p-1 min-w-[200px] text-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: chainColor(s.chain) }} />
                            <span className="font-semibold">{s.name}</span>
                          </div>
                          {s.chain && <div className="text-xs text-muted-foreground mb-1">{s.chain}</div>}
                          {isAdmin && (
                            <>
                              {s.address && <div className="text-xs text-muted-foreground mb-1">{s.address}</div>}
                              <div className="flex justify-between text-xs"><span>Receipts</span><span className="font-mono">{s.receipt_count}</span></div>
                              <div className="flex justify-between text-xs"><span>Revenue</span><span className="font-mono">R{s.total_sales.toFixed(2)}</span></div>
                              <div className="flex justify-between text-xs"><span>Location</span><span>{s.precision}{s.place_id ? " · Place ID" : ""}</span></div>
                            </>
                          )}
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
              )}
            </div>
          </Card>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 justify-center text-xs">
            {showBranches && chains.map(c => (
              <span key={c} className="flex items-center gap-1.5 glass px-3 py-1 rounded-full">
                <span className="w-3 h-3 rounded-full border border-white/60" style={{ background: chainColor(c) }} />{c}
              </span>
            ))}
            {isAdmin && showTrips && categories.map(c => (
              <span key={c} className="flex items-center gap-1.5 glass px-3 py-1 rounded-full">
                <span className="w-4 h-0.5 rounded" style={{ background: catColor(c) }} />{c}
              </span>
            ))}
            {isAdmin && showTrips && (
              <span className="flex items-center gap-1.5 glass px-3 py-1 rounded-full text-muted-foreground">
                <span className="w-4 h-0.5 rounded border-t border-dashed border-muted-foreground" />flagged / review trips dashed
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
