import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import ZoomableImage from "../components/ZoomableImage";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { ScrollArea } from "../components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { 
  AlertTriangle, Shield, CheckCircle, XCircle, MapPin, 
  Store, Phone, Clock, TrendingUp, Eye, Navigation,
  Receipt, Package, Image, FileText, User
} from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

export default function FraudDetection() {
  const [stats, setStats] = useState(null);
  const [flaggedReceipts, setFlaggedReceipts] = useState([]);
  const [thresholds, setThresholds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [receiptDetail, setReceiptDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    fetchFraudData();
  }, []);

  const fetchFraudData = async () => {
    setLoading(true);
    try {
      const [statsRes, flaggedRes, thresholdsRes] = await Promise.all([
        api.get("/fraud/stats"),
        api.get("/fraud/flagged"),
        api.get("/fraud/thresholds")
      ]);
      setStats(statsRes.data);
      setFlaggedReceipts(flaggedRes.data.receipts);
      setThresholds(thresholdsRes.data);
    } catch (error) {
      console.error("Failed to fetch fraud data:", error);
      toast.error("Failed to load fraud data");
    } finally {
      setLoading(false);
    }
  };

  const fetchReceiptDetail = async (receiptId) => {
    setLoadingDetail(true);
    try {
      const response = await api.get(`/receipts/${receiptId}/full`);
      setReceiptDetail(response.data);
      setDetailDialogOpen(true);
    } catch (error) {
      console.error("Failed to fetch receipt details:", error);
      toast.error("Failed to load receipt details");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleReview = async (action) => {
    if (!selectedReceipt) return;
    
    try {
      await api.post(`/fraud/review/${selectedReceipt.id}?action=${action}&reason=${encodeURIComponent(reviewReason)}`);
      toast.success(`Receipt ${action === 'approve' ? 'approved' : 'rejected'} successfully`);
      setReviewDialogOpen(false);
      setSelectedReceipt(null);
      setReviewReason("");
      fetchFraudData();
    } catch (error) {
      toast.error(`Failed to ${action} receipt`);
    }
  };

  const getFraudBadge = (flag) => {
    const styles = {
      valid: "bg-green-500/20 text-green-400 border-green-500/30",
      review: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      suspicious: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      flagged: "bg-red-500/20 text-red-400 border-red-500/30"
    };
    const icons = {
      valid: <CheckCircle className="w-3 h-3 mr-1" />,
      review: <Eye className="w-3 h-3 mr-1" />,
      suspicious: <AlertTriangle className="w-3 h-3 mr-1" />,
      flagged: <XCircle className="w-3 h-3 mr-1" />
    };
    return (
      <Badge className={`${styles[flag]} flex items-center`}>
        {icons[flag]}
        {flag.charAt(0).toUpperCase() + flag.slice(1)}
      </Badge>
    );
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("en-ZA", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading fraud data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6" data-testid="fraud-detection-page">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-red-500/20 flex items-center justify-center">
            <Shield className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-heading font-bold">Fraud Detection</h1>
            <p className="text-muted-foreground text-sm">Monitor and review suspicious receipts</p>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      {stats && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          <Card className="glass-card">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-green-400">{stats.valid_count || 0}</p>
              <p className="text-xs text-muted-foreground">Valid</p>
            </CardContent>
          </Card>
          <Card className="glass-card">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-yellow-400">{stats.review_count || 0}</p>
              <p className="text-xs text-muted-foreground">Review</p>
            </CardContent>
          </Card>
          <Card className="glass-card">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-orange-400">{stats.suspicious_count || 0}</p>
              <p className="text-xs text-muted-foreground">Suspicious</p>
            </CardContent>
          </Card>
          <Card className="glass-card">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-red-400">{stats.flagged_count || 0}</p>
              <p className="text-xs text-muted-foreground">Flagged</p>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Flagged Receipts List */}
      <div className="max-w-6xl mx-auto">
        <Card className="glass-card rounded-2xl">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-500" />
              Receipts Requiring Review ({flaggedReceipts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]" data-testid="flagged-receipts-list">
              <div className="space-y-4">
                {flaggedReceipts.length === 0 ? (
                  <div className="text-center py-12">
                    <Shield className="w-16 h-16 text-green-500 mx-auto mb-4" />
                    <p className="text-lg font-semibold text-green-400">All Clear!</p>
                    <p className="text-muted-foreground">No receipts flagged for review</p>
                  </div>
                ) : (
                  flaggedReceipts.map((receipt, index) => (
                    <motion.div
                      key={receipt.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors border border-white/5"
                    >
                      <div className="flex flex-col md:flex-row justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            {getFraudBadge(receipt.fraud_flag)}
                            <span className="font-mono text-sm text-muted-foreground">
                              Score: {receipt.fraud_score}/100
                            </span>
                            {receipt.has_image && (
                              <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                                <Image className="w-3 h-3 mr-1" />
                                Has Image
                              </Badge>
                            )}
                          </div>
                          
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div className="flex items-center gap-2">
                              <Store className="w-4 h-4 text-primary" />
                              <span>{receipt.shop_name || "Unknown Shop"}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Phone className="w-4 h-4 text-secondary" />
                              <span className="font-mono">{receipt.customer_phone}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <MapPin className="w-4 h-4 text-orange-500" />
                              <span className="font-mono">{receipt.distance_km?.toFixed(1) || '?'}km away</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Clock className="w-4 h-4 text-muted-foreground" />
                              <span>{formatDate(receipt.created_at)}</span>
                            </div>
                          </div>
                          
                          {receipt.fraud_reason && (
                            <p className="mt-2 text-xs text-orange-400 bg-orange-500/10 px-2 py-1 rounded">
                              {receipt.fraud_reason}
                            </p>
                          )}
                        </div>
                        
                        <div className="flex flex-col items-end gap-2">
                          <p className="font-mono text-xl font-bold text-primary">
                            R{receipt.amount?.toFixed(2)}
                          </p>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              data-testid={`view-detail-btn-${receipt.id}`}
                              onClick={() => fetchReceiptDetail(receipt.id)}
                              disabled={loadingDetail}
                              className="rounded-lg"
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              View Details
                            </Button>
                            <Button
                              size="sm"
                              data-testid={`review-btn-${receipt.id}`}
                              onClick={() => {
                                setSelectedReceipt(receipt);
                                setReviewDialogOpen(true);
                              }}
                              className="rounded-lg"
                            >
                              Review
                            </Button>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      {/* Receipt Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="glass border-white/10 max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="detail-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl flex items-center gap-2">
              <Receipt className="w-5 h-5 text-primary" />
              Receipt Details
            </DialogTitle>
          </DialogHeader>
          
          {receiptDetail && (
            <div className="space-y-6 py-4">
              {/* Basic Info */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="p-3 rounded-lg bg-white/5">
                  <p className="text-muted-foreground text-xs mb-1">Shop</p>
                  <p className="font-semibold flex items-center gap-2">
                    <Store className="w-4 h-4 text-primary" />
                    {receiptDetail.receipt?.shop_name}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/5">
                  <p className="text-muted-foreground text-xs mb-1">Amount</p>
                  <p className="font-mono font-bold text-xl text-primary">
                    R{receiptDetail.receipt?.amount?.toFixed(2)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/5">
                  <p className="text-muted-foreground text-xs mb-1">Customer</p>
                  <p className="font-mono flex items-center gap-2">
                    <User className="w-4 h-4 text-secondary" />
                    +{receiptDetail.receipt?.customer_phone}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-white/5">
                  <p className="text-muted-foreground text-xs mb-1">Status</p>
                  {getFraudBadge(receiptDetail.receipt?.fraud_flag || 'review')}
                </div>
              </div>

              {/* Two columns: Image and Items */}
              <div className="grid md:grid-cols-2 gap-6">
                {/* Receipt Image */}
                <div>
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Image className="w-4 h-4 text-primary" />
                    Original Receipt Image
                  </h3>
                  <div className="rounded-xl overflow-hidden border border-white/10 bg-white/5">
                    {(receiptDetail.receipt?.image_url || receiptDetail.receipt?.image_data) ? (
                      <ZoomableImage
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

                {/* Items List */}
                <div>
                  <h3 className="font-semibold mb-3 flex items-center gap-2">
                    <Package className="w-4 h-4 text-primary" />
                    Extracted Items ({receiptDetail.receipt?.items?.length || 0})
                  </h3>
                  <ScrollArea className="h-[400px] rounded-xl border border-white/10 bg-white/5">
                    <div className="p-4 space-y-2">
                      {receiptDetail.receipt?.items?.length > 0 ? (
                        receiptDetail.receipt.items.map((item, index) => (
                          <div 
                            key={index}
                            className="flex justify-between items-center p-2 rounded-lg hover:bg-white/5"
                            data-testid={`item-${index}`}
                          >
                            <div className="flex-1">
                              <p className="text-sm font-medium">{item.name}</p>
                              {item.quantity > 1 && (
                                <p className="text-xs text-muted-foreground">Qty: {item.quantity}</p>
                              )}
                            </div>
                            <p className="font-mono text-primary">R{item.price?.toFixed(2)}</p>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8 text-muted-foreground">
                          <Package className="w-8 h-8 mx-auto mb-2 opacity-50" />
                          <p>No items extracted</p>
                        </div>
                      )}
                      
                      {/* Total */}
                      {receiptDetail.receipt?.items?.length > 0 && (
                        <div className="border-t border-white/10 pt-3 mt-3">
                          <div className="flex justify-between items-center font-semibold">
                            <span>Total</span>
                            <span className="font-mono text-lg text-primary">
                              R{receiptDetail.receipt?.amount?.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </div>

              {/* Additional Details */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* Location Info */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-orange-500" />
                    Location Data
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Shop Address</span>
                      <span className="text-right max-w-[200px]">{receiptDetail.receipt?.shop_address || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Upload Location</span>
                      <span className="font-mono">
                        {receiptDetail.receipt?.upload_latitude?.toFixed(4)}, {receiptDetail.receipt?.upload_longitude?.toFixed(4)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Distance</span>
                      <span className="font-mono text-orange-400">
                        {receiptDetail.receipt?.distance_km?.toFixed(1) || '?'} km
                      </span>
                    </div>
                  </div>
                </div>

                {/* Fraud Info */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-red-500" />
                    Fraud Analysis
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Fraud Score</span>
                      <span className="font-mono">{receiptDetail.receipt?.fraud_score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status</span>
                      {getFraudBadge(receiptDetail.receipt?.fraud_flag || 'review')}
                    </div>
                    {receiptDetail.receipt?.fraud_reason && (
                      <div className="mt-2 p-2 rounded bg-orange-500/10 text-orange-400 text-xs">
                        {receiptDetail.receipt.fraud_reason}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Customer Info */}
              {receiptDetail.customer && (
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <h4 className="font-semibold mb-3 flex items-center gap-2">
                    <User className="w-4 h-4 text-secondary" />
                    Customer Profile
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs">Phone</p>
                      <p className="font-mono">+{receiptDetail.customer.phone_number}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Total Receipts</p>
                      <p className="font-semibold">{receiptDetail.customer.total_receipts}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Total Spent</p>
                      <p className="font-mono text-primary">R{receiptDetail.customer.total_spent?.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Total Wins</p>
                      <p className="font-semibold text-yellow-400">{receiptDetail.customer.total_wins}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDetailDialogOpen(false)}
            >
              Close
            </Button>
            <Button
              onClick={() => {
                setDetailDialogOpen(false);
                setSelectedReceipt(receiptDetail?.receipt);
                setReviewDialogOpen(true);
              }}
            >
              Review This Receipt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Review Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={setReviewDialogOpen}>
        <DialogContent className="glass border-white/10" data-testid="review-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-xl">Review Receipt</DialogTitle>
          </DialogHeader>
          
          {selectedReceipt && (
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Shop</p>
                  <p className="font-semibold">{selectedReceipt.shop_name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Amount</p>
                  <p className="font-mono font-bold text-primary">R{selectedReceipt.amount?.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Customer</p>
                  <p className="font-mono">{selectedReceipt.customer_phone}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Distance</p>
                  <p className="font-mono text-orange-400">{selectedReceipt.distance_km?.toFixed(1) || '?'}km</p>
                </div>
              </div>
              
              <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
                <p className="text-sm text-orange-400">{selectedReceipt.fraud_reason}</p>
              </div>
              
              <div>
                <Label htmlFor="reason" className="text-xs uppercase tracking-widest text-muted-foreground">
                  Review Notes (Optional)
                </Label>
                <Input
                  id="reason"
                  data-testid="review-reason-input"
                  placeholder="Add notes about your decision..."
                  value={reviewReason}
                  onChange={(e) => setReviewReason(e.target.value)}
                  className="mt-2 bg-white/5 border-white/10"
                />
              </div>
            </div>
          )}
          
          <DialogFooter className="flex gap-2">
            <Button
              variant="outline"
              data-testid="reject-btn"
              onClick={() => handleReview("reject")}
              className="flex-1 border-red-500/30 text-red-400 hover:bg-red-500/10"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Reject
            </Button>
            <Button
              data-testid="approve-btn"
              onClick={() => handleReview("approve")}
              className="flex-1 bg-green-600 hover:bg-green-700"
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
