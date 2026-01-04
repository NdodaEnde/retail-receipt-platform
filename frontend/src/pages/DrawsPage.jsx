import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { ScrollArea } from "../components/ui/scroll-area";
import { Calendar } from "../components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";
import { Trophy, Calendar as CalendarIcon, Sparkles, Gift, Users, DollarSign, Play } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { format } from "date-fns";
import { API } from "../App";

export default function DrawsPage() {
  const [draws, setDraws] = useState([]);
  const [todayDraw, setTodayDraw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    fetchDraws();
  }, []);

  const fetchDraws = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/draws`);
      setDraws(response.data.draws);
      
      // Check for today's draw
      const today = format(new Date(), "yyyy-MM-dd");
      const todaysDraw = response.data.draws.find(d => d.draw_date === today);
      setTodayDraw(todaysDraw);
    } catch (error) {
      console.error("Failed to fetch draws:", error);
    } finally {
      setLoading(false);
    }
  };

  const runDraw = async (date = null) => {
    setRunning(true);
    try {
      const drawDate = date ? format(date, "yyyy-MM-dd") : format(new Date(), "yyyy-MM-dd");
      const response = await axios.post(`${API}/draws/run?draw_date=${drawDate}`);
      
      if (response.data.success) {
        setShowConfetti(true);
        toast.success(`🎉 Winner: ${response.data.winner.phone} won $${response.data.winner.amount.toFixed(2)}!`);
        setTimeout(() => setShowConfetti(false), 5000);
        fetchDraws();
      } else {
        toast.info(response.data.message);
      }
    } catch (error) {
      toast.error("Failed to run draw");
    } finally {
      setRunning(false);
    }
  };

  const totalPrizes = draws.reduce((sum, d) => sum + (d.prize_amount || 0), 0);
  const totalEntries = draws.reduce((sum, d) => sum + (d.total_receipts || 0), 0);

  return (
    <div className="min-h-screen p-6 pt-8 relative" data-testid="draws-page">
      {/* Confetti Effect */}
      {showConfetti && (
        <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
          {[...Array(50)].map((_, i) => (
            <div
              key={i}
              className="confetti absolute w-3 h-3"
              style={{
                left: `${Math.random() * 100}%`,
                background: ['#8b5cf6', '#00ff80', '#ff00ff', '#00ffff', '#ffd700'][Math.floor(Math.random() * 5)],
                animationDelay: `${Math.random() * 2}s`,
                transform: `rotate(${Math.random() * 360}deg)`
              }}
            />
          ))}
        </div>
      )}

      {/* Header */}
      <div className="max-w-4xl mx-auto mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight mb-2">Daily Draws</h1>
            <p className="text-muted-foreground">Daily winners and prize history</p>
          </div>
          
          <div className="flex gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="border-white/20" data-testid="date-picker-btn">
                  <CalendarIcon className="w-4 h-4 mr-2" />
                  {format(selectedDate, "MMM d")}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="glass border-white/10 p-0" align="end">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={(date) => date && setSelectedDate(date)}
                  className="rounded-lg"
                />
              </PopoverContent>
            </Popover>
            
            <Button 
              data-testid="run-draw-btn"
              onClick={() => runDraw(selectedDate)}
              disabled={running}
              className="glow-primary rounded-xl"
            >
              <Play className="w-4 h-4 mr-2" />
              {running ? "Drawing..." : "Run Draw"}
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="max-w-4xl mx-auto mb-8">
        <div className="grid grid-cols-3 gap-4">
          <Card className="stat-card-purple rounded-2xl">
            <CardContent className="p-4">
              <Trophy className="w-5 h-5 text-primary mb-2" />
              <p className="font-mono text-2xl font-bold">{draws.length}</p>
              <p className="text-xs text-muted-foreground">Total Draws</p>
            </CardContent>
          </Card>
          <Card className="stat-card-green rounded-2xl">
            <CardContent className="p-4">
              <DollarSign className="w-5 h-5 text-secondary mb-2" />
              <p className="font-mono text-2xl font-bold">${totalPrizes.toFixed(2)}</p>
              <p className="text-xs text-muted-foreground">Prizes Given</p>
            </CardContent>
          </Card>
          <Card className="stat-card-cyan rounded-2xl">
            <CardContent className="p-4">
              <Users className="w-5 h-5 text-cyan-400 mb-2" />
              <p className="font-mono text-2xl font-bold">{totalEntries}</p>
              <p className="text-xs text-muted-foreground">Total Entries</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Today's Draw Card */}
      {todayDraw && todayDraw.status === "completed" && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-4xl mx-auto mb-8"
        >
          <Card className="win-bg relative overflow-hidden rounded-2xl">
            <div className="absolute inset-0 bg-gradient-to-b from-black/70 to-black/90" />
            <CardContent className="relative p-8 text-center">
              <Sparkles className="w-12 h-12 text-yellow-400 mx-auto mb-4 animate-pulse" />
              <h2 className="font-heading text-2xl font-bold mb-2">Today's Winner!</h2>
              <p className="text-4xl font-mono font-bold text-secondary mb-2">
                ${todayDraw.prize_amount?.toFixed(2)}
              </p>
              <p className="text-muted-foreground mb-4">
                {todayDraw.winner_customer_phone}
              </p>
              <Badge className="bg-secondary/20 text-secondary border-secondary/30">
                {todayDraw.draw_date}
              </Badge>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Draw History */}
      <div className="max-w-4xl mx-auto">
        <Card className="glass-card rounded-2xl">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <Gift className="w-5 h-5 text-primary" />
              Draw History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px]" data-testid="draws-list">
              <div className="space-y-4">
                {loading ? (
                  <div className="text-center py-8">
                    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
                  </div>
                ) : draws.length === 0 ? (
                  <div className="text-center py-8">
                    <Trophy className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No draws yet. Run your first draw!</p>
                  </div>
                ) : (
                  draws.map((draw, index) => (
                    <motion.div
                      key={draw.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                          draw.status === 'completed' ? 'bg-secondary/20' : 'bg-muted'
                        }`}>
                          <Trophy className={`w-6 h-6 ${
                            draw.status === 'completed' ? 'text-secondary' : 'text-muted-foreground'
                          }`} />
                        </div>
                        <div>
                          <p className="font-semibold">{draw.draw_date}</p>
                          <p className="text-sm text-muted-foreground">
                            {draw.total_receipts} entries • ${draw.total_amount?.toFixed(2)} total
                          </p>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        {draw.status === 'completed' ? (
                          <>
                            <p className="font-mono text-lg font-bold text-secondary">
                              ${draw.prize_amount?.toFixed(2)}
                            </p>
                            <p className="text-xs text-muted-foreground truncate max-w-[120px]">
                              {draw.winner_customer_phone}
                            </p>
                          </>
                        ) : (
                          <Badge variant="outline" className="border-muted-foreground/30">
                            Pending
                          </Badge>
                        )}
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
