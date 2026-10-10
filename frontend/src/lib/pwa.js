// Installable-app (PWA) helpers.
//
// The installed app opens at /my, which forwards to the report token saved on
// this device. iPhone home-screen apps never receive WhatsApp links (they open in
// Safari, whose storage is separate), so the app signs in with the 6-digit code
// the REPORT reply includes (POST /portal/pair → 30-day token).

import { useEffect, useState } from "react";

const TOKEN_KEY = "klpit.reportToken";
export const WHATSAPP_REPORT_URL = "https://wa.me/27655615874?text=REPORT";

export function saveReportToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* private mode */ }
}

export function getReportToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function clearReportToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
}

export function isStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

export function isIOS() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

// Chrome fires beforeinstallprompt once, often before React mounts — capture it at import time.
let deferredPrompt = null;
const listeners = new Set();
if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    listeners.forEach((fn) => fn(true));
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    listeners.forEach((fn) => fn(false));
  });
}

// { canPrompt, promptInstall } — canPrompt is true on Android/desktop Chrome when installable.
export function useInstallPrompt() {
  const [canPrompt, setCanPrompt] = useState(!!deferredPrompt);
  useEffect(() => {
    listeners.add(setCanPrompt);
    return () => listeners.delete(setCanPrompt);
  }, []);
  const promptInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    setCanPrompt(false);
  };
  return { canPrompt, promptInstall };
}
