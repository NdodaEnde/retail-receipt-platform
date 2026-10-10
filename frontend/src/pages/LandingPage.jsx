import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Trophy, PiggyBank, Wallet, MessageCircle, Camera, Sparkles, Gift, Scale, ShieldCheck,
  ArrowRight, FileText,
} from "lucide-react";
import axios from "axios";
import { API } from "../App";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import SiteFooter from "../components/SiteFooter";
import { APP_URL, JOIN_WHATSAPP_URL } from "../lib/site";

// Keeps the stat tiles one line wide on small phones as totals grow: 9 850, 37k, 1.2m
const shortRand = (v) =>
  v >= 1e6 ? `${(v / 1e6).toFixed(1)}m` : v >= 1e4 ? `${Math.round(v / 1e3)}k` : Math.round(v).toLocaleString("en-ZA");

// Copy rules: shoppers only (no retailer/brand pitch yet); never "track"; location is
// explained once, honestly, in the FAQ — it is not a feature. Every claim must be true today.
const PROMISES = [
  { icon: Gift, title: "Free", text: "No fees and no subscriptions. All you need is WhatsApp and a till slip." },
  { icon: Scale, title: "Fair", text: "One winner every night at 21:00, picked at random. Every receipt is one equal chance." },
  { icon: ShieldCheck, title: "Private", text: "Your details are protected under POPIA and never shown publicly. Your report opens only with a link or code sent to your own WhatsApp." },
];

const PRODUCTS = [
  { icon: Trophy, title: "Win daily", text: "Every receipt you send enters that night's draw. If yours is picked, you win back the full amount of that receipt." },
  { icon: PiggyBank, title: "Know your spending", text: "See where your money goes each month — your shops, your biggest baskets, what you buy most. Small insights that make budgeting easier." },
  { icon: Wallet, title: "Keep every receipt", text: "No more faded till slips. Every receipt you send is kept safe in one place — handy for returns, warranties and budgeting." },
];

const STEPS = [
  { icon: MessageCircle, title: "Say Hi on WhatsApp", text: "Tap Join, send “Hi”, and register with your name. It takes a minute." },
  { icon: Camera, title: "Send your till slip", text: "Take a clear photo of your receipt after you shop and send it to KlpIT." },
  { icon: Sparkles, title: "Win at 21:00", text: "One receipt wins every night. If it's yours, we'll tell you on WhatsApp." },
];

const COMMANDS = [
  ["REPORT", "your spending report"],
  ["RECEIPTS", "your recent receipts"],
  ["WINS", "your winnings"],
  ["STATUS", "tonight's draw"],
  ["BALANCE", "your totals"],
  ["HELP", "all options"],
];

const FAQ = [
  ["Is it really free?", "Yes. Entering costs nothing. You only need WhatsApp and a till slip from your shopping."],
  ["How is the winner chosen?", "Every night at 21:00 our system picks one receipt at random from that day's valid entries. Each receipt is one entry, so every receipt has the same chance."],
  ["How much can I win?", "The full amount of your winning receipt — what you spent comes back to you."],
  ["Why does KlpIT ask where I am when I send a receipt?", "When you send a receipt, WhatsApp shows a button to share your location for that receipt only. We use it to check the receipt is genuine, which keeps the draw fair for everyone. Your location is never shown publicly."],
  ["What happens to my information?", "We use your name, number and receipts to run the draw and to show you your own spending. Your details are never shown publicly, and your report opens only with a private link or code sent to your own WhatsApp. Our privacy policy explains this in full."],
  ["How do I see my receipts and spending?", "Send REPORT to KlpIT on WhatsApp and open the link, or open the KlpIT app if you've added it to your home screen."],
];

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.4 },
};

function JoinButton({ testId }) {
  return (
    <a
      href={JOIN_WHATSAPP_URL}
      data-testid={testId}
      className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-8 py-4 text-lg font-bold text-primary-foreground glow-primary hover:scale-105 transition-transform"
    >
      Join on WhatsApp <ArrowRight className="w-5 h-5" />
    </a>
  );
}

