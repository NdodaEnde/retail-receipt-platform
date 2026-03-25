import { useState, useEffect, useMemo, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ZoomableImage from "../components/ZoomableImage";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { ScrollArea } from "../components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import {
  TrendingUp, Store, Calendar,
  BarChart3, Search, Receipt, Clock, ShoppingCart, Package,
  Hash, Trophy, User, AlertCircle, Image, ChevronRight
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart as RechartsPie, Pie, Cell, AreaChart, Area
} from "recharts";
import axios from "axios";
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

function titleCase(str) {
  if (!str) return '';
  return str.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function formatRand(amount, decimals = 0) {
  return Number(amount).toLocaleString('en-ZA', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function RandIcon({ className }) {
  return (
    <span className={`inline-flex items-center justify-center font-bold font-mono ${className}`}>R</span>
  );
}

export default function MyReport() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [searchItem, setSearchItem] = useState("");
  const [itemPeriod, setItemPeriod] = useState("all");
  const [selectedReceipt, setSelectedReceipt] = useState(null);
  const [receiptDetail, setReceiptDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedShop, setSelectedShop] = useState(null);
  const itemListRef = useRef(null);

  useEffect(() => {
    async function fetchPortalData() {
      try {
        const res = await axios.get(`${API}/portal/${token}`);
        setData(res.data);
      } catch (err) {
        if (err.response?.status === 401) {
          setError("expired");
        } else {
          setError("failed");
        }
      } finally {
        setLoading(false);
      }
    }
    if (token) fetchPortalData();
  }, [token]);

  const openReceiptDetail = async (receipt) => {
    setSelectedReceipt(receipt);
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API}/portal/${token}/receipt/${receipt.id}`);
      setReceiptDetail(res.data);
    } catch (err) {
      console.error("Failed to fetch receipt detail:", err);
      setReceiptDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // Derived data
  const customer = data?.customer || {};
  const summary = data?.summary || {};
  const monthly = (data?.monthly || []).slice().reverse();
  const shops = data?.shops || [];
  const topItems = data?.top_items || [];
  const receipts = data?.recent_receipts || [];

  const totalSpent = parseFloat(summary.total_spent || customer.total_spent || 0);
  const thisMonthSpent = parseFloat(summary.this_month_spent || 0);
  const thisYearSpent = parseFloat(summary.this_year_spent || 0);
  const avgReceipt = parseFloat(summary.avg_receipt || 0);
  const totalReceipts = parseInt(summary.total_receipts || customer.total_receipts || 0, 10);

  const monthlyChart = monthly.map(m => ({
    month: formatMonth(m.month),
    spent: parseFloat(m.total_spent || 0),
    receipts: parseInt(m.receipt_count || 0, 10),
  }));

  const pieData = useMemo(() => {
    const top = shops.slice(0, 6).map(s => ({
      name: s.shop_name,
      value: parseFloat(s.total_spent || 0)
    }));
    const rest = shops.slice(6);
    if (rest.length > 0) {
      top.push({
        name: 'Other',
        value: rest.reduce((sum, s) => sum + parseFloat(s.total_spent || 0), 0)
      });
    }
    return top;
  }, [shops]);

  // Item analytics
  const availableMonths = useMemo(() => {
    const months = [...new Set(topItems.map(i => i.last_purchased?.slice(0, 7)).filter(Boolean))];
    return months.sort().reverse();
  }, [topItems]);

  const filteredItems = useMemo(() => {
    let items = topItems.map(i => ({
      item_name: i.item_name,
      purchase_count: parseInt(i.purchase_count || 0, 10),
      total_spent: parseFloat(i.total_spent || 0),
      avg_price: parseFloat(i.avg_price || 0),
      shops_selling: parseInt(i.shops_selling || 0, 10),
    }));

    if (searchItem) {
      items = items.filter(i => i.item_name.toLowerCase().includes(searchItem.toLowerCase()));
    }

    return items;
  }, [topItems, searchItem]);

  const itemChartData = useMemo(() => {
    return filteredItems.slice(0, 10).map(i => ({
      name: titleCase(i.item_name),
      spent: i.total_spent,
    })).reverse();
  }, [filteredItems]);

  const shopReceipts = useMemo(() => {
    if (!selectedShop) return [];
    return receipts.filter(r => r.shop_name === selectedShop);
  }, [selectedShop, receipts]);

  const greeting = customer.first_name ? `Hi ${titleCase(customer.first_name)}` : "Your Spending Report";

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center space-y-4">
          <div className="w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-muted-foreground">Loading your report...</p>
        </motion.div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="glass border-white/10 max-w-md">
            <CardContent className="p-8 text-center space-y-4">
              <AlertCircle className="w-12 h-12 text-yellow-400 mx-auto" />
              {error === "expired" ? (
                <>
                  <h2 className="font-heading text-xl font-bold">Link Expired</h2>
                  <p className="text-muted-foreground">
                    This report link has expired. Send <strong>REPORT</strong> on WhatsApp to get a fresh link.
                  </p>
                </>
              ) : (
                <>
                  <h2 className="font-heading text-xl font-bold">Something Went Wrong</h2>
                  <p className="text-muted-foreground">
                    We couldn't load your report. Try again or send <strong>REPORT</strong> on WhatsApp for a new link.
                  </p>
                </>
              )}
              <p className="text-sm text-muted-foreground/60">WhatsApp: +27 65 561 5874</p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "shops", label: "Shops" },
    { id: "items", label: "Items" },
    { id: "receipts", label: "Receipts" },
  ];

  return (
    <div className="min-h-screen p-4 pt-6 max-w-5xl mx-auto space-y-5 pb-8">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
            <User className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-2xl font-bold tracking-tight">{greeting}</h1>
            <p className="text-sm text-muted-foreground">Your personal spending report</p>
          </div>
        </div>
      </motion.div>

      {/* Summary Cards */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <RandIcon className="w-5 h-5 text-primary mb-1" />
              <p className="font-mono text-2xl font-bold">R{formatRand(totalSpent)}</p>
              <p className="text-xs text-muted-foreground">All-Time Spend</p>
            </CardContent>
          </Card>
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <Calendar className="w-5 h-5 text-green-400 mb-1" />
              <p className="font-mono text-2xl font-bold">R{formatRand(thisMonthSpent)}</p>
              <p className="text-xs text-muted-foreground">This Month</p>
            </CardContent>
          </Card>
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <Receipt className="w-5 h-5 text-cyan-400 mb-1" />
              <p className="font-mono text-2xl font-bold">{totalReceipts}</p>
              <p className="text-xs text-muted-foreground">Receipts</p>
            </CardContent>
          </Card>
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <Trophy className="w-5 h-5 text-yellow-400 mb-1" />
              <p className="font-mono text-2xl font-bold">R{formatRand(parseFloat(customer.total_winnings || 0))}</p>
              <p className="text-xs text-muted-foreground">{customer.total_wins || 0} Wins</p>
            </CardContent>
          </Card>
        </div>
      </motion.div>

      {/* Quick Stats */}
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
          <Store className="w-3.5 h-3.5 mr-1.5" />
          {summary.unique_shops || shops.length} shops
        </Badge>
        <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
          <Package className="w-3.5 h-3.5 mr-1.5" />
          {topItems.length} unique items
        </Badge>
        <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
          <RandIcon className="w-3.5 h-3.5 mr-1.5" />
          Avg R{formatRand(avgReceipt)}/receipt
        </Badge>
        {thisYearSpent > 0 && (
          <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
            <TrendingUp className="w-3.5 h-3.5 mr-1.5" />
            R{formatRand(thisYearSpent)} this year
          </Badge>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 p-1 bg-black/30 rounded-lg border border-white/10 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 min-w-[80px] px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.id
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-white/5"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          {/* Monthly Trend */}
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
                <div style={{ width: '100%', height: 280 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={monthlyChart} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="portalSpendGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="month" stroke="rgba(255,255,255,0.5)" tick={{ fontSize: 11 }} />
                      <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fontSize: 11 }}
                        tickFormatter={(v) => `R${formatRand(v)}`} />
                      <Tooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                        formatter={(value, name) => {
                          if (name === 'spent') return [`R${formatRand(value, 2)}`, 'Total Spent'];
                          return [value, name];
                        }}
                      />
                      <Area type="monotone" dataKey="spent" stroke="hsl(265, 89%, 66%)"
                        fill="url(#portalSpendGradient)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Top 5 Shops mini-list */}
          {shops.length > 0 && (
            <Card className="glass border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Store className="w-5 h-5 text-green-400" />
                  Top Shops
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {shops.slice(0, 5).map((shop, i) => (
                    <div key={i} className="flex items-center justify-between p-2 bg-black/20 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                        <span className="text-sm">{shop.shop_name}</span>
                      </div>
                      <span className="font-mono text-sm font-bold">R{formatRand(parseFloat(shop.total_spent || 0))}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </motion.div>
      )}

      {/* Shops Tab */}
      {activeTab === "shops" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <Card className="glass border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  Spend by Shop
                </CardTitle>
                <p className="text-xs text-muted-foreground">Tap a segment to see receipts</p>
              </CardHeader>
              <CardContent>
                {pieData.length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">No shop data</p>
                ) : (
                  <div style={{ width: '100%', height: 280 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPie>
                        <Pie data={pieData} cx="50%" cy="50%" outerRadius={100} innerRadius={50}
                          dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                          labelLine={{ stroke: 'rgba(255,255,255,0.3)' }}
                          onClick={(data) => { if (data?.name && data.name !== 'Other') setSelectedShop(data.name); }}
                          className="cursor-pointer"
                        >
                          {pieData.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                          formatter={(value) => [`R${formatRand(value, 2)}`, 'Spent']}
                        />
                      </RechartsPie>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="glass border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Store className="w-5 h-5 text-green-400" />
                  All Shops ({shops.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {shops.map((shop, i) => (
                      <div
                        key={i}
                        onClick={() => setSelectedShop(shop.shop_name)}
                        className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all hover:bg-white/5 ${
                          selectedShop === shop.shop_name
                            ? 'bg-primary/10 border-primary/30'
                            : 'bg-black/20 border-white/5'
                        }`}
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className="w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{shop.shop_name}</p>
                            <p className="text-xs text-muted-foreground">
                              {shop.receipt_count} visits &middot; avg R{formatRand(parseFloat(shop.avg_receipt || 0))}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <p className="font-mono font-bold text-sm">R{formatRand(parseFloat(shop.total_spent || 0))}</p>
                          <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          {/* Shop Receipts Drill-Down */}
          {selectedShop && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <Card className="glass border-white/10">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Receipt className="w-5 h-5 text-primary" />
                      {selectedShop} — Receipts ({shopReceipts.length})
                    </CardTitle>
                    <button onClick={() => setSelectedShop(null)} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
                      Clear
                    </button>
                  </div>
                </CardHeader>
                <CardContent>
                  {shopReceipts.length === 0 ? (
                    <p className="text-center py-6 text-muted-foreground text-sm">No receipts found for this shop in your recent history</p>
                  ) : (
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {shopReceipts.map((r) => (
                          <div
                            key={r.id}
                            onClick={() => openReceiptDetail(r)}
                            className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5 cursor-pointer hover:bg-white/5 transition-all"
                          >
                            <div className="min-w-0">
                              <p className="text-sm font-medium">
                                {new Date(r.created_at).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-white/10 mt-1">
                                {r.status === "won" ? "Winner!" : r.status === "processed" ? "Valid" : r.status}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-2">
                              <p className="font-mono font-bold text-primary">R{formatRand(parseFloat(r.amount || 0), 2)}</p>
                              <ChevronRight className="w-4 h-4 text-muted-foreground" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Items Tab */}
      {activeTab === "items" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          {/* Item Summary Badges */}
          <div className="flex flex-wrap gap-3">
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <Package className="w-3.5 h-3.5 mr-1.5" />
              {topItems.length} unique items
            </Badge>
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <Hash className="w-3.5 h-3.5 mr-1.5" />
              {topItems.reduce((s, i) => s + parseInt(i.purchase_count || 0, 10), 0)} purchases
            </Badge>
            <Badge variant="outline" className="text-sm px-3 py-1 border-white/20">
              <RandIcon className="w-3.5 h-3.5 mr-1.5" />
              R{formatRand(topItems.reduce((s, i) => s + parseFloat(i.total_spent || 0), 0))} item spend
            </Badge>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search items..."
              value={searchItem}
              onChange={(e) => setSearchItem(e.target.value)}
              className="pl-10 bg-white/5 border-white/10"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {/* Bar Chart */}
            <Card className="glass border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <ShoppingCart className="w-5 h-5 text-primary" />
                  Top Items by Spend
                </CardTitle>
              </CardHeader>
              <CardContent>
                {itemChartData.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Package className="w-10 h-10 mx-auto mb-2 opacity-50" />
                    <p>No items found</p>
                  </div>
                ) : (
                  <div style={{ width: '100%', height: Math.max(200, itemChartData.length * 35) }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={itemChartData} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
                        <XAxis type="number" stroke="rgba(255,255,255,0.5)" tick={{ fontSize: 10 }}
                          tickFormatter={(v) => `R${formatRand(v)}`} />
                        <YAxis type="category" dataKey="name" width={120} stroke="rgba(255,255,255,0.5)"
                          tick={{ fontSize: 10 }} />
                        <Tooltip
                          contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                          formatter={(value) => [`R${formatRand(value, 2)}`, 'Total Spent']}
                        />
                        <Bar dataKey="spent" radius={[0, 4, 4, 0]}>
                          {itemChartData.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Item List */}
            <Card ref={itemListRef} className="glass border-white/10">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Package className="w-5 h-5 text-green-400" />
                  All Items ({filteredItems.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[350px]">
                  <div className="space-y-2">
                    {filteredItems.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground">
                        <Package className="w-10 h-10 mx-auto mb-2 opacity-50" />
                        <p>No items found</p>
                      </div>
                    ) : (
                      filteredItems.map((item, i) => (
                        <div key={i} className="p-3 bg-black/20 rounded-lg border border-white/5">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{titleCase(item.item_name)}</p>
                              <div className="flex flex-wrap gap-x-3 mt-1">
                                <span className="text-xs text-muted-foreground">{item.purchase_count}x</span>
                                <span className="text-xs text-muted-foreground">avg R{formatRand(item.avg_price, 2)}</span>
                                {item.shops_selling > 0 && (
                                  <span className="text-xs text-muted-foreground">{item.shops_selling} shop{item.shops_selling !== 1 ? 's' : ''}</span>
                                )}
                              </div>
                            </div>
                            <p className="font-mono font-bold text-sm text-primary shrink-0">
                              R{formatRand(item.total_spent)}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}

      {/* Receipts Tab */}
      {activeTab === "receipts" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <Card className="glass border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Receipt className="w-5 h-5 text-primary" />
                Recent Receipts ({receipts.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[450px]">
                <div className="space-y-2">
                  {receipts.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Receipt className="w-10 h-10 mx-auto mb-2 opacity-50" />
                      <p>No receipts yet</p>
                    </div>
                  ) : (
                    receipts.map((r) => (
                      <div
                        key={r.id}
                        onClick={() => openReceiptDetail(r)}
                        className="p-3 bg-black/20 rounded-lg border border-white/5 cursor-pointer hover:bg-white/5 hover:border-white/10 transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                              <Store className="w-4 h-4 text-primary" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">{r.shop_name || 'Unknown'}</p>
                              <p className="text-xs text-muted-foreground flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {new Date(r.created_at).toLocaleDateString('en-ZA', {
                                  day: 'numeric', month: 'short', year: 'numeric'
                                })}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <p className="font-mono font-bold text-primary">R{formatRand(parseFloat(r.amount || 0), 2)}</p>
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-white/10">
                                {r.status === "won" ? "Winner!" : r.status === "processed" ? "Valid" : r.status}
                              </Badge>
                            </div>
                            <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Receipt Detail Dialog */}
          <Dialog open={!!selectedReceipt} onOpenChange={(open) => { if (!open) { setSelectedReceipt(null); setReceiptDetail(null); } }}>
            <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto glass border-white/10">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Store className="w-5 h-5 text-primary" />
                  {selectedReceipt?.shop_name || "Receipt Detail"}
                </DialogTitle>
              </DialogHeader>

              {detailLoading ? (
                <div className="p-8 text-center">
                  <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-muted-foreground">Loading receipt...</p>
                </div>
              ) : receiptDetail ? (
                <div className="space-y-4">
                  {/* Summary bar */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-xs text-muted-foreground flex items-center gap-1"><RandIcon className="w-3 h-3" /> Amount</div>
                      <div className="font-semibold mt-1 text-sm text-green-400">R{formatRand(parseFloat(receiptDetail.receipt?.amount || 0), 2)}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-xs text-muted-foreground flex items-center gap-1"><Package className="w-3 h-3" /> Items</div>
                      <div className="font-semibold mt-1 text-sm">{(receiptDetail.receipt?.items || []).length}</div>
                    </div>
                    <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" /> Date</div>
                      <div className="font-semibold mt-1 text-sm">
                        {receiptDetail.receipt?.created_at
                          ? new Date(receiptDetail.receipt.created_at).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' })
                          : 'N/A'}
                      </div>
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
                        {receiptDetail.receipt?.image_url ? (
                          <ZoomableImage
                            src={receiptDetail.receipt.image_url}
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
                                  <div className="flex-1 min-w-0">
                                    <span className="truncate block">{titleCase(item.name || `Item ${i + 1}`)}</span>
                                    {item.quantity > 1 && (
                                      <span className="text-xs text-muted-foreground">x{item.quantity}</span>
                                    )}
                                  </div>
                                  <span className="font-mono text-green-400 shrink-0 ml-2">
                                    R{formatRand(parseFloat(item.total_price || item.price || 0), 2)}
                                  </span>
                                </div>
                              ))}
                              <div className="flex justify-between items-center py-2 px-3 rounded-lg bg-primary/10 border border-primary/20 font-semibold text-sm">
                                <span>Total</span>
                                <span className="text-green-400">R{formatRand(parseFloat(receiptDetail.receipt.amount || 0), 2)}</span>
                              </div>
                            </>
                          ) : (
                            <div className="p-4 text-center text-muted-foreground">No items extracted</div>
                          )}
                        </div>
                      </ScrollArea>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-muted-foreground">Failed to load receipt details</div>
              )}
            </DialogContent>
          </Dialog>
        </motion.div>
      )}

      {/* Footer */}
      <div className="text-center pt-4 pb-2">
        <p className="text-xs text-muted-foreground/50">
          Powered by KlpIT &middot; Report generated {new Date().toLocaleDateString('en-ZA')}
        </p>
        <p className="text-xs text-muted-foreground/40 mt-1">
          This link expires after 24 hours. Send REPORT on WhatsApp for a new one.
        </p>
      </div>
    </div>
  );
}
