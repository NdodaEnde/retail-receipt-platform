import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { MessageCircle } from "lucide-react";
import { API } from "../App";
import { saveReportToken, WHATSAPP_REPORT_URL } from "../lib/pwa";

// Signs the installed app in with the code from the WhatsApp REPORT reply.
export default function PairCodeCard() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const digits = code.replace(/\D/g, "");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/portal/pair`, { code: digits });
      saveReportToken(res.data.token);
      navigate(`/my/${res.data.token}`, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't connect. Check your internet and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 text-left">
      <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
        <li>Tap <strong>Get my code</strong> and send <strong>REPORT</strong> on WhatsApp</li>
        <li>Come back here and type the 6-digit code we reply with</li>
      </ol>
      <a
        href={WHATSAPP_REPORT_URL}
        className="flex items-center justify-center gap-2 rounded-lg bg-green-500 px-4 py-2.5 font-semibold text-black"
        data-testid="get-report-whatsapp"
      >
        <MessageCircle className="w-4 h-4" /> Get my code
      </a>
      <form onSubmit={submit} className="space-y-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="123 456"
          maxLength={7}
          aria-label="6-digit code"
          className="w-full rounded-lg border border-white/15 bg-black/40 px-4 py-3 text-center font-mono text-2xl tracking-[0.3em] placeholder:text-muted-foreground/25 focus:outline-none focus:border-primary"
          data-testid="pair-code-input"
        />
        {error && <p className="text-sm text-red-400 text-center" data-testid="pair-code-error">{error}</p>}
        <button
          type="submit"
          disabled={digits.length !== 6 || busy}
          className="w-full rounded-lg bg-primary px-4 py-2.5 font-semibold text-primary-foreground disabled:opacity-40"
          data-testid="pair-code-submit"
        >
          {busy ? "Checking…" : "Open my report"}
        </button>
      </form>
    </div>
  );
}
