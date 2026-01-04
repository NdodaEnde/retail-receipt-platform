import { useState, useEffect } from "react";
import { motion } from "framer-motion";
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
  Store, Phone, Clock, TrendingUp, Eye, Navigation
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "../App";

export default function FraudDetection() {
  const [stats, setStats] = useState(null);
  const [flaggedReceipts, setFlaggedReceipts] = useState([]);
  const [thresholds, setThresholds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);

  useEffect(() => {
    fetchFraudData();
  }, []);

  const fetchFraudData = async () => {
    setLoading(true);
    try {
      const [statsRes, flaggedRes, thresholdsRes] = await Promise.all([
        axios.get(`${API}/fraud/stats`),
        axios.get(`${API}/fraud/flagged`),
        axios.get(`${API}/fraud/thresholds`)
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

  const handleReview = async (action) => {
    if (!selectedReceipt) return;
    
    try {
      await axios.post(`${API}/fraud/review/${selectedReceipt.id}?action=${action}&reason=${encodeURIComponent(reviewReason)}`);
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
          <p className="text-muted-foreground">Loading fraud detection data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 pt-8" data-testid="fraud-detection">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-red-500/20 flex items-center justify-center">
            <Shield className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight">Fraud Detection</h1>
            <p className="text-muted-foreground">Monitor and review suspicious receipts</p>
          </div>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="max-w-6xl mx-auto mb-8">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card className="glass-card rounded-2xl border-green-500/20">
              <CardContent className="p-4">
                <CheckCircle className="w-5 h-5 text-green-500 mb-2" />
                <p className="font-mono text-2xl font-bold text-green-400">{stats.valid}</p>
                <p className="text-xs text-muted-foreground">Valid</p>
              </CardContent>
            </Card>
            <Card className="glass-card rounded-2xl border-yellow-500/20">
              <CardContent className="p-4">
                <Eye className="w-5 h-5 text-yellow-500 mb-2" />
                <p className="font-mono text-2xl font-bold text-yellow-400">{stats.review}</p>
                <p className="text-xs text-muted-foreground">Review</p>
              </CardContent>
            </Card>
            <Card className="glass-card rounded-2xl border-orange-500/20">
              <CardContent className="p-4">
                <AlertTriangle className="w-5 h-5 text-orange-500 mb-2" />
                <p className="font-mono text-2xl font-bold text-orange-400">{stats.suspicious}</p>
                <p className="text-xs text-muted-foreground">Suspicious</p>
              </CardContent>
            </Card>
            <Card className="glass-card rounded-2xl border-red-500/20">
              <CardContent className="p-4">
                <XCircle className="w-5 h-5 text-red-500 mb-2" />
                <p className="font-mono text-2xl font-bold text-red-400">{stats.flagged}</p>
                <p className="text-xs text-muted-foreground">Flagged</p>
              </CardContent>
            </Card>
            <Card className="glass-card rounded-2xl border-primary/20">
              <CardContent className="p-4">
                <TrendingUp className="w-5 h-5 text-primary mb-2" />
                <p className="font-mono text-2xl font-bold">{stats.fraud_rate}%</p>
                <p className="text-xs text-muted-foreground">Fraud Rate</p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Thresholds Info */}
      {thresholds && (
        <div className="max-w-6xl mx-auto mb-8">
          <Card className="glass-card rounded-2xl">
            <CardHeader className="pb-2">
              <CardTitle className="font-heading text-lg flex items-center gap-2">
                <Navigation className="w-5 h-5 text-primary" />
                Distance Thresholds
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <p className="font-semibold text-green-400">Valid</p>
                  <p className="text-muted-foreground">{thresholds.description.valid}</p>
                </div>
                <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <p className="font-semibold text-yellow-400">Review</p>
                  <p className="text-muted-foreground">{thresholds.description.review}</p>
                </div>
                <div className="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
                  <p className="font-semibold text-orange-400">Suspicious</p>
                  <p className="text-muted-foreground">{thresholds.description.suspicious}</p>
                </div>
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <p className="font-semibold text-red-400">Flagged</p>
                  <p className="text-muted-foreground">{thresholds.description.flagged}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Flagged Receipts */}
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
                              ⚠️ {receipt.fraud_reason}
                            </p>
                          )}
                        </div>
                        
                        <div className="flex flex-col items-end gap-2">
                          <p className="font-mono text-xl font-bold text-primary">
                            R{receipt.amount?.toFixed(2)}
                          </p>
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
                    </motion.div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

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
                  <p className="font-mono text-orange-400">{selectedReceipt.distance_km?.toFixed(1)}km</p>
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
