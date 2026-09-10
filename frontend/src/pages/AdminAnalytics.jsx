import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { ScrollArea } from "../components/ui/scroll-area";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { 
  BarChart3, TrendingUp, Store, Users, Receipt, DollarSign, 
  Clock, Calendar, Trophy, PieChart, Search, ArrowUp, ArrowDown, ArrowUpDown
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart as RePieChart, Pie, Cell, AreaChart, Area
} from "recharts";
import api from "../lib/api";

const COLORS = ['hsl(265, 89%, 66%)', 'hsl(150, 100%, 50%)', 'hsl(300, 100%, 50%)', 'hsl(190, 100%, 50%)', 'hsl(40, 100%, 50%)'];

export default function AdminAnalytics() {
  const [overview, setOverview] = useState({});
  const [spendingByDay, setSpendingByDay] = useState([]);
  const [popularShops, setPopularShops] = useState([]);
  const [allShops, setAllShops] = useState([]);
  const [shopSearch, setShopSearch] = useState("");
  const [shopSort, setShopSort] = useState({ field: "total_sales", dir: "desc" });
  const [topSpenders, setTopSpenders] = useState([]);
  const [receiptsByHour, setReceiptsByHour] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAllAnalytics();
  }, []);

  const fetchAllAnalytics = async () => {
    setLoading(true);
    try {
      const [overviewRes, spendingRes, shopsRes, spendersRes, hoursRes, allShopsRes] = await Promise.all([
        api.get("/analytics/overview"),
        api.get("/analytics/spending-by-day?days=14"),
        api.get("/analytics/popular-shops?limit=8"),
        api.get("/analytics/top-spenders?limit=8"),
        api.get("/analytics/receipts-by-hour"),
        api.get("/analytics/shops")
      ]);
      
      setOverview(overviewRes.data);
      setSpendingByDay(spendingRes.data.data);
      setPopularShops(shopsRes.data.shops);
      setAllShops(allShopsRes.data.data || []);
      setTopSpenders(spendersRes.data.customers);
      setReceiptsByHour(hoursRes.data.data);
    } catch (error) {
      console.error("Failed to fetch analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredShops = useMemo(() => {
    const q = shopSearch.trim().toLowerCase();
    let rows = allShops.filter(s => !q || [s.name, s.chain, s.address].some(v => (v || "").toLowerCase().includes(q)));
    const { field, dir } = shopSort;
    rows = [...rows].sort((a, b) => {
      const av = a[field], bv = b[field];
      if (typeof av === "string" || typeof bv === "string") {
        return dir === "asc" ? String(av || "").localeCompare(String(bv || "")) : String(bv || "").localeCompare(String(av || ""));
      }
      return dir === "asc" ? (av || 0) - (bv || 0) : (bv || 0) - (av || 0);
    });
    return rows;
  }, [allShops, shopSearch, shopSort]);

  const toggleShopSort = (field) => setShopSort(prev => ({
    field, dir: prev.field === field && prev.dir === "desc" ? "asc" : "desc",
  }));
  const ShopSortIcon = ({ field }) => shopSort.field !== field
    ? <ArrowUpDown className="w-3 h-3 ml-1 opacity-40 inline" />
    : (shopSort.dir === "desc" ? <ArrowDown className="w-3 h-3 ml-1 text-primary inline" /> : <ArrowUp className="w-3 h-3 ml-1 text-primary inline" />);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass p-3 rounded-lg border border-white/10">
          <p className="text-sm font-medium mb-1">{label}</p>
          {payload.map((item, index) => (
            <p key={index} className="text-xs text-muted-foreground">
              {item.name}: <span className="font-mono text-foreground">{typeof item.value === 'number' ? item.value.toLocaleString() : item.value}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 pt-8" data-testid="admin-analytics">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <h1 className="font-heading text-3xl font-bold tracking-tight mb-2">Analytics Dashboard</h1>
        <p className="text-muted-foreground">Insights into customer behavior and spending patterns</p>
      </div>

      {/* Overview Stats */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card className="stat-card-purple rounded-2xl">
            <CardContent className="p-4">
              <Users className="w-5 h-5 text-primary mb-2" />
              <p className="font-mono text-2xl font-bold">{overview.total_customers?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Customers</p>
            </CardContent>
          </Card>
          <Card className="stat-card-green rounded-2xl">
            <CardContent className="p-4">
              <Receipt className="w-5 h-5 text-secondary mb-2" />
              <p className="font-mono text-2xl font-bold">{overview.total_receipts?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Receipts</p>
            </CardContent>
          </Card>
          <Card className="stat-card-pink rounded-2xl">
            <CardContent className="p-4">
              <Store className="w-5 h-5 text-accent mb-2" />
              <p className="font-mono text-2xl font-bold">{overview.total_shops?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Shops</p>
            </CardContent>
          </Card>
          <Card className="stat-card-cyan rounded-2xl">
            <CardContent className="p-4">
              <DollarSign className="w-5 h-5 text-cyan-400 mb-2" />
              <p className="font-mono text-2xl font-bold">R{overview.total_spent?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Total Spent</p>
            </CardContent>
          </Card>
          <Card className="glass-card rounded-2xl border-yellow-500/20">
            <CardContent className="p-4">
              <Trophy className="w-5 h-5 text-yellow-500 mb-2" />
              <p className="font-mono text-2xl font-bold">{overview.total_draws?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Draws</p>
            </CardContent>
          </Card>
          <Card className="glass-card rounded-2xl border-orange-500/20">
            <CardContent className="p-4">
              <TrendingUp className="w-5 h-5 text-orange-500 mb-2" />
              <p className="font-mono text-2xl font-bold">R{overview.total_winnings?.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Won Back</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Charts */}
      <div className="max-w-7xl mx-auto">
        <Tabs defaultValue="spending" className="w-full">
          <TabsList className="w-full glass border-white/10 p-1 rounded-xl mb-6 grid grid-cols-4">
            <TabsTrigger 
              value="spending" 
              data-testid="spending-tab"
              className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Spending
            </TabsTrigger>
            <TabsTrigger 
              value="shops" 
              data-testid="shops-tab"
              className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
            >
              <Store className="w-4 h-4 mr-2" />
              Shops
            </TabsTrigger>
            <TabsTrigger 
              value="customers" 
              data-testid="customers-tab"
              className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
            >
              <Users className="w-4 h-4 mr-2" />
              Customers
            </TabsTrigger>
            <TabsTrigger 
              value="time" 
              data-testid="time-tab"
              className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
            >
              <Clock className="w-4 h-4 mr-2" />
              Time
            </TabsTrigger>
          </TabsList>

          {/* Spending Tab */}
          <TabsContent value="spending" data-testid="spending-content">
            <Card className="glass-card rounded-2xl">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-primary" />
                  Daily Spending Trend
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={spendingByDay}>
                      <defs>
                        <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="hsl(265, 89%, 66%)" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="date" 
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                        tickFormatter={(value) => value.slice(5)}
                      />
                      <YAxis 
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                        tickFormatter={(value) => `R${value}`}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Area 
                        type="monotone" 
                        dataKey="amount" 
                        stroke="hsl(265, 89%, 66%)" 
                        fillOpacity={1}
                        fill="url(#colorAmount)"
                        name="Amount"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Shops Tab */}
          <TabsContent value="shops" data-testid="shops-content">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="glass-card rounded-2xl">
                <CardHeader>
                  <CardTitle className="font-heading flex items-center gap-2">
                    <Store className="w-5 h-5 text-secondary" />
                    Popular Shops
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[350px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={popularShops} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis 
                          type="number"
                          stroke="hsl(var(--muted-foreground))"
                          tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                        />
                        <YAxis 
                          dataKey="name" 
                          type="category"
                          stroke="hsl(var(--muted-foreground))"
                          tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                          width={100}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="receipt_count" fill="hsl(150, 100%, 50%)" radius={[0, 4, 4, 0]} name="Receipts" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card rounded-2xl">
                <CardHeader>
                  <CardTitle className="font-heading flex items-center gap-2">
                    <PieChart className="w-5 h-5 text-accent" />
                    Sales Distribution
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[350px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RePieChart>
                        <Pie
                          data={popularShops.slice(0, 5)}
                          dataKey="total_sales"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={120}
                          innerRadius={60}
                          paddingAngle={2}
                          label={({ name, percent }) => `${name.split(' ')[0]} ${(percent * 100).toFixed(0)}%`}
                          labelLine={{ stroke: 'hsl(var(--muted-foreground))' }}
                        >
                          {popularShops.slice(0, 5).map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                      </RePieChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* All shops — searchable, sortable */}
            <Card className="glass-card rounded-2xl mt-6">
              <CardHeader className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 space-y-0">
                <CardTitle className="font-heading flex items-center gap-2">
                  <Store className="w-5 h-5 text-primary" />
                  All Shops
                  <span className="text-xs font-normal text-muted-foreground ml-1">{filteredShops.length} of {allShops.length}</span>
                </CardTitle>
                <div className="relative w-full md:w-72">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search shop, chain or address…"
                    value={shopSearch}
                    onChange={(e) => setShopSearch(e.target.value)}
                    className="pl-9 bg-black/20 border-white/10"
                    data-testid="shop-search"
                  />
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[420px]">
                  <table className="w-full table-fixed text-sm">
                    <colgroup>
                      <col className="w-[34%]" /><col className="w-[16%]" /><col className="w-[11%]" />
                      <col className="w-[14%]" /><col className="w-[13%]" /><col className="w-[12%]" />
                    </colgroup>
                    <thead className="sticky top-0 bg-card/95 backdrop-blur">
                      <tr className="text-[11px] uppercase tracking-wider text-muted-foreground border-b border-white/10">
                        <th className="py-2 px-2 text-left font-medium cursor-pointer select-none" onClick={() => toggleShopSort("name")}>Shop<ShopSortIcon field="name" /></th>
                        <th className="py-2 px-2 text-left font-medium cursor-pointer select-none" onClick={() => toggleShopSort("chain")}>Chain<ShopSortIcon field="chain" /></th>
                        <th className="py-2 px-2 text-right font-medium cursor-pointer select-none" onClick={() => toggleShopSort("receipt_count")}>Receipts<ShopSortIcon field="receipt_count" /></th>
                        <th className="py-2 px-2 text-right font-medium cursor-pointer select-none" onClick={() => toggleShopSort("total_sales")}>Revenue<ShopSortIcon field="total_sales" /></th>
                        <th className="py-2 px-2 text-right font-medium cursor-pointer select-none" onClick={() => toggleShopSort("avg_basket")}>Avg basket<ShopSortIcon field="avg_basket" /></th>
                        <th className="py-2 px-2 text-left font-medium">Location</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredShops.map((s) => (
                        <tr key={s.id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-2 px-2">
                            <div className="truncate font-medium">{s.name}</div>
                            {s.address && <div className="truncate text-[11px] text-muted-foreground">{s.address}</div>}
                          </td>
                          <td className="py-2 px-2 truncate text-muted-foreground">{s.chain || "—"}</td>
                          <td className="py-2 px-2 text-right font-mono tabular-nums">{s.receipt_count}</td>
                          <td className={`py-2 px-2 text-right font-mono tabular-nums ${s.receipt_count && !s.total_sales ? "text-yellow-400" : ""}`}>
                            R{Number(s.total_sales).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-2 px-2 text-right font-mono tabular-nums text-muted-foreground">{s.avg_basket != null ? `R${Number(s.avg_basket).toFixed(2)}` : "—"}</td>
                          <td className="py-2 px-2">
                            <Badge variant="outline" className={`text-[10px] border-white/15 ${["verified", "rooftop"].includes(s.precision) ? "text-green-400" : s.precision === "biased" ? "text-yellow-400" : "text-muted-foreground"}`}>
                              {s.precision}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                      {filteredShops.length === 0 && (
                        <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">No shops match "{shopSearch}"</td></tr>
                      )}
                    </tbody>
                  </table>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Customers Tab */}
          <TabsContent value="customers" data-testid="customers-content">
            <Card className="glass-card rounded-2xl">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Users className="w-5 h-5 text-primary" />
                  Top Spenders
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <div className="space-y-4">
                    {topSpenders.map((customer, index) => (
                      <motion.div
                        key={customer.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${
                            index === 0 ? 'bg-yellow-500/20 text-yellow-500' :
                            index === 1 ? 'bg-gray-400/20 text-gray-400' :
                            index === 2 ? 'bg-orange-600/20 text-orange-600' :
                            'bg-muted text-muted-foreground'
                          }`}>
                            {index + 1}
                          </div>
                          <div>
                            <p className="font-semibold">{customer.name || customer.phone_number}</p>
                            <p className="text-xs text-muted-foreground font-mono">{customer.phone_number}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-lg font-bold text-primary">
                            R{customer.total_spent?.toFixed(2)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {customer.total_receipts} receipts
                          </p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Time Tab */}
          <TabsContent value="time" data-testid="time-content">
            <Card className="glass-card rounded-2xl">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Clock className="w-5 h-5 text-cyan-400" />
                  Receipts by Hour of Day
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={receiptsByHour}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="hour" 
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                        tickFormatter={(value) => `${value}:00`}
                      />
                      <YAxis 
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar 
                        dataKey="count" 
                        fill="hsl(190, 100%, 50%)" 
                        radius={[4, 4, 0, 0]}
                        name="Receipts"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
