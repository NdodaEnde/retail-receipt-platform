import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Receipt, MapPin, Trophy, Smartphone, ArrowRight, Sparkles } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "../App";

export default function LandingPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ total_receipts: 0, total_customers: 0, total_winnings: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/analytics/overview`);
      setStats(response.data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const seedDemo = async () => {
    try {
      toast.loading("Seeding demo data...");
      await axios.post(`${API}/demo/seed`);
      toast.dismiss();
      toast.success("Demo data created!");
      fetchStats();
    } catch (error) {
      toast.dismiss();
      toast.error("Failed to seed demo data");
    }
  };

  const features = [
    {
      icon: Smartphone,
      title: "WhatsApp Upload",
      description: "Simply snap your receipt and send via WhatsApp"
    },
    {
      icon: MapPin,
      title: "Auto-Location",
      description: "We geo-tag your purchase and track shop locations"
    },
    {
      icon: Trophy,
      title: "Daily Draws",
      description: "Win back your entire spend every single day"
    },
    {
      icon: Receipt,
      title: "Track Everything",
      description: "View all your receipts and spending analytics"
    }
  ];

  return (
    <div className="min-h-screen" data-testid="landing-page">
      {/* Hero Section */}
      <section className="hero-bg relative min-h-[90vh] flex items-center justify-center">
        <div className="hero-overlay absolute inset-0" />
        
        {/* Background Glow */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-glow rounded-full opacity-30" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-gradient-to-r from-emerald-600/20 to-cyan-600/20 blur-3xl rounded-full opacity-30" />
        
        <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm font-medium text-primary mb-6">
              <Sparkles className="w-4 h-4" />
              Daily Prize Draws
            </span>
            
            <h1 className="font-heading text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              <span className="text-gradient">Win Back</span>
              <br />
              <span className="text-gradient-primary">What You Spend</span>
            </h1>
            
            <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              Upload your retail receipts via WhatsApp. Every day, one lucky customer wins back their entire purchase amount.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button
                size="lg"
                data-testid="get-started-btn"
                onClick={() => navigate("/dashboard")}
                className="rounded-full px-8 py-6 text-lg font-bold glow-primary hover:scale-105 transition-transform"
              >
                Get Started
                <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
              
              <Button
                size="lg"
                variant="outline"
                data-testid="seed-demo-btn"
                onClick={seedDemo}
                className="rounded-full px-8 py-6 text-lg border-white/20 hover:bg-white/5"
              >
                Load Demo Data
              </Button>
            </div>
          </motion.div>
          
          {/* Stats Row */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-16 grid grid-cols-3 gap-6"
          >
            <div className="glass-card rounded-2xl p-6">
              <p className="font-mono text-3xl font-bold text-primary">{stats.total_receipts.toLocaleString()}</p>
              <p className="text-sm text-muted-foreground mt-1">Receipts Processed</p>
            </div>
            <div className="glass-card rounded-2xl p-6">
              <p className="font-mono text-3xl font-bold text-secondary">{stats.total_customers.toLocaleString()}</p>
              <p className="text-sm text-muted-foreground mt-1">Happy Customers</p>
            </div>
            <div className="glass-card rounded-2xl p-6">
              <p className="font-mono text-3xl font-bold text-accent">R{stats.total_winnings.toLocaleString()}</p>
              <p className="text-sm text-muted-foreground mt-1">Won Back</p>
            </div>
          </motion.div>
        </div>
      </section>
      
      {/* Features Section */}
      <section className="py-24 px-6 relative" data-testid="features-section">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-glow rounded-full opacity-20" />
        
        <div className="max-w-6xl mx-auto relative z-10">
          <div className="text-center mb-16">
            <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight mb-4">
              How It Works
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              Three simple steps to start winning
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
              >
                <Card className="glass-card p-6 h-full hover:border-primary/30 transition-all duration-300 group">
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <feature.icon className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="font-heading text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
      
      {/* CTA Section */}
      <section className="py-24 px-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />
        
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight mb-6">
              Ready to Start Winning?
            </h2>
            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
              Join thousands of smart shoppers who are already winning back their purchases.
            </p>
            
            <div className="glass inline-block rounded-2xl p-8">
              <img 
                src="https://images.unsplash.com/photo-1619320669563-92aeccfc4d95?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwxfHxob2xkaW5nJTIwcmVjZWlwdCUyMGhhbmQlMjBjbG9zZSUyMHVwfGVufDB8fHx8MTc2NzUyOTA4M3ww&ixlib=rb-4.1.0&q=85" 
                alt="Hand holding receipt"
                className="w-64 h-48 object-cover rounded-xl mb-6 mx-auto"
              />
              <p className="text-lg font-medium mb-2">Snap. Send. Win.</p>
              <p className="text-sm text-muted-foreground">It's that simple</p>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
