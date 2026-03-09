import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  ShoppingCart, Package, TrendingUp, Users, DollarSign, Layers
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, Cell
} from "recharts";
import api from "../lib/api";

const COLORS = ['hsl(265, 89%, 66%)', 'hsl(150, 100%, 50%)', 'hsl(300, 100%, 50%)', 'hsl(190, 100%, 50%)', 'hsl(40, 100%, 50%)'];

export default function BasketAnalytics() {
  const [stats, setStats] = useState({});
  const [topItems, setTopItems] = useState([]);
  const [itemPairs, setItemPairs] = useState([]);
  const [behavior, setBehavior] = useState([]);
  const [loading, setLoading] = useState(true);

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
      <Tabs defaultValue="items" className="space-y-4">
        <TabsList className="glass border-white/10">
          <TabsTrigger value="items">Top Items</TabsTrigger>
          <TabsTrigger value="pairs">Bought Together</TabsTrigger>
          <TabsTrigger value="customers">Customer Behavior</TabsTrigger>
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
      </Tabs>
    </div>
  );
}
