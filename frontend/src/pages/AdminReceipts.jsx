import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  Receipt, MapPin, Clock, DollarSign, Store, Eye, Image,
  Package, User, Shield, ChevronLeft, ChevronRight, Filter
} from "lucide-react";
import axios from "axios";
import { API } from "../App";

const fraudColors = {
  valid: "bg-green-500/20 text-green-400 border-green-500/30",
  review: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  suspicious: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  flagged: "bg-red-500/20 text-red-400 border-red-500/30",
};

const statusColors = {
  processed: "bg-green-500/20 text-green-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  review: "bg-orange-500/20 text-orange-400",
  won: "bg-violet-500/20 text-violet-400",
  rejected: "bg-red-500/20 text-red-400",
};

export default function AdminReceipts() {
  const [receipts, setReceipts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("all"); // all, valid, review, flagged
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [receiptDetail, setReceiptDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pageSize = 20;

  const fetchReceipts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip: page * pageSize, limit: pageSize };
      if (filter !== "all") params.fraud_flag = filter;
      const res = await axios.get(`${API}/receipts`, { params });
      setReceipts(res.data.receipts || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error("Failed to fetch receipts:", err);
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => { fetchReceipts(); }, [fetchReceipts]);

  const openDetail = async (receipt) => {
    setSelectedReceipt(receipt);
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API}/receipts/${receipt.id}/full`);
      setReceiptDetail(res.data);
    } catch (err) {
      console.error("Failed to fetch receipt detail:", err);
    } finally {
      setDetailLoading(false);
    }
  };

  const formatDate = (d) => {
    if (!d) return "N/A";
    return new Date(d).toLocaleString("en-ZA", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
  };

  const formatPhone = (p) => {
    if (!p) return "N/A";
    if (p.length === 11) return `+${p.slice(0,2)} ${p.slice(2,5)} ${p.slice(5,8)} ${p.slice(8)}`;
    return p;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Receipt className="w-6 h-6 text-primary" />
              All Receipts
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              {total} total receipts
            </p>
          </div>

          {/* Filter */}
          <div className="flex gap-2">
            {["all", "valid", "review", "flagged"].map((f) => (
              <Button
                key={f}
                variant={filter === f ? "default" : "outline"}
                size="sm"
                onClick={() => { setFilter(f); setPage(0); }}
                className="capitalize"
              >
                {f === "all" ? "All" : f}
              </Button>
            ))}
          </div>
        </div>

        {/* Receipts Table */}
        <Card className="glass border-white/10">
          <CardContent className="p-0">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground">Loading...</div>
            ) : receipts.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No receipts found</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-muted-foreground">
                      <th className="p-3">Date</th>
                      <th className="p-3">Shop</th>
                      <th className="p-3">Amount</th>
                      <th className="p-3">Customer</th>
                      <th className="p-3">Distance</th>
                      <th className="p-3">Fraud</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Image</th>
                      <th className="p-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipts.map((r) => (
                      <tr key={r.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="p-3 text-xs">{formatDate(r.created_at)}</td>
                        <td className="p-3 font-medium">{r.shop_name || "Unknown"}</td>
                        <td className="p-3 text-green-400 font-mono">R{(r.amount || 0).toFixed(2)}</td>
                        <td className="p-3 text-xs font-mono">{formatPhone(r.customer_phone)}</td>
                        <td className="p-3">
                          {r.distance_km != null ? (
                            <span className={r.distance_km < 50 ? "text-green-400" : r.distance_km < 100 ? "text-yellow-400" : "text-red-400"}>
                              {r.distance_km.toFixed(1)} km
                            </span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="p-3">
                          <Badge variant="outline" className={`text-xs ${fraudColors[r.fraud_flag] || ""}`}>
                            {r.fraud_flag || "N/A"}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Badge className={`text-xs ${statusColors[r.status] || ""}`}>
                            {r.status || "N/A"}
                          </Badge>
                        </td>
                        <td className="p-3">
                          {r.has_image ? (
                            <Image className="w-4 h-4 text-green-400" />
                          ) : (
                            <Image className="w-4 h-4 text-muted-foreground opacity-30" />
                          )}
                        </td>
                        <td className="p-3">
                          <Button variant="ghost" size="sm" onClick={() => openDetail(r)}>
                            <Eye className="w-4 h-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            <div className="flex items-center justify-between p-3 border-t border-white/10">
              <span className="text-xs text-muted-foreground">
                Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= total} onClick={() => setPage(p => p + 1)}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Detail Dialog */}
        <Dialog open={!!selectedReceipt} onOpenChange={(open) => { if (!open) { setSelectedReceipt(null); setReceiptDetail(null); } }}>
          <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto glass border-white/10">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Store className="w-5 h-5 text-primary" />
                {selectedReceipt?.shop_name || "Receipt Detail"}
              </DialogTitle>
            </DialogHeader>

            {detailLoading ? (
              <div className="p-8 text-center text-muted-foreground">Loading details...</div>
            ) : receiptDetail ? (
              <div className="space-y-6">
                {/* Summary Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="text-xs text-muted-foreground flex items-center gap-1"><Store className="w-3 h-3" /> Shop</div>
                    <div className="font-semibold mt-1 text-sm">{receiptDetail.receipt?.shop_name || "Unknown"}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="text-xs text-muted-foreground flex items-center gap-1"><DollarSign className="w-3 h-3" /> Amount</div>
                    <div className="font-semibold mt-1 text-sm text-green-400">R{(receiptDetail.receipt?.amount || 0).toFixed(2)}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" /> Date</div>
                    <div className="font-semibold mt-1 text-sm">{formatDate(receiptDetail.receipt?.created_at)}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="text-xs text-muted-foreground flex items-center gap-1"><Shield className="w-3 h-3" /> Fraud</div>
                    <div className="mt-1">
                      <Badge variant="outline" className={`text-xs ${fraudColors[receiptDetail.receipt?.fraud_flag] || ""}`}>
                        {receiptDetail.receipt?.fraud_flag || "N/A"}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Customer Info */}
                <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
                    <User className="w-4 h-4 text-primary" /> Customer
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div><span className="text-muted-foreground">Phone:</span> {formatPhone(receiptDetail.receipt?.customer_phone)}</div>
                    <div><span className="text-muted-foreground">Name:</span> {receiptDetail.customer?.name || "Unknown"}</div>
                    <div><span className="text-muted-foreground">Total Receipts:</span> {receiptDetail.customer?.total_receipts || 0}</div>
                    <div><span className="text-muted-foreground">Total Spent:</span> R{(receiptDetail.customer?.total_spent || 0).toFixed(2)}</div>
                  </div>
                </div>

                {/* Image + Items side by side */}
                <div className="grid md:grid-cols-2 gap-4">
                  {/* Receipt Image */}
                  <div>
                    <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
                      <Image className="w-4 h-4 text-primary" /> Receipt Image
                    </h3>
                    <div className="rounded-xl overflow-hidden border border-white/10 bg-white/5">
                      {(receiptDetail.receipt?.image_url || receiptDetail.receipt?.image_data) ? (
                        <img
                          src={receiptDetail.receipt.image_url || `data:image/jpeg;base64,${receiptDetail.receipt.image_data}`}
                          alt="Receipt"
                          className="w-full max-h-[400px] object-contain"
                        />
                      ) : (
                        <div className="p-8 text-center text-muted-foreground">
                          <Image className="w-12 h-12 mx-auto mb-2 opacity-50" />
                          <p>No image available</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Items */}
                  <div>
                    <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
                      <Package className="w-4 h-4 text-primary" />
                      Items ({(receiptDetail.receipt?.items || []).length})
                    </h3>
                    <ScrollArea className="h-[400px] rounded-xl border border-white/10 bg-white/5">
                      <div className="p-3 space-y-2">
                        {(receiptDetail.receipt?.items || []).length > 0 ? (
                          <>
                            {receiptDetail.receipt.items.map((item, i) => (
                              <div key={i} className="flex justify-between items-center py-2 px-3 rounded-lg bg-white/5 text-sm">
                                <div className="flex-1">
                                  <span>{item.name || item.description || `Item ${i + 1}`}</span>
                                  {item.quantity > 1 && (
                                    <span className="text-muted-foreground ml-2">x{item.quantity}</span>
                                  )}
                                </div>
                                <span className="font-mono text-green-400">
                                  R{(item.price || item.total_price || 0).toFixed(2)}
                                </span>
                              </div>
                            ))}
                            <div className="flex justify-between items-center py-2 px-3 rounded-lg bg-primary/10 border border-primary/20 font-semibold text-sm">
                              <span>Total</span>
                              <span className="text-green-400">R{(receiptDetail.receipt.amount || 0).toFixed(2)}</span>
                            </div>
                          </>
                        ) : (
                          <div className="p-4 text-center text-muted-foreground">No items extracted</div>
                        )}
                      </div>
                    </ScrollArea>
                  </div>
                </div>

                {/* Location & Distance */}
                <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
                    <MapPin className="w-4 h-4 text-primary" /> Location & Distance
                  </h3>
                  <div className="grid md:grid-cols-3 gap-4 text-sm">
                    {/* Consumer Location */}
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Consumer Location</div>
                      {receiptDetail.receipt?.upload_latitude ? (
                        <>
                          <div className="font-mono text-xs">
                            {receiptDetail.receipt.upload_latitude.toFixed(4)}, {receiptDetail.receipt.upload_longitude.toFixed(4)}
                          </div>
                          {receiptDetail.receipt.upload_address && (
                            <div className="text-muted-foreground text-xs mt-1">{receiptDetail.receipt.upload_address}</div>
                          )}
                        </>
                      ) : (
                        <div className="text-muted-foreground">Not provided</div>
                      )}
                    </div>

                    {/* Shop Location */}
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Shop Location</div>
                      {receiptDetail.receipt?.shop_latitude ? (
                        <>
                          <div className="font-mono text-xs">
                            {receiptDetail.receipt.shop_latitude.toFixed(4)}, {receiptDetail.receipt.shop_longitude.toFixed(4)}
                          </div>
                          {receiptDetail.receipt.shop_address && (
                            <div className="text-muted-foreground text-xs mt-1">{receiptDetail.receipt.shop_address}</div>
                          )}
                        </>
                      ) : (
                        <div className="text-muted-foreground">Not geocoded</div>
                      )}
                    </div>

                    {/* Distance */}
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Distance</div>
                      {receiptDetail.receipt?.distance_km != null ? (
                        <div className={`text-lg font-bold ${
                          receiptDetail.receipt.distance_km < 50 ? "text-green-400" :
                          receiptDetail.receipt.distance_km < 100 ? "text-yellow-400" :
                          "text-red-400"
                        }`}>
                          {receiptDetail.receipt.distance_km.toFixed(1)} km
                        </div>
                      ) : (
                        <div className="text-muted-foreground">N/A</div>
                      )}
                      {receiptDetail.receipt?.fraud_reason && (
                        <div className="text-xs text-orange-400 mt-1">{receiptDetail.receipt.fraud_reason}</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Fraud Details */}
                {receiptDetail.receipt?.fraud_score != null && (
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
                      <Shield className="w-4 h-4 text-primary" /> Fraud Analysis
                    </h3>
                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <span className="text-muted-foreground">Score:</span>{" "}
                        <span className="font-mono">{receiptDetail.receipt.fraud_score}/100</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Flag:</span>{" "}
                        <Badge variant="outline" className={`text-xs ${fraudColors[receiptDetail.receipt.fraud_flag] || ""}`}>
                          {receiptDetail.receipt.fraud_flag}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Status:</span>{" "}
                        <Badge className={`text-xs ${statusColors[receiptDetail.receipt.status] || ""}`}>
                          {receiptDetail.receipt.status}
                        </Badge>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </motion.div>
    </div>
  );
}
