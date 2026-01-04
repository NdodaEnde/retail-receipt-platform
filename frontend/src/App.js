import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Receipt, Map, Trophy, BarChart3, Settings, Home, MessageSquare } from "lucide-react";
import LandingPage from "./pages/LandingPage";
import CustomerDashboard from "./pages/CustomerDashboard";
import MapView from "./pages/MapView";
import DrawsPage from "./pages/DrawsPage";
import AdminAnalytics from "./pages/AdminAnalytics";
import WhatsAppSetup from "./pages/WhatsAppSetup";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const navItems = [
  { path: "/", icon: Home, label: "Home" },
  { path: "/dashboard", icon: Receipt, label: "Receipts" },
  { path: "/map", icon: Map, label: "Map" },
  { path: "/draws", icon: Trophy, label: "Draws" },
  { path: "/analytics", icon: BarChart3, label: "Analytics" },
  { path: "/whatsapp", icon: MessageSquare, label: "WhatsApp" },
];

function BottomNav() {
  const location = useLocation();
  
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 glass border-t border-white/10" data-testid="bottom-nav">
      <div className="max-w-screen-xl mx-auto px-2">
        <div className="flex justify-around items-center h-16">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            
            return (
              <NavLink
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={`flex flex-col items-center justify-center px-3 py-2 rounded-xl transition-all duration-300 ${
                  isActive 
                    ? "text-primary glow-primary" 
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? "animate-pulse-glow" : ""}`} />
                <span className="text-xs mt-1 font-medium">{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className="min-h-screen pb-20"
      >
        <Routes location={location}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard" element={<CustomerDashboard />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/draws" element={<DrawsPage />} />
          <Route path="/analytics" element={<AdminAnalytics />} />
          <Route path="/whatsapp" element={<WhatsAppSetup />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function App() {
  return (
    <div className="App min-h-screen bg-background">
      <BrowserRouter>
        <AnimatedRoutes />
        <BottomNav />
      </BrowserRouter>
      <Toaster 
        position="top-center" 
        toastOptions={{
          style: {
            background: 'hsl(var(--card))',
            color: 'hsl(var(--foreground))',
            border: '1px solid hsl(var(--border))',
          },
        }}
      />
    </div>
  );
}

export default App;
