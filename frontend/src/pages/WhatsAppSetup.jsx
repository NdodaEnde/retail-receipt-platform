import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";
import { 
  MessageSquare, QrCode, Check, X, AlertTriangle, 
  Smartphone, Send, Image, MapPin, HelpCircle, ExternalLink 
} from "lucide-react";
import axios from "axios";
import { API } from "../App";

export default function WhatsAppSetup() {
  const [status, setStatus] = useState({ connected: false, qr: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    try {
      const response = await axios.get(`${API}/whatsapp/status`);
      setStatus(response.data);
    } catch (error) {
      console.error("Failed to check WhatsApp status:", error);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: Image,
      title: "Receipt Photos",
      description: "Customers send receipt photos directly via WhatsApp"
    },
    {
      icon: MapPin,
      title: "Location Sharing",
      description: "Automatic geolocation when uploading receipts"
    },
    {
      icon: Send,
      title: "Instant Responses",
      description: "Bot replies with confirmation and draw status"
    },
    {
      icon: HelpCircle,
      title: "Help Commands",
      description: "Customers can check receipts, wins, and status"
    }
  ];

  const commands = [
    { cmd: "HELP", desc: "Show all available commands" },
    { cmd: "RECEIPTS", desc: "View recent uploaded receipts" },
    { cmd: "WINS", desc: "Check winning history" },
    { cmd: "STATUS", desc: "Check today's draw status" },
    { cmd: "[Send Photo]", desc: "Upload a receipt image" },
    { cmd: "[Share Location]", desc: "Share location before upload" }
  ];

  return (
    <div className="min-h-screen p-6 pt-8" data-testid="whatsapp-setup">
      {/* Header */}
      <div className="max-w-4xl mx-auto mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-green-500/20 flex items-center justify-center">
            <MessageSquare className="w-6 h-6 text-green-500" />
          </div>
          <div>
            <h1 className="font-heading text-3xl font-bold tracking-tight">WhatsApp Integration</h1>
            <p className="text-muted-foreground">Connect customers via WhatsApp Business API</p>
          </div>
        </div>
      </div>

      {/* Status Card */}
      <div className="max-w-4xl mx-auto mb-8">
        <Card className="glass-card rounded-2xl overflow-hidden">
          <div className={`h-1 ${status.connected ? 'bg-green-500' : 'bg-yellow-500'}`} />
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
                  status.connected ? 'bg-green-500/20' : 'bg-yellow-500/20'
                }`}>
                  {status.connected ? (
                    <Check className="w-8 h-8 text-green-500" />
                  ) : (
                    <AlertTriangle className="w-8 h-8 text-yellow-500" />
                  )}
                </div>
                <div>
                  <h2 className="font-heading text-xl font-semibold">
                    {status.connected ? "Connected" : "Setup Required"}
                  </h2>
                  <p className="text-muted-foreground text-sm">
                    {status.connected 
                      ? "WhatsApp Business API is active" 
                      : "WhatsApp integration needs configuration"}
                  </p>
                </div>
              </div>
              <Badge 
                variant={status.connected ? "default" : "outline"}
                className={status.connected ? "bg-green-500/20 text-green-500 border-green-500/30" : ""}
              >
                {status.connected ? "Online" : "Offline"}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Setup Instructions */}
      <div className="max-w-4xl mx-auto mb-8">
        <Alert className="glass border-white/10">
          <AlertTriangle className="h-4 w-4 text-yellow-500" />
          <AlertTitle className="font-heading">WhatsApp Business API Setup</AlertTitle>
          <AlertDescription className="mt-2 text-muted-foreground">
            <p className="mb-4">
              This platform uses the <strong>Baileys library</strong> for WhatsApp Web integration. 
              To enable full functionality:
            </p>
            <ol className="list-decimal list-inside space-y-2">
              <li>Set up the Node.js WhatsApp microservice</li>
              <li>Configure Redis for session persistence</li>
              <li>Scan the QR code with your WhatsApp account</li>
              <li>The webhook will automatically process incoming messages</li>
            </ol>
            <div className="mt-4 flex gap-2">
              <Button variant="outline" size="sm" className="border-white/20" asChild>
                <a href="https://github.com/WhiskeySockets/Baileys" target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Baileys Docs
                </a>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>

      {/* Features Grid */}
      <div className="max-w-4xl mx-auto mb-8">
        <h2 className="font-heading text-xl font-semibold mb-4">Features</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="glass-card h-full">
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center flex-shrink-0">
                      <feature.icon className="w-5 h-5 text-green-500" />
                    </div>
                    <div>
                      <h3 className="font-semibold mb-1">{feature.title}</h3>
                      <p className="text-sm text-muted-foreground">{feature.description}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Bot Commands */}
      <div className="max-w-4xl mx-auto mb-8">
        <Card className="glass-card rounded-2xl">
          <CardHeader>
            <CardTitle className="font-heading flex items-center gap-2">
              <Smartphone className="w-5 h-5 text-primary" />
              Bot Commands
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {commands.map((item, index) => (
                <div 
                  key={item.cmd}
                  className="flex items-center justify-between p-3 rounded-lg bg-white/5"
                >
                  <code className="font-mono text-sm text-primary bg-primary/10 px-2 py-1 rounded">
                    {item.cmd}
                  </code>
                  <span className="text-sm text-muted-foreground">{item.desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Architecture Diagram */}
      <div className="max-w-4xl mx-auto">
        <Card className="glass-card rounded-2xl">
          <CardHeader>
            <CardTitle className="font-heading">System Architecture</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative">
              <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                {/* Customer */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-green-500/20 flex items-center justify-center mx-auto mb-3">
                    <Smartphone className="w-10 h-10 text-green-500" />
                  </div>
                  <p className="font-semibold">Customer</p>
                  <p className="text-xs text-muted-foreground">WhatsApp App</p>
                </div>
                
                {/* Arrow */}
                <div className="hidden md:block text-muted-foreground">→</div>
                <div className="md:hidden text-muted-foreground">↓</div>

                {/* Baileys Service */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-blue-500/20 flex items-center justify-center mx-auto mb-3">
                    <MessageSquare className="w-10 h-10 text-blue-500" />
                  </div>
                  <p className="font-semibold">Baileys</p>
                  <p className="text-xs text-muted-foreground">Node.js Service</p>
                </div>

                {/* Arrow */}
                <div className="hidden md:block text-muted-foreground">→</div>
                <div className="md:hidden text-muted-foreground">↓</div>

                {/* FastAPI */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-primary/20 flex items-center justify-center mx-auto mb-3">
                    <svg className="w-10 h-10 text-primary" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <p className="font-semibold">FastAPI</p>
                  <p className="text-xs text-muted-foreground">Backend API</p>
                </div>

                {/* Arrow */}
                <div className="hidden md:block text-muted-foreground">→</div>
                <div className="md:hidden text-muted-foreground">↓</div>

                {/* MongoDB */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-emerald-500/20 flex items-center justify-center mx-auto mb-3">
                    <svg className="w-10 h-10 text-emerald-500" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                    </svg>
                  </div>
                  <p className="font-semibold">MongoDB</p>
                  <p className="text-xs text-muted-foreground">Database</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
