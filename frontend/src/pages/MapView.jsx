import { useState, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from "react-leaflet";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Store, MapPin, Receipt, Users } from "lucide-react";
import axios from "axios";
import { API } from "../App";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default marker icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// Custom icons
const shopIcon = new L.DivIcon({
  className: "custom-marker",
  html: `<div style="background: linear-gradient(135deg, #8b5cf6, #a855f7); width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px rgba(139, 92, 246, 0.5);">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <polyline points="9,22 9,12 15,12 15,22"/>
    </svg>
  </div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
});

const receiptIcon = new L.DivIcon({
  className: "custom-marker",
  html: `<div style="background: linear-gradient(135deg, #00ff80, #00cc66); width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px rgba(0, 255, 128, 0.5);">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="black" stroke-width="2">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14,2 14,8 20,8"/>
    </svg>
  </div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 24],
  popupAnchor: [0, -24],
});

export default function MapView() {
  const [shops, setShops] = useState([]);
  const [receipts, setReceipts] = useState([]);
  const [viewMode, setViewMode] = useState("shops");
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total_shops: 0, total_receipts: 0 });

  useEffect(() => {
    fetchMapData();
  }, []);

  const fetchMapData = async () => {
    setLoading(true);
    try {
      const [shopsRes, receiptsRes] = await Promise.all([
        axios.get(`${API}/map/shops`),
        axios.get(`${API}/map/receipts`)
      ]);
      
      setShops(shopsRes.data.shops);
      setReceipts(receiptsRes.data.receipts);
      setStats({
        total_shops: shopsRes.data.shops.length,
        total_receipts: receiptsRes.data.receipts.length
      });
    } catch (error) {
      console.error("Failed to fetch map data:", error);
    } finally {
      setLoading(false);
    }
  };

  // Calculate center from data or use default
  const getCenter = () => {
    if (viewMode === "shops" && shops.length > 0) {
      const lat = shops.reduce((sum, s) => sum + s.latitude, 0) / shops.length;
      const lng = shops.reduce((sum, s) => sum + s.longitude, 0) / shops.length;
      return [lat, lng];
    }
    if (viewMode === "receipts" && receipts.length > 0) {
      const lat = receipts.reduce((sum, r) => sum + r.upload_latitude, 0) / receipts.length;
      const lng = receipts.reduce((sum, r) => sum + r.upload_longitude, 0) / receipts.length;
      return [lat, lng];
    }
    return [39.8283, -98.5795]; // Center of USA
  };

  return (
    <div className="min-h-screen" data-testid="map-view">
      {/* Header */}
      <div className="p-6 pt-8 pb-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
            <div>
              <h1 className="font-heading text-3xl font-bold tracking-tight mb-2">Activity Map</h1>
              <p className="text-muted-foreground">Visualize shops and customer activity</p>
            </div>
            
            <Select value={viewMode} onValueChange={setViewMode}>
              <SelectTrigger className="w-[180px] glass border-white/10" data-testid="view-mode-select">
                <SelectValue placeholder="View mode" />
              </SelectTrigger>
              <SelectContent className="glass border-white/10">
                <SelectItem value="shops">
                  <div className="flex items-center gap-2">
                    <Store className="w-4 h-4 text-primary" />
                    Shops
                  </div>
                </SelectItem>
                <SelectItem value="receipts">
                  <div className="flex items-center gap-2">
                    <Receipt className="w-4 h-4 text-secondary" />
                    Receipts
                  </div>
                </SelectItem>
                <SelectItem value="both">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-accent" />
                    All Activity
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <Card className="stat-card-purple rounded-2xl">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                  <Store className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <p className="font-mono text-2xl font-bold">{stats.total_shops}</p>
                  <p className="text-xs text-muted-foreground">Shops Tracked</p>
                </div>
              </CardContent>
            </Card>
            <Card className="stat-card-green rounded-2xl">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-secondary/20 flex items-center justify-center">
                  <MapPin className="w-6 h-6 text-secondary" />
                </div>
                <div>
                  <p className="font-mono text-2xl font-bold">{stats.total_receipts}</p>
                  <p className="text-xs text-muted-foreground">Upload Locations</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Map Container */}
      <div className="px-6 pb-24">
        <div className="max-w-6xl mx-auto">
          <Card className="glass-card overflow-hidden rounded-2xl">
            <div className="h-[500px] relative" data-testid="map-container">
              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-card">
                  <div className="text-center">
                    <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-muted-foreground">Loading map data...</p>
                  </div>
                </div>
              ) : (
                <MapContainer
                  center={getCenter()}
                  zoom={4}
                  style={{ height: "100%", width: "100%" }}
                  className="rounded-2xl"
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  
                  {/* Shop Markers */}
                  {(viewMode === "shops" || viewMode === "both") && shops.map((shop) => (
                    <Marker
                      key={shop.id}
                      position={[shop.latitude, shop.longitude]}
                      icon={shopIcon}
                    >
                      <Popup className="custom-popup">
                        <div className="p-2 min-w-[200px]">
                          <div className="flex items-center gap-2 mb-2">
                            <Store className="w-4 h-4 text-primary" />
                            <span className="font-semibold">{shop.name}</span>
                          </div>
                          {shop.address && (
                            <p className="text-xs text-muted-foreground mb-2">{shop.address}</p>
                          )}
                          <div className="flex justify-between text-xs">
                            <span>Receipts: {shop.receipt_count}</span>
                            <span className="font-mono">R{shop.total_sales?.toFixed(2)}</span>
                          </div>
                        </div>
                      </Popup>
                    </Marker>
                  ))}

                  {/* Receipt Markers */}
                  {(viewMode === "receipts" || viewMode === "both") && receipts.map((receipt) => (
                    <CircleMarker
                      key={receipt.id}
                      center={[receipt.upload_latitude, receipt.upload_longitude]}
                      radius={8}
                      pathOptions={{
                        fillColor: "#00ff80",
                        fillOpacity: 0.7,
                        color: "#00cc66",
                        weight: 2
                      }}
                    >
                      <Popup>
                        <div className="p-2 min-w-[180px]">
                          <div className="flex items-center gap-2 mb-2">
                            <Receipt className="w-4 h-4 text-secondary" />
                            <span className="font-semibold">{receipt.shop_name || "Receipt"}</span>
                          </div>
                          <div className="flex justify-between text-xs mb-1">
                            <span>Amount:</span>
                            <span className="font-mono font-bold">R{receipt.amount?.toFixed(2)}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {new Date(receipt.created_at).toLocaleString()}
                          </p>
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
              )}
            </div>
          </Card>

          {/* Legend */}
          <div className="mt-4 flex flex-wrap gap-4 justify-center">
            {(viewMode === "shops" || viewMode === "both") && (
              <div className="flex items-center gap-2 glass px-4 py-2 rounded-full">
                <div className="w-4 h-4 rounded-full bg-primary" />
                <span className="text-sm">Shops</span>
              </div>
            )}
            {(viewMode === "receipts" || viewMode === "both") && (
              <div className="flex items-center gap-2 glass px-4 py-2 rounded-full">
                <div className="w-4 h-4 rounded-full bg-secondary" />
                <span className="text-sm">Receipt Uploads</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
