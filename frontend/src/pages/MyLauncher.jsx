import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Card, CardContent } from "../components/ui/card";
import PairCodeCard from "../components/PairCodeCard";
import { getReportToken } from "../lib/pwa";

// Home screen of the installed app (manifest start_url = /my).
// Forwards to the report token saved on this device; otherwise signs in with a WhatsApp code.
export default function MyLauncher() {
  const token = getReportToken();
  if (token) return <Navigate to={`/my/${token}`} replace />;

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
        <Card className="glass border-white/10">
          <CardContent className="p-8 space-y-5">
            <div className="text-center space-y-2">
              <img src="/icon-192.png" alt="KlpIT" className="w-16 h-16 rounded-2xl mx-auto" />
              <h2 className="font-heading text-xl font-bold">Your spending report</h2>
            </div>
            <PairCodeCard />
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
