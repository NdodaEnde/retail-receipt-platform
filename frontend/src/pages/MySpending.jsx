import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  DollarSign, TrendingUp, TrendingDown, Store, Calendar,
  Phone, Search, Receipt, Download, Eye, Clock, BarChart3, PieChart
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart as RechartsPie, Pie, Cell, AreaChart, Area
} from "recharts";
import axios from "axios";
import { toast } from "sonner";
import { API } from "../App";

const COLORS = [
  'hsl(265, 89%, 66%)', 'hsl(150, 100%, 50%)', 'hsl(300, 100%, 50%)',
  'hsl(190, 100%, 50%)', 'hsl(40, 100%, 50%)', 'hsl(0, 100%, 65%)',
  'hsl(220, 90%, 60%)', 'hsl(330, 80%, 60%)'
];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatMonth(monthStr) {
  if (!monthStr || monthStr.length < 7) return monthStr;
  const [year, month] = monthStr.split('-');
  return `${MONTHS[parseInt(month, 10) - 1]} ${year}`;
}

export default function MySpending() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [receipts, setReceipts] = useState([]);
  const [searchShop, setSearchShop] = useState("");
  const [receiptDetail, setReceiptDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const formatPhoneNumber = (num) => {
    let cleaned = num.replace(/\D/g, "");
    if (cleaned.startsWith("0")) cleaned = "27" + cleaned.substring(1);
    if (cleaned.length === 9 && !cleaned.startsWith("27")) cleaned = "27" + cleaned;
    return cleaned;
  };

  const fetchData = useCallback(async () => {
    if (!phoneNumber) return;
    const formatted = formatPhoneNumber(phoneNumber);
    setLoading(true);
    try {
      const [spendRes, receiptsRes] = await Promise.all([
        axios.get(`${API}/customers/${formatted}/spending`),
        axios.get(`${API}/receipts/customer/${formatted}?limit=200`),
      ]);
      setData(spendRes.data);
      setReceipts(receiptsRes.data.receipts || []);
    } catch (err) {
      toast.error("Could not load spending data");
    } finally {
      setLoading(false);
    }
  }, [phoneNumber]);

  const viewReceipt = async (id) => {
    try {
      const res = await axios.get(`${API}/receipts/${id}/full`);
      setReceiptDetail(res.data);
      setDetailOpen(true);
    } catch {
      toast.error("Failed to load receipt");
    }
  };

  const filteredReceipts = searchShop
    ? receipts.filter(r => r.shop_name?.toLowerCase().includes(searchShop.toLowerCase()))
    : receipts;

  const summary = data?.summary || {};
  const monthly = (data?.monthly || []).slice().reverse();
  const shops = data?.shops || [];

  // Prepare pie chart data from shops
  const pieData = shops.slice(0, 8).map(s => ({
    name: s.shop_name,
    value: parseFloat(s.total_spent || 0)
  }));
  const otherShops = shops.slice(8);
  if (otherShops.length > 0) {
    pieData.push({
      name: 'Other',
      value: otherShops.reduce((sum, s) => sum + parseFloat(s.total_spent || 0), 0)
    });
  }

  // Format monthly for bar chart
  const monthlyChart = monthly.map(m => ({
    month: formatMonth(m.month),
    spent: parseFloat(m.total_spent || 0),
    receipts: parseInt(m.receipt_count || 0, 10),
  }));

  const thisMonthSpent = parseFloat(summary.this_month_spent || 0);
  const avgReceipt = parseFloat(summary.avg_receipt || 0);
  const totalSpent = parseFloat(summary.total_spent || 0);
  const thisYearSpent = parseFloat(summary.this_year_spent || 0);

  return (
    <div className="min-h-screen p-4 pt-8 max-w-5xl mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-heading text-3xl font-bold tracking-tight flex items-center gap-2">
          <BarChart3 className="w-7 h-7 text-primary" />
          My Spending
        </h1>
        <p className="text-muted-foreground mt-1">See where your money goes and find past receipts</p>
      </motion.div>

      {/* Phone Input */}
      <Card className="glass border-white/10">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <Label className="text-xs uppercase tracking-widest text-muted-foreground mb-1 block">Phone Number</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="e.g. 0761234567"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchData()}
                  className="pl-10 bg-white/5 border-white/10 h-11"
                />
              </div>
            </div>
            <Button
              onClick={fetchData}
              disabled={!phoneNumber || loading}
              className="h-11 px-6 self-end glow-primary"
            >
              {loading ? "Loading..." : "View Spending"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {data && (
        <>
          {/* Summary Cards */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card className="glass border-white/10">
                <CardContent className="p-4">
                  <DollarSign className="w-5 h-5 text-primary mb-1" />
                  <p className="font-mono text-2xl font-bold">R{totalSpent.toFixed(0)}</p>
                  <p className="text-xs text-muted-foreground">All-Time Spend</p>
                </CardContent>
              </Card>
              <Card className="glass border-white/10">
                <CardContent className="p-4">
                  <Calendar className="w-5 h-5 text-green-400 mb-1" />
                  <p className="font-mono text-2xl font-bold">R{thisMonthSpent.toFixed(0)}</p>
                  <p className="text-xs text-muted-foreground">This Month</p>
                </CardContent>
              </Card>
              <Card className="glass border-white/10">
                <CardContent className="p-4">
                  <TrendingUp className="w-5 h-5 text-cyan-400 mb-1" />
                  <p className="font-mono text-2xl font-bold">R{thisYearSpent.toFixed(0)}</p>
                  <p className="text-xs text-muted-foreground">This Year</p>
                </CardContent>
              </Card>
              <Card className="glass border-white/10">
                <CardContent className="p-4">
                  <Receipt className="w-5 h-5 text-yellow-400 mb-1" />
                  <p className="font-mono text-2xl font-bold">R{avgReceipt.toFixed(0)}</p>
                  <p className="text-xs text-muted-foreground">Avg Receipt</p>
                </CardContent>
              </Card>
            </div>
          </motion.div>

          {/* Quick Stats Row */}
          <div className="flex flex-wrap gap-3">
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <Store className="w-3.5 h-3.5 mr-1.5" />
              {summary.unique_shops || 0} shops visited
            </Badge>
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <Calendar className="w-3.5 h-3.5 mr-1.5" />
              {summary.active_days || 0} active days
            </Badge>
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <Receipt className="w-3.5 h-3.5 mr-1.5" />
              {summary.total_receipts || 0} total receipts
            </Badge>
            {summary.min_receipt && (
              <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
                <TrendingDown className="w-3.5 h-3.5 mr-1.5" />
                Smallest: R{parseFloat(summary.min_receipt).toFixed(0)}
              </Badge>
            )}
            {summary.max_receipt && (
              <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
                <TrendingUp className="w-3.5 h-3.5 mr-1.5" />
                Biggest: R{parseFloat(summary.max_receipt).toFixed(0)}
              </Badge>
            )}
          </div>

          {/* Main Content Tabs */}
          <Tabs defaultValue="trends" className="space-y-4">
            <TabsList className="glass border-white/10">
              <TabsTrigger value="trends">Trends</TabsTrigger>
              <TabsTrigger value="shops">By Shop</TabsTrigger>
              <TabsTrigger value="receipts">Receipt Wallet</TabsTrigger>
            </TabsList>

            {/* Trends Tab */}
            <TabsContent value="trends">
              <Card className="glass border-white/10">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    Monthly Spending
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {monthlyChart.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">No spending data yet</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={monthlyChart} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="spendGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0.4} />
                            <stop offset="95%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis dataKey="month" stroke="rgba(255,255,255,0.5)" tick={{ fontSize: 11 }} />
                        <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fontSize: 11 }}
                          tickFormatter={(v) => `R${v}`} />
                        <Tooltip
                          contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                          formatter={(value, name) => {
                            if (name === 'spent') return [`R${Number(value).toFixed(2)}`, 'Total Spent'];
                            if (name === 'receipts') return [value, 'Receipts'];
                            return [value, name];
                          }}
                        />
                        <Area type="monotone" dataKey="spent" stroke="hsl(265, 89%, 66%)"
                          fill="url(#spendGradient)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>

              {/* Quarterly summary */}
              {data.quarterly?.length > 0 && (
                <Card className="glass border-white/10 mt-4">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-green-400" />
                      Quarterly Summary
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {data.quarterly.slice(0, 4).map((q, i) => (
                        <div key={q.quarter} className="p-3 bg-black/20 rounded-lg border border-white/5 text-center">
                          <p className="text-xs text-muted-foreground">{q.quarter}</p>
                          <p className="font-mono text-xl font-bold mt-1">R{parseFloat(q.total_spent).toFixed(0)}</p>
                          <p className="text-xs text-muted-foreground">{q.receipt_count} receipts</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Shops Tab */}
            <TabsContent value="shops">
              <div className="grid md:grid-cols-2 gap-4">
                {/* Pie Chart */}
                <Card className="glass border-white/10">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <PieChart className="w-5 h-5 text-primary" />
                      Spend by Shop
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {pieData.length === 0 ? (
                      <p className="text-muted-foreground text-center py-8">No shop data</p>
                    ) : (
                      <ResponsiveContainer width="100%" height={280}>
                        <RechartsPie>
                          <Pie data={pieData} cx="50%" cy="50%" outerRadius={100} innerRadius={50}
                            dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                            labelLine={{ stroke: 'rgba(255,255,255,0.3)' }}
                          >
                            {pieData.map((_, i) => (
                              <Cell key={i} fill={COLORS[i % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                            formatter={(value) => [`R${Number(value).toFixed(2)}`, 'Spent']}
                          />
                        </RechartsPie>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Shop List */}
                <Card className="glass border-white/10">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Store className="w-5 h-5 text-green-400" />
                      Your Shops
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {shops.map((shop, i) => (
                          <div key={i} className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              <div className="w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">{shop.shop_name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {shop.receipt_count} visits &middot; avg R{parseFloat(shop.avg_receipt || 0).toFixed(0)}
                                </p>
                              </div>
                            </div>
                            <p className="font-mono font-bold text-sm">R{parseFloat(shop.total_spent || 0).toFixed(0)}</p>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Receipt Wallet Tab */}
            <TabsContent value="receipts">
              <Card className="glass border-white/10">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Receipt className="w-5 h-5 text-primary" />
                    Receipt Wallet
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Search and retrieve any past receipt — never lose a slip again
                  </p>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Search */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      placeholder="Search by shop name..."
                      value={searchShop}
                      onChange={(e) => setSearchShop(e.target.value)}
                      className="pl-10 bg-white/5 border-white/10"
                    />
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {filteredReceipts.length} receipt{filteredReceipts.length !== 1 ? 's' : ''} found
                  </p>

                  {/* Receipt List */}
                  <ScrollArea className="h-[400px]">
                    <div className="space-y-2">
                      {filteredReceipts.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                          <Receipt className="w-10 h-10 mx-auto mb-2 opacity-50" />
                          <p>No receipts found</p>
                        </div>
                      ) : (
                        filteredReceipts.map((r) => (
                          <div
                            key={r.id}
                            className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5 hover:border-white/15 transition-colors cursor-pointer"
                            onClick={() => viewReceipt(r.id)}
                          >
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                                <Store className="w-4 h-4 text-primary" />
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">{r.shop_name || 'Unknown'}</p>
                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                  <Clock className="w-3 h-3" />
                                  {new Date(r.created_at).toLocaleDateString('en-ZA', {
                                    day: 'numeric', month: 'short', year: 'numeric',
                                    hour: '2-digit', minute: '2-digit'
                                  })}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <p className="font-mono font-bold text-primary">R{parseFloat(r.amount || 0).toFixed(2)}</p>
                              <Eye className="w-4 h-4 text-muted-foreground" />
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Receipt Detail Overlay */}
      {detailOpen && receiptDetail && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setDetailOpen(false)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-[hsl(var(--card))] border border-white/10 rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-heading text-lg font-bold flex items-center gap-2">
                  <Receipt className="w-5 h-5 text-primary" />
                  {receiptDetail.receipt?.shop_name || 'Receipt'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {receiptDetail.receipt?.created_at && new Date(receiptDetail.receipt.created_at).toLocaleDateString('en-ZA', {
                    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                  })}
                </p>
              </div>
              <p className="font-mono text-2xl font-bold text-primary">
                R{parseFloat(receiptDetail.receipt?.amount || 0).toFixed(2)}
              </p>
            </div>

            {/* Receipt Image */}
            {(receiptDetail.receipt?.image_url || receiptDetail.receipt?.image_data) && (
              <div className="rounded-xl overflow-hidden border border-white/10">
                <img
                  src={receiptDetail.receipt.image_url || `data:image/jpeg;base64,${receiptDetail.receipt.image_data}`}
                  alt="Receipt"
                  className="w-full max-h-[300px] object-contain bg-white/5"
                />
              </div>
            )}

            {/* Items */}
            {receiptDetail.receipt?.items?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Items ({receiptDetail.receipt.items.length})</h4>
                <div className="space-y-1 bg-black/20 rounded-lg p-3">
                  {receiptDetail.receipt.items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-muted-foreground truncate flex-1">{item.name}</span>
                      <span className="font-mono ml-2">R{(item.total_price || item.price || 0).toFixed(2)}</span>
                    </div>
                  ))}
                  <div className="border-t border-white/10 mt-2 pt-2 flex justify-between font-semibold">
                    <span>Total</span>
                    <span className="font-mono text-primary">R{parseFloat(receiptDetail.receipt.amount || 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Shop Info */}
            {receiptDetail.receipt?.shop_address && (
              <div className="text-sm">
                <p className="text-muted-foreground text-xs">Shop Address</p>
                <p>{receiptDetail.receipt.shop_address}</p>
              </div>
            )}

            <Button variant="outline" className="w-full" onClick={() => setDetailOpen(false)}>
              Close
            </Button>
          </motion.div>
        </div>
      )}
    </div>
  );
}