function QrCard() {
  // Desktop visitors can't tap a wa.me link — they scan this with their phone.
  return (
    <div className="hidden md:flex items-center gap-4 glass rounded-2xl p-4 text-left" data-testid="join-qr">
      <img src="/join-whatsapp-qr.png" alt="QR code to join KlpIT on WhatsApp" className="w-24 h-24 rounded-lg bg-white p-1" />
      <p className="text-sm text-muted-foreground max-w-[10rem]">On a computer? Scan with your phone's camera to join.</p>
    </div>
  );
}

export default function LandingPage() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    axios.get(`${API}/stats/public`)
      .then((res) => setStats(res.data))
      .catch((error) => console.error("Failed to fetch stats:", error));
  }, []);

  return (
    <div className="min-h-screen" data-testid="landing-page">
      {/* Header */}
      <header className="sticky top-0 z-40 glass border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <a href="/" className="font-heading text-xl font-bold tracking-tight">Klp<span className="text-primary">IT</span></a>
          <nav className="hidden md:flex items-center gap-6 text-sm text-muted-foreground" aria-label="Main">
            <a href="#how" className="hover:text-foreground">How it works</a>
            <a href="#customers" className="hover:text-foreground">For customers</a>
            <a href="#faq" className="hover:text-foreground">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            <a href={APP_URL} className="hidden sm:inline-flex rounded-full px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground" data-testid="header-my-report">
              My report
            </a>
            <a href={JOIN_WHATSAPP_URL} className="inline-flex rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground" data-testid="header-join">
              Join
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden px-6 pt-16 pb-20 sm:pt-24">
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-glow rounded-full opacity-30 pointer-events-none" />
        <div className="relative max-w-4xl mx-auto text-center">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass text-sm font-medium text-primary mb-6">
              <Sparkles className="w-4 h-4" /> Daily prize draw · 21:00
            </span>
            <h1 className="font-heading text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              <span className="text-gradient">Win Back</span>
              <br />
              <span className="text-gradient-primary">What You Spend</span>
            </h1>
            <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              Send a photo of your till slip on WhatsApp. Every night one receipt wins its full amount back —
              and every receipt you send is kept safe, with a clear picture of your spending.
            </p>
            <div className="flex flex-col md:flex-row items-center justify-center gap-6">
              <JoinButton testId="get-started-btn" />
              <QrCard />
            </div>
          </motion.div>

          {stats && (
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="mt-16 grid grid-cols-2 gap-3 sm:gap-6 max-w-md mx-auto"
            >
              <div className="glass-card rounded-2xl px-2 py-4 min-[400px]:p-4 sm:p-6">
                <p className="font-mono text-xl min-[400px]:text-2xl sm:text-3xl font-bold text-primary">{stats.total_receipts.toLocaleString("en-ZA")}</p>
                <p className="text-sm text-muted-foreground mt-1">Receipts Processed</p>
              </div>
              <div className="glass-card rounded-2xl px-2 py-4 min-[400px]:p-4 sm:p-6">
                <p className="font-mono text-xl min-[400px]:text-2xl sm:text-3xl font-bold text-accent">R{shortRand(stats.total_winnings)}</p>
                <p className="text-sm text-muted-foreground mt-1">Won Back</p>
              </div>
            </motion.div>
          )}
        </div>
      </section>

      {/* Free. Fair. Private. */}
      <section className="px-6 py-20" data-testid="promises-section">
        <div className="max-w-6xl mx-auto">
          <motion.h2 {...fadeUp} className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-center mb-12">
            Free. Fair. <span className="text-primary">Private.</span>
          </motion.h2>
          <div className="grid gap-6 md:grid-cols-3">
            {PROMISES.map(({ icon: Icon, title, text }, i) => (
              <motion.div key={title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.1 }} className="glass-card rounded-2xl p-6">
                <Icon className="w-7 h-7 text-primary mb-4" />
                <h3 className="font-heading text-xl font-semibold mb-2">{title}</h3>
                <p className="text-sm text-muted-foreground">{text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="px-6 py-20" data-testid="features-section">
        <div className="max-w-6xl mx-auto">
          <motion.div {...fadeUp} className="text-center mb-12">
            <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight mb-4">More than a lucky draw</h2>
            <p className="text-muted-foreground max-w-xl mx-auto">Every receipt you send works for you — win or not.</p>
          </motion.div>
          <div className="grid gap-6 md:grid-cols-3">
            {PRODUCTS.map(({ icon: Icon, title, text }, i) => (
              <motion.div key={title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.1 }} className="glass-card rounded-2xl p-6 hover:border-primary/30 transition-colors">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  <Icon className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-heading text-lg font-semibold mb-2">{title}</h3>
                <p className="text-sm text-muted-foreground">{text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="px-6 py-20 scroll-mt-16" data-testid="how-section">
        <div className="max-w-4xl mx-auto">
          <motion.h2 {...fadeUp} className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-center mb-12">
            How it works
          </motion.h2>
          <ol className="grid gap-6 md:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <motion.li key={title} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.1 }} className="glass-card rounded-2xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <span className="w-8 h-8 rounded-full bg-primary text-primary-foreground font-bold flex items-center justify-center">{i + 1}</span>
                  <Icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="font-heading text-lg font-semibold mb-1">{title}</h3>
                <p className="text-sm text-muted-foreground">{text}</p>
              </motion.li>
            ))}
          </ol>
          <div className="text-center mt-10">
            <JoinButton testId="how-join" />
          </div>
        </div>
      </section>

      {/* Existing customers */}
      <section id="customers" className="px-6 py-20 scroll-mt-16" data-testid="customers-section">
        <motion.div {...fadeUp} className="max-w-4xl mx-auto glass-card rounded-3xl p-6 sm:p-10 grid gap-8 md:grid-cols-2">
          <div className="space-y-4">
            <h2 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Already with us?</h2>
            <p className="text-muted-foreground">
              Open your spending report and all your receipts. Add the KlpIT app to your phone's home screen to open it in one tap.
            </p>
            <a href={APP_URL} className="inline-flex items-center gap-2 rounded-full border border-white/20 px-6 py-3 font-semibold hover:bg-white/5" data-testid="open-my-report">
              <FileText className="w-4 h-4" /> Open my report
            </a>
          </div>
          <div>
            <p className="text-sm font-semibold mb-3">Send these words to KlpIT on WhatsApp:</p>
            <ul className="grid grid-cols-2 gap-2 text-sm">
              {COMMANDS.map(([cmd, what]) => (
                <li key={cmd} className="rounded-lg bg-white/5 px-3 py-2">
                  <span className="font-mono font-semibold text-primary">{cmd}</span>
                  <span className="block text-xs text-muted-foreground">{what}</span>
                </li>
              ))}
            </ul>
          </div>
        </motion.div>
      </section>

      {/* FAQ */}
      <section id="faq" className="px-6 py-20 scroll-mt-16" data-testid="faq-section">
        <div className="max-w-3xl mx-auto">
          <motion.h2 {...fadeUp} className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-center mb-10">
            Questions
          </motion.h2>
          <Accordion type="single" collapsible className="glass-card rounded-2xl px-6">
            {FAQ.map(([q, a], i) => (
              <AccordionItem key={q} value={`q${i}`} className="border-white/10 last:border-b-0">
                <AccordionTrigger className="text-base hover:no-underline">{q}</AccordionTrigger>
                <AccordionContent className="text-muted-foreground">{a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* Final call to action */}
      <section className="px-6 py-20 text-center">
        <motion.div {...fadeUp} className="max-w-2xl mx-auto space-y-6">
          <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight">Snap. Send. Win.</h2>
          <p className="text-muted-foreground">Your next till slip could come back to you tonight.</p>
          <JoinButton testId="final-join" />
        </motion.div>
      </section>

      <SiteFooter />
    </div>
  );
}
