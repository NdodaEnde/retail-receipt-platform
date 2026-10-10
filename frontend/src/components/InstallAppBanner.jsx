import { useState } from "react";
import { Compass, Download, PlusSquare, Share, X } from "lucide-react";
import { isIOS, isStandalone, useInstallPrompt } from "../lib/pwa";

const DISMISS_KEY = "klpit.installDismissed";

// iOS never lets a website trigger installation, and WhatsApp's in-app browser
// has no "Add to Home Screen" — so on iPhone the button opens a step-by-step guide.
const IOS_STEPS = [
  { icon: Compass, text: <>Opened from WhatsApp? Tap the <strong>Safari</strong> compass icon (or ••• → <strong>Open in Safari</strong>) first</> },
  { icon: Share, text: <>In Safari, tap <strong>Share</strong> at the bottom of the screen</> },
  { icon: PlusSquare, text: <>Scroll down and tap <strong>Add to Home Screen</strong> (may be under <strong>View More</strong>)</> },
  { icon: Download, text: <>Tap <strong>Add</strong> — KlpIT appears on your home screen</> },
];

export default function InstallAppBanner() {
  const { canPrompt, promptInstall } = useInstallPrompt();
  const [showSteps, setShowSteps] = useState(false);
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
    <div className="glass border border-primary/30 rounded-xl p-3 space-y-3" data-testid="install-app-banner">
      <div className="flex items-center gap-3">
        <img src="/icon-192.png" alt="" className="w-10 h-10 rounded-lg shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">Get the KlpIT app</p>
          <p className="text-xs text-muted-foreground">Open your report straight from your home screen</p>
        </div>
        <button
          onClick={ios ? () => setShowSteps((s) => !s) : promptInstall}
          className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"
          data-testid="install-app-button"
        >
          <Download className="w-3.5 h-3.5" /> {ios && showSteps ? "Hide" : "Install"}
        </button>
        <button onClick={dismiss} aria-label="Dismiss" className="shrink-0 p-1 text-muted-foreground hover:text-foreground">
          <X className="w-4 h-4" />
        </button>
      </div>
      {ios && showSteps && (
        <ol className="space-y-2 border-t border-white/10 pt-3" data-testid="ios-install-steps">
          {IOS_STEPS.map(({ icon: Icon, text }, i) => (
            <li key={i} className="flex items-start gap-3 text-xs text-muted-foreground">
              <span className="shrink-0 w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center font-semibold">{i + 1}</span>
              <Icon className="shrink-0 w-4 h-4 mt-1 text-foreground" />
              <span className="pt-0.5">{text}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
