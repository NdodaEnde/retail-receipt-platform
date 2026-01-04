import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { ScrollArea } from "../components/ui/scroll-area";
import { Receipt, Upload, Trophy, MapPin, Clock, DollarSign, Store, Plus, Phone } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "../App";

export default function CustomerDashboard() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [customer, setCustomer] = useState(null);
  const [receipts, setReceipts] = useState([]);
  const [wins, setWins] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  // Upload form state
  const [uploadData, setUploadData] = useState({
    shop_name: "",
    amount: "",
    receipt_text: ""
  });
  const [userLocation, setUserLocation] = useState(null);

  // Get user location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          });
        },
        (error) => console.log("Location not available:", error)
      );
    }
  }, []);

  const fetchCustomerData = useCallback(async () => {
    if (!phoneNumber) return;
    
    setLoading(true);
    try {
      // Get or create customer
      const customerRes = await axios.post(`${API}/customers`, { phone_number: phoneNumber });
      setCustomer(customerRes.data);
      
      // Get receipts
      const receiptsRes = await axios.get(`${API}/receipts/customer/${phoneNumber}`);
      setReceipts(receiptsRes.data.receipts);
      
      // Get wins
      const winsRes = await axios.get(`${API}/draws/winner/${phoneNumber}`);
      setWins(winsRes.data.wins);
      
    } catch (error) {
      toast.error("Failed to load customer data");
    } finally {
      setLoading(false);
    }
  }, [phoneNumber]);

  const handleUploadReceipt = async () => {
    if (!phoneNumber || !uploadData.amount) {
      toast.error("Please enter phone number and amount");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("phone_number", phoneNumber);
      formData.append("shop_name", uploadData.shop_name);
      formData.append("amount", parseFloat(uploadData.amount));
      formData.append("receipt_text", uploadData.receipt_text);
      
      if (userLocation) {
        formData.append("latitude", userLocation.latitude);
        formData.append("longitude", userLocation.longitude);
      }

      await axios.post(`${API}/receipts/upload`, formData);
      toast.success("Receipt uploaded successfully!");
      setUploadOpen(false);
      setUploadData({ shop_name: "", amount: "", receipt_text: "" });
      fetchCustomerData();
    } catch (error) {
      toast.error("Failed to upload receipt");
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  return (
    <div className="min-h-screen p-6 pt-8" data-testid="customer-dashboard">
      {/* Header */}
      <div className="max-w-4xl mx-auto mb-8">
        <h1 className="font-heading text-3xl font-bold tracking-tight mb-2">My Receipts</h1>
        <p className="text-muted-foreground">Track your uploads and winnings</p>
      </div>

      {/* Phone Input */}
      <div className="max-w-4xl mx-auto mb-8">
        <Card className="glass-card">
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <Label htmlFor="phone" className="text-xs uppercase tracking-widest text-muted-foreground mb-2 block">
                  Phone Number
                </Label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="phone"
                    data-testid="phone-input"
                    placeholder="+1234567890"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="pl-10 bg-white/5 border-white/10 h-12"
                  />
                </div>
              </div>
              <div className="flex gap-2 items-end">
                <Button 
                  data-testid="load-data-btn"
                  onClick={fetchCustomerData} 
                  disabled={!phoneNumber || loading}
                  className="h-12 px-6 rounded-xl glow-primary"
                >
                  {loading ? "Loading..." : "Load Data"}
                </Button>
                
                <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
                  <DialogTrigger asChild>
                    <Button 
                      data-testid="upload-receipt-btn"
                      variant="outline" 
                      disabled={!phoneNumber}
                      className="h-12 px-6 rounded-xl border-white/20"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Upload Receipt
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="glass border-white/10" data-testid="upload-dialog">
                    <DialogHeader>
                      <DialogTitle className="font-heading text-xl">Upload Receipt</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div>
                        <Label htmlFor="shop" className="text-xs uppercase tracking-widest text-muted-foreground">
                          Shop Name
                        </Label>
                        <Input
                          id="shop"
                          data-testid="shop-name-input"
                          placeholder="e.g., Walmart, Target..."
                          value={uploadData.shop_name}
                          onChange={(e) => setUploadData({ ...uploadData, shop_name: e.target.value })}
                          className="mt-2 bg-white/5 border-white/10"
                        />
                      </div>
                      <div>
                        <Label htmlFor="amount" className="text-xs uppercase tracking-widest text-muted-foreground">
                          Total Amount
                        </Label>
                        <Input
                          id="amount"
                          data-testid="amount-input"
                          type="number"
                          step="0.01"
                          placeholder="0.00"
                          value={uploadData.amount}
                          onChange={(e) => setUploadData({ ...uploadData, amount: e.target.value })}
                          className="mt-2 bg-white/5 border-white/10"
                        />
                      </div>
                      <div>
                        <Label htmlFor="text" className="text-xs uppercase tracking-widest text-muted-foreground">
                          Receipt Text (Optional)
                        </Label>
                        <textarea
                          id="text"
                          data-testid="receipt-text-input"
                          placeholder="Paste or type receipt content..."
                          value={uploadData.receipt_text}
                          onChange={(e) => setUploadData({ ...uploadData, receipt_text: e.target.value })}
                          className="mt-2 w-full h-24 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm resize-none focus:outline-none focus:border-primary/50"
                        />
                      </div>
                      {userLocation && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <MapPin className="w-4 h-4 text-secondary" />
                          <span>Location: {userLocation.latitude.toFixed(4)}, {userLocation.longitude.toFixed(4)}</span>
                        </div>
                      )}
                      <Button 
                        data-testid="submit-upload-btn"
                        onClick={handleUploadReceipt} 
                        className="w-full h-12 rounded-xl glow-primary"
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Upload Receipt
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Customer Stats */}
      {customer && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-4xl mx-auto mb-8"
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="stat-card-purple rounded-2xl">
              <CardContent className="p-4">
                <Receipt className="w-5 h-5 text-primary mb-2" />
                <p className="font-mono text-2xl font-bold">{customer.total_receipts}</p>
                <p className="text-xs text-muted-foreground">Receipts</p>
              </CardContent>
            </Card>
            <Card className="stat-card-green rounded-2xl">
              <CardContent className="p-4">
                <DollarSign className="w-5 h-5 text-secondary mb-2" />
                <p className="font-mono text-2xl font-bold">R{customer.total_spent?.toFixed(2) || '0.00'}</p>
                <p className="text-xs text-muted-foreground">Total Spent</p>
              </CardContent>
            </Card>
            <Card className="stat-card-pink rounded-2xl">
              <CardContent className="p-4">
                <Trophy className="w-5 h-5 text-accent mb-2" />
                <p className="font-mono text-2xl font-bold">{customer.total_wins}</p>
                <p className="text-xs text-muted-foreground">Wins</p>
              </CardContent>
            </Card>
            <Card className="stat-card-cyan rounded-2xl">
              <CardContent className="p-4">
                <DollarSign className="w-5 h-5 text-cyan-400 mb-2" />
                <p className="font-mono text-2xl font-bold">R{customer.total_winnings?.toFixed(2) || '0.00'}</p>
                <p className="text-xs text-muted-foreground">Won Back</p>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}

      {/* Tabs */}
      {customer && (
        <div className="max-w-4xl mx-auto">
          <Tabs defaultValue="receipts" className="w-full">
            <TabsList className="w-full glass border-white/10 p-1 rounded-xl mb-6">
              <TabsTrigger 
                value="receipts" 
                data-testid="receipts-tab"
                className="flex-1 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              >
                <Receipt className="w-4 h-4 mr-2" />
                Receipts ({receipts.length})
              </TabsTrigger>
              <TabsTrigger 
                value="wins" 
                data-testid="wins-tab"
                className="flex-1 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              >
                <Trophy className="w-4 h-4 mr-2" />
                Wins ({wins.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="receipts" data-testid="receipts-list">
              <ScrollArea className="h-[400px]">
                <div className="space-y-4">
                  {receipts.length === 0 ? (
                    <Card className="glass-card">
                      <CardContent className="p-8 text-center">
                        <Receipt className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">No receipts yet. Upload your first receipt!</p>
                      </CardContent>
                    </Card>
                  ) : (
                    receipts.map((receipt, index) => (
                      <motion.div
                        key={receipt.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <Card className="receipt-card relative overflow-hidden rounded-2xl">
                          <CardContent className="p-4 pt-6">
                            <div className="flex justify-between items-start mb-3">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                  <Store className="w-5 h-5 text-primary" />
                                </div>
                                <div>
                                  <p className="font-semibold">{receipt.shop_name || "Unknown Shop"}</p>
                                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {formatDate(receipt.created_at)}
                                  </p>
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="font-mono text-xl font-bold text-primary">R{receipt.amount?.toFixed(2)}</p>
                                <Badge 
                                  variant={receipt.status === 'won' ? 'default' : 'secondary'}
                                  className={receipt.status === 'won' ? 'bg-secondary text-secondary-foreground' : ''}
                                >
                                  {receipt.status === 'won' ? '🏆 Winner!' : receipt.status}
                                </Badge>
                              </div>
                            </div>
                            {receipt.upload_latitude && (
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <MapPin className="w-3 h-3" />
                                <span className="font-mono">
                                  {receipt.upload_latitude.toFixed(4)}, {receipt.upload_longitude.toFixed(4)}
                                </span>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="wins" data-testid="wins-list">
              <ScrollArea className="h-[400px]">
                <div className="space-y-4">
                  {wins.length === 0 ? (
                    <Card className="glass-card">
                      <CardContent className="p-8 text-center">
                        <Trophy className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">No wins yet. Keep uploading receipts!</p>
                      </CardContent>
                    </Card>
                  ) : (
                    wins.map((win, index) => (
                      <motion.div
                        key={win.id}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.1 }}
                      >
                        <Card className="stat-card-green rounded-2xl overflow-hidden">
                          <CardContent className="p-6">
                            <div className="flex justify-between items-center">
                              <div className="flex items-center gap-4">
                                <div className="w-12 h-12 rounded-full bg-secondary/20 flex items-center justify-center">
                                  <Trophy className="w-6 h-6 text-secondary" />
                                </div>
                                <div>
                                  <p className="font-semibold">Daily Draw Winner!</p>
                                  <p className="text-sm text-muted-foreground">{win.draw_date}</p>
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="font-mono text-2xl font-bold text-secondary">
                                  ${win.prize_amount?.toFixed(2)}
                                </p>
                                <p className="text-xs text-muted-foreground">Won Back</p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
