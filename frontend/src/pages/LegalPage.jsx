import { Link } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import SiteFooter from "../components/SiteFooter";
import { JOIN_WHATSAPP_URL } from "../lib/site";

const PAGES = {
  rules: {
    title: "Competition rules",
    intro: "The full rules of the KlpIT daily draw — how to enter, how winners are chosen and paid, and who may take part — are being finalised.",
  },
  privacy: {
    title: "Privacy policy",
    intro: "Our full privacy policy — what we collect, why, how long we keep it and your rights under POPIA — is being finalised.",
  },
};

// Holding page until the lawyer-reviewed text is ready. Never put draft legal wording here.
export default function LegalPage({ page }) {
  const { title, intro } = PAGES[page];
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 max-w-2xl mx-auto px-6 py-16 space-y-6" data-testid={`legal-${page}`}>
        <Link to="/" className="font-heading text-lg font-bold">KlpIT</Link>
        <h1 className="font-heading text-3xl font-bold">{title}</h1>
        <p className="text-muted-foreground">{intro}</p>
        <p className="text-muted-foreground">
          Questions in the meantime? Message us on WhatsApp or email{" "}
          <a href="mailto:info@klpit.co.za" className="underline">info@klpit.co.za</a>.
        </p>
        <a href={JOIN_WHATSAPP_URL} className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 font-semibold text-primary-foreground">
          <MessageCircle className="w-4 h-4" /> WhatsApp us
        </a>
      </main>
      <SiteFooter />
    </div>
  );
}
