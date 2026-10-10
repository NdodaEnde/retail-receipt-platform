import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { MessageCircle } from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { getReportToken, WHATSAPP_REPORT_URL } from "../lib/pwa";

// Home screen of the installed app (manifest start_url = /my).
// Forwards to the last report link this device opened; otherwise explains how to get one.
export default function MyLauncher() {
  const token = getReportToken();
  if (token) return <Navigate to={`/my/${token}`} replace />;

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="glass border-white/10 max-w-md">
          <CardContent className="p-8 text-center space-y-4">
            <img src="/icon-192.png" alt="KlpIT" className="w-16 h-16 rounded-2xl mx-auto" />
            <h2 className="font-heading text-xl font-bold">Your spending report</h2>
            <p className="text-muted-foreground">
              Send <strong>REPORT</strong> to KlpIT on WhatsApp and open the link we send you.
            </p>
            <a
              href={WHATSAPP_REPORT_URL}
              className="inline-flex items-center gap-2 rounded-lg bg-green-500 px-4 py-2.5 font-semibold text-black"
              data-testid="get-report-whatsapp"
            >
              <MessageCircle className="w-4 h-4" /> Get my report
            </a>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
