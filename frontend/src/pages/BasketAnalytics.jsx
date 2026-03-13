import { useState, useEffect, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { ScrollArea } from "../components/ui/scroll-area";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  ShoppingCart, Package, TrendingUp, Users, DollarSign, Layers,
  Search, ArrowUpDown, ArrowDown, ArrowUp, List
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, Cell
} from "recharts";
import api from "../lib/api";

const COLORS = ['hsl(265, 89%, 66%)', 'hsl(150, 100%, 50%)', 'hsl(300, 100%, 50%)', 'hsl(190, 100%, 50%)', 'hsl(40, 100%, 50%)'];

function titleCase(str) {
  if (!str) return '';
  return str.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

export default function BasketAnalytics() {
  const [stats, setStats] = useState({});
  const [topItems, setTopItems] = useState([]);
  const [itemPairs, setItemPairs] = useState([]);
  const [behavior, setBehavior] = useState([]);
  const [loading, setLoading] = useState(true);

  // All Items tab state — lazy loaded
  const [allItems, setAllItems] = useState(null); // null = not loaded yet
  const [allItemsLoading, setAllItemsLoading] = useState(false);
  const [allItemsSearch, setAllItemsSearch] = useState("");
  const [allItemsSort, setAllItemsSort] = useState({ field: "frequency", dir: "desc" });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, itemsRes, pairsRes, behaviorRes] = await Promise.all([
        api.get("/analytics/basket-stats"),
        api.get("/analytics/top-items?limit=20"),
        api.get("/analytics/item-pairs?limit=20"),
        api.get("/analytics/customer-behavior?limit=50"),
      ]);
      setStats(statsRes.data);
      setTopItems(itemsRes.data.data || []);
      setItemPairs(pairsRes.data.data || []);
      setBehavior(behaviorRes.data.data || []);
    } catch (err) {
      console.error("Failed to fetch basket analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllItems = useCallback(async () => {
    if (allItems !== null) return; // Already loaded
    setAllItemsLoading(true);
    try {
      const res = await api.get("/analytics/top-items?limit=500");
      setAllItems(res.data.data || []);
    } catch (err) {
      console.error("Failed to fetch all items:", err);
    } finally {
      setAllItemsLoading(false);
    }
  }, [allItems]);

  const handleTabChange = (value) => {
    if (value === "all-items") {
      fetchAllItems();
    }
  };

  const toggleSort = (field) => {
    setAllItemsSort(prev => ({
      field,
      dir: prev.field === field && prev.dir === "desc" ? "asc" : "desc",
    }));
  };

  const SortIcon = ({ field }) => {
    if (allItemsSort.field !== field) return <ArrowUpDown className="w-3 h-3 ml-1 opacity-40" />;
    return allItemsSort.dir === "desc"
      ? <ArrowDown className="w-3 h-3 ml-1 text-primary" />
      : <ArrowUp className="w-3 h-3 ml-1 text-primary" />;
  };

  const filteredAllItems = useMemo(() => {
    if (!allItems) return [];
    let items = [...allItems];

    // Search filter
    if (allItemsSearch) {
      items = items.filter(i => i.item_name?.toLowerCase().includes(allItemsSearch.toLowerCase()));
    }

    // Sort
    const { field, dir } = allItemsSort;
    items.sort((a, b) => {
      let aVal, bVal;
      if (field === "name") {
        aVal = a.item_name || "";
        bVal = b.item_name || "";
        return dir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      if (field === "frequency") { aVal = a.frequency || 0; bVal = b.frequency || 0; }
      else if (field === "avg_price") { aVal = parseFloat(a.avg_price || 0); bVal = parseFloat(b.avg_price || 0); }
      else if (field === "total_qty") { aVal = a.total_qty || 0; bVal = b.total_qty || 0; }
      else if (field === "price_range") { aVal = parseFloat(a.max_price || 0) - parseFloat(a.min_price || 0); bVal = parseFloat(b.max_price || 0) - parseFloat(b.min_price || 0); }
      return dir === "desc" ? bVal - aVal : aVal - bVal;
    });

    return items;
  }, [allItems, allItemsSearch, allItemsSort]);

  const statCards = [
    { label: "Avg Basket Size", value: `R${stats.avg_basket_size || 0}`, icon: ShoppingCart, color: "text-primary" },
    { label: "Avg Items/Receipt", value: stats.avg_item_count || 0, icon: Package, color: "text-green-400" },
    { label: "Avg Item Price", value: `R${stats.avg_item_price || 0}`, icon: DollarSign, color: "text-yellow-400" },
    { label: "Total Baskets", value: stats.total_baskets || 0, icon: Layers, color: "text-cyan-400" },
  ];

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-4 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="glass border-white/10">
              <CardContent className="p-4"><div className="h-16 bg-white/5 rounded animate-pulse" /></CardContent>
            </Card>
          ))}
        </div>
        <Card className="glass border-white/10"><CardContent className="p-6"><div className="h-64 bg-white/5 rounded animate-pulse" /></CardContent></Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <ShoppingCart className="w-6 h-6 text-primary" />
          Basket Analysis
        </h1>
        <p className="text-muted-foreground mt-1">Product insights and shopping patterns</p>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.div key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
              <Card className="glass border-white/10">
                <CardContent className="p-4 flex items-center gap-3">
                  <Icon className={`w-8 h-8 ${card.color}`} />
                  <div>
                    <p className="text-2xl font-bold">{card.value}</p>
                    <p className="text-xs text-muted-foreground">{card.label}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="items" className="space-y-4" onValueChange={handleTabChange}>
        <TabsList className="glass border-white/10">
          <TabsTrigger value="items">Top Items</TabsTrigger>
          <TabsTrigger value="pairs">Bought Together</TabsTrigger>
          <TabsTrigger value="customers">Customer Behavior</TabsTrigger>
          <TabsTrigger value="all-items">
            <List className="w-3.5 h-3.5 mr-1.5" />
            All Items
          </TabsTrigger>
        </TabsList>

        {/* Top Items Tab */}
        <TabsContent value="items">
          <Card className="glass border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                Top Products by Frequency
              </CardTitle>
            </CardHeader>
            <CardContent>
              {topItems.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No item data yet. Upload more receipts to see trends.</p>
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={topItems.slice(0, 15)} layout="vertical" margin={{ left: 120 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis type="number" stroke="rgba(255,255,255,0.5)" />
                    <YAxis type="category" dataKey="item_name" width={110} tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                      formatter={(value, name) => {
                        if (name === 'frequency') return [value, 'Times Purchased'];
                        if (name === 'avg_price') return [`R${Number(value).toFixed(2)}`, 'Avg Price'];
                        return [value, name];
                      }}
                    />
                    <Bar dataKey="frequency" fill="hsl(265, 89%, 66%)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Bought Together Tab */}
        <TabsContent value="pairs">
          <Card className="glass border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-primary" />
                Frequently Bought Together
              </CardTitle>
            </CardHeader>
            <CardContent>
              {itemPairs.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">Not enough data for item pair analysis yet.</p>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {itemPairs.map((pair, i) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{pair.item_a}</p>
                          <p className="text-xs text-muted-foreground">+ {pair.item_b}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-primary">{pair.co_occurrence}x</p>
                          <p className="text-xs text-muted-foreground">together</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Customer Behavior Tab */}
        <TabsContent value="customers">
          <Card className="glass border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="w-5 h-5 text-primary" />
                Customer Shopping Patterns
              </CardTitle>
            </CardHeader>
            <CardContent>
              {behavior.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No customer behavior data yet.</p>
              ) : (
                <>
                  <div className="mb-4">
                    <ResponsiveContainer width="100%" height={300}>
                      <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis
                          type="number"
                          dataKey="total_receipts"
                          name="Receipts"
                          stroke="rgba(255,255,255,0.5)"
                          label={{ value: 'Total Receipts', position: 'bottom', fill: 'rgba(255,255,255,0.5)' }}
                        />
                        <YAxis
                          type="number"
                          dataKey="avg_basket"
                          name="Avg Basket"
                          stroke="rgba(255,255,255,0.5)"
                          label={{ value: 'Avg Basket (R)', angle: -90, position: 'insideLeft', fill: 'rgba(255,255,255,0.5)' }}
                        />
                        <Tooltip
                          contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
                          formatter={(value, name) => {
                            if (name === 'Avg Basket') return [`R${Number(value).toFixed(2)}`, name];
                            return [value, name];
                          }}
                          labelFormatter={() => ''}
                        />
                        <Scatter data={behavior.filter(b => b.total_receipts > 0)} fill="hsl(265, 89%, 66%)">
                          {behavior.filter(b => b.total_receipts > 0).map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Scatter>
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  <ScrollArea className="h-[250px]">
                    <div className="space-y-2">
                      {behavior.map((c, i) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                              {c.first_name && c.surname ? `${c.first_name} ${c.surname}` : c.phone_number}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {c.unique_shops || 0} shops &middot; {c.active_days || 0} active days
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-bold">R{Number(c.avg_basket || 0).toFixed(0)}</p>
                            <p className="text-xs text-muted-foreground">{c.total_receipts || 0} receipts</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* All Items Tab — lazy loaded */}
        <TabsContent value="all-items">
          <Card className="glass border-white/10">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="w-5 h-5 text-primary" />
                All Items
                {allItems && (
                  <Badge variant="outline" className="ml-2 text-xs border-white/20">
                    {filteredAllItems.length} of {allItems.length}
                  </Badge>
                )}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Browse, search, and sort every product across all receipts
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {allItemsLoading ? (
                <div className="space-y-3">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="h-14 bg-white/5 rounded animate-pulse" />
                  ))}
                </div>
              ) : allItems === null ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>Click the tab to load all items</p>
                </div>
              ) : (
                <>
                  {/* Search */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      placeholder="Search items by name..."
                      value={allItemsSearch}
                      onChange={(e) => setAllItemsSearch(e.target.value)}
                      className="pl-10 bg-white/5 border-white/10"
                    />
                  </div>

                  {/* Sort buttons */}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => toggleSort("name")}>
                      Name <SortIcon field="name" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => toggleSort("frequency")}>
                      Frequency <SortIcon field="frequency" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => toggleSort("total_qty")}>
                      Qty Sold <SortIcon field="total_qty" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => toggleSort("avg_price")}>
                      Avg Price <SortIcon field="avg_price" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => toggleSort("price_range")}>
                      Price Range <SortIcon field="price_range" />
                    </Button>
                  </div>

                  {/* Items list */}
                  {filteredAllItems.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <Search className="w-10 h-10 mx-auto mb-2 opacity-40" />
                      <p>No items match your search</p>
                    </div>
                  ) : (
                    <ScrollArea className="h-[500px]">
                      <div className="space-y-1.5">
                        {filteredAllItems.map((item, i) => (
                          <div key={i} className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5 hover:border-white/15 transition-colors">
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                                <span className="text-xs font-mono text-primary font-bold">{i + 1}</span>
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium truncate">{titleCase(item.item_name)}</p>
                                <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                                  <span className="text-xs text-muted-foreground">
                                    {item.frequency}x purchased
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {item.total_qty || item.frequency} qty
                                  </span>
                                  {item.min_price != null && item.max_price != null && parseFloat(item.min_price) !== parseFloat(item.max_price) && (
                                    <span className="text-xs text-muted-foreground">
                                      R{parseFloat(item.min_price).toFixed(0)}–R{parseFloat(item.max_price).toFixed(0)}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="text-right shrink-0 ml-2">
                              <p className="font-mono font-bold text-sm text-primary">
                                R{parseFloat(item.avg_price || 0).toFixed(2)}
                              </p>
                              <p className="text-xs text-muted-foreground">avg price</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
