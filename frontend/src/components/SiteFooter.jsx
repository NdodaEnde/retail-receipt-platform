import { Link } from "react-router-dom";
import { APP_URL, JOIN_WHATSAPP_URL } from "../lib/site";

// Public footer for the marketing site. Staff login lives here, out of the customer's way.
export default function SiteFooter() {
  return (
    <footer className="border-t border-white/10 px-6 py-10 text-sm text-muted-foreground" data-testid="site-footer">
      <div className="max-w-6xl mx-auto grid gap-8 sm:grid-cols-3">
        <div className="space-y-2">
          <p className="font-heading text-lg font-bold text-foreground">KlpIT</p>
          <p>Win back what you spend. A free receipt wallet with a daily prize, on WhatsApp.</p>
        </div>
        <nav className="space-y-2" aria-label="Customers">
          <p className="font-semibold text-foreground">Customers</p>
          <a href={JOIN_WHATSAPP_URL} className="block hover:text-foreground">Join on WhatsApp</a>
          <a href={APP_URL} className="block hover:text-foreground">My report</a>
          <a href="/#faq" className="block hover:text-foreground">FAQ</a>
        </nav>
        <nav className="space-y-2" aria-label="Legal">
          <p className="font-semibold text-foreground">KlpIT</p>
          <Link to="/rules" className="block hover:text-foreground">Competition rules</Link>
          <Link to="/privacy" className="block hover:text-foreground">Privacy policy</Link>
          <a href="mailto:info@klpit.co.za" className="block hover:text-foreground">info@klpit.co.za</a>
        </nav>
      </div>
      <div className="max-w-6xl mx-auto mt-8 pt-6 border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <p>© {new Date().getFullYear()} KlpIT. All rights reserved.</p>
        <Link to="/login" className="hover:text-foreground" data-testid="staff-login-link">Staff login</Link>
      </div>
    </footer>
  );
}
