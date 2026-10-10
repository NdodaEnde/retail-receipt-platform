// Installable-app (PWA) helpers.
//
// The installed app opens at /my, which forwards to the customer's last report
// link. Report tokens expire after 24h (portal_token.py), so an expired link
// lands on the "send REPORT on WhatsApp" screen — on Android, tapping the fresh
// link WhatsApp sends opens straight back inside the installed app.

import { useEffect, useState } from "react";

const TOKEN_KEY = "klpit.reportToken";
export const WHATSAPP_REPORT_URL = "https://wa.me/27655615874?text=REPORT";

export function saveReportToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* private mode */ }
}

export function getReportToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
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
