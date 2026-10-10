import { useState } from "react";
import { Download, Share, X } from "lucide-react";
import { isIOS, isStandalone, useInstallPrompt } from "../lib/pwa";

const DISMISS_KEY = "klpit.installDismissed";

export default function InstallAppBanner() {
  const { canPrompt, promptInstall } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
  });

  const ios = isIOS();
  if (dismissed || isStandalone() || (!canPrompt && !ios)) return null;

  const dismiss = () => {
    setDismissed(true);
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* private mode */ }
  };

  return (
    <div className="glass border border-primary/30 rounded-xl p-3 flex items-center gap-3" data-testid="install-app-banner">
      <img src="/icon-192.png" alt="" className="w-10 h-10 rounded-lg shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">Get the KlpIT app</p>
        {ios ? (
          <p className="text-xs text-muted-foreground">
            Tap <Share className="inline w-3.5 h-3.5 -mt-0.5" /> Share, then <strong>Add to Home Screen</strong>
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">Open your report straight from your home screen</p>
        )}
      </div>
      {!ios && (
        <button
          onClick={promptInstall}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"
          data-testid="install-app-button"
        >
          <Download className="w-3.5 h-3.5" /> Install
        </button>
      )}
      <button onClick={dismiss} aria-label="Dismiss" className="shrink-0 p-1 text-muted-foreground hover:text-foreground">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
