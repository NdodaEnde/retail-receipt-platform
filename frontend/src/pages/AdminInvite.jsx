import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import {
  UserPlus, QrCode, Copy, Check, Users, Phone, Clock, Link2
} from "lucide-react";
import api from "../lib/api";

const regStatusColors = {
  registered: "bg-green-500/20 text-green-400 border-green-500/30",
  unregistered: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  pending_first_name: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  pending_surname: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

export default function AdminInvite() {
  const [inviteData, setInviteData] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [phoneInput, setPhoneInput] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteResult, setInviteResult] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [inviteRes, customersRes] = await Promise.all([
        api.get("/admin/invite"),
        api.get("/admin/customers"),
      ]);
      setInviteData(inviteRes.data);
      setCustomers(customersRes.data.customers || []);
    } catch (err) {
      console.error("Failed to fetch invite data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const copyLink = async () => {
    if (!inviteData?.link) return;
    await navigator.clipboard.writeText(inviteData.link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const inviteCustomer = async () => {
    if (!phoneInput.trim()) return;
    setInviting(true);
    setInviteResult(null);
    try {
      const res = await api.post(`/admin/invite/${phoneInput.trim()}`);
      setInviteResult(res.data);
      setPhoneInput("");
      fetchData();
    } catch (err) {
      setInviteResult({ error: err.response?.data?.detail || "Failed to invite" });
    } finally {
      setInviting(false);
    }
  };

  const registered = customers.filter(c => c.registration_status === "registered").length;
  const total = customers.length;

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <UserPlus className="w-6 h-6 text-primary" />
          Customer Invitations
        </h1>
        <p className="text-muted-foreground mt-1">
          Invite new customers via QR code or WhatsApp link
        </p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="glass border-white/10">
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="w-8 h-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{total}</p>
              <p className="text-xs text-muted-foreground">Total Customers</p>
            </div>
          </CardContent>
        </Card>
        <Card className="glass border-white/10">
          <CardContent className="p-4 flex items-center gap-3">
            <Check className="w-8 h-8 text-green-400" />
            <div>
              <p className="text-2xl font-bold">{registered}</p>
              <p className="text-xs text-muted-foreground">Registered</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* QR Code Card */}
      <Card className="glass border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-primary" />
            Invite QR Code
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center space-y-4">
          {loading ? (
            <div className="w-48 h-48 bg-white/5 rounded-lg animate-pulse" />
          ) : inviteData?.qr_code ? (
            <img
              src={inviteData.qr_code}
              alt="WhatsApp Invite QR"
              className="w-48 h-48 rounded-lg bg-white p-2"
            />
          ) : null}
          <p className="text-sm text-muted-foreground text-center">
            Customer scans this QR code to open WhatsApp and start registration
          </p>
          {inviteData?.link && (
            <div className="flex items-center gap-2 w-full max-w-md">
              <div className="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-muted-foreground truncate">
                <Link2 className="w-4 h-4 inline mr-2" />
                {inviteData.link}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={copyLink}
                className="shrink-0"
              >
                {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invite by Phone */}
      <Card className="glass border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Phone className="w-5 h-5 text-primary" />
            Invite by Phone Number
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Pre-register a customer by their phone number. They'll complete registration when they message the bot.
          </p>
          <div className="flex gap-2">
            <Input
              placeholder="e.g. 27761234567"
              value={phoneInput}
              onChange={(e) => setPhoneInput(e.target.value)}
              className="flex-1 bg-black/40 border-white/10"
            />
            <Button onClick={inviteCustomer} disabled={inviting || !phoneInput.trim()}>
              {inviting ? "Inviting..." : "Invite"}
            </Button>
          </div>
          {inviteResult && (
            <div className={`text-sm p-2 rounded ${inviteResult.error ? "bg-red-500/20 text-red-400" : "bg-green-500/20 text-green-400"}`}>
              {inviteResult.error || `Invited ${inviteResult.customer_phone} — status: ${inviteResult.status}`}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Customer List */}
      <Card className="glass border-white/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Customers ({total})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 bg-white/5 rounded animate-pulse" />
              ))}
            </div>
          ) : customers.length === 0 ? (
            <p className="text-muted-foreground text-center py-4">No customers yet</p>
          ) : (
            <div className="space-y-2">
              {customers.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {c.first_name && c.surname
                        ? `${c.first_name} ${c.surname}`
                        : c.name || "Unregistered"}
                    </p>
                    <p className="text-xs text-muted-foreground">{c.phone_number}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={regStatusColors[c.registration_status] || regStatusColors.unregistered}
                    >
                      {c.registration_status || "unregistered"}
                    </Badge>
                    {c.invited_by && (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        invited
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
