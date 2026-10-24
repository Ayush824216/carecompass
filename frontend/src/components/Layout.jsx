import { useEffect, useRef, useState } from "react";
import { ConsentNotice, ModeToggle } from "./Privacy.jsx";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Contrast, Github, Menu, Minus, Phone, Plus, SlidersHorizontal, Volume2, VolumeX, X, XCircle } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { API_BASE } from "../lib/api.js";

/** Brand mark: a medical cross inside a location pin ("care" + "near you"). */
export function Logo({ className = "h-9 w-9" }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <path d="M20 2C11.7 2 5 8.6 5 16.8 5 27.4 20 38 20 38s15-10.6 15-21.2C35 8.6 28.3 2 20 2z" className="fill-primary" />
      <path d="M17.4 9h5.2v5.2h5.2v5.2h-5.2v5.2h-5.2v-5.2h-5.2v-5.2h5.2z" fill="white" />
    </svg>
  );
}

/** Assistant avatar: the brand mark on a soft mint circle. */
export function BrandAvatar({ className = "h-9 w-9" }) {
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full bg-primary-soft ring-1 ring-primary/15 ${className}`} aria-hidden="true">
      <Logo className="h-[62%] w-[62%]" />
    </span>
  );
}

export function EmergencyButton({ compact = false }) {
  const { t } = useApp();
  return (
    <a href="tel:112" className="btn-emergency px-3 sm:px-4 shrink-0" aria-label={t("nav.emergencyAria")}>
      <Phone className="h-5 w-5" aria-hidden="true" />
      <span className={compact ? "hidden sm:inline" : ""}>{t("nav.emergency")}</span>
    </a>
  );
}

export function LanguageToggle() {
  const { t, lang, setLang } = useApp();
  return (
    <button type="button" onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label={t("meta.otherLangLabel")}
      className="btn-ghost px-3 min-w-[48px] font-semibold" lang={lang === "en" ? "hi" : "en"}>
      {t("meta.otherLang")}
    </button>
  );
}

export function TextSizeControl() {
  const { t, grow, shrink, canGrow, canShrink } = useApp();
  return (
    <div className="flex items-center rounded-xl border border-line bg-surface" role="group" aria-label={t("nav.textSize")}>
      <button type="button" onClick={shrink} disabled={!canShrink} aria-label={t("nav.textSmaller")}
        className="flex h-12 w-11 items-center justify-center rounded-l-xl hover:bg-sunken disabled:opacity-40">
        <Minus className="h-4 w-4" aria-hidden="true" /><span className="text-sm font-bold">A</span>
      </button>
      <span className="h-6 w-px bg-line" aria-hidden="true" />
      <button type="button" onClick={grow} disabled={!canGrow} aria-label={t("nav.textLarger")}
        className="flex h-12 w-11 items-center justify-center rounded-r-xl hover:bg-sunken disabled:opacity-40">
        <span className="text-lg font-bold">A</span><Plus className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export function ContrastToggle() {
  const { t, contrast, setContrast } = useApp();
  return (
    <button type="button" onClick={() => setContrast(!contrast)} aria-pressed={contrast} aria-label={t("nav.contrast")}
      title={t("nav.contrast")}
      className={`flex h-12 w-12 items-center justify-center rounded-xl border ${contrast ? "border-ink bg-ink text-bg" : "border-line bg-surface hover:bg-sunken"}`}>
      <Contrast className="h-5 w-5" aria-hidden="true" />
    </button>
  );
}

export function VoiceToggle({ withLabel = false }) {
  const { t, voice, setVoice } = useApp();
  const Icon = voice ? Volume2 : VolumeX;
  return (
    <button type="button" onClick={() => setVoice(!voice)} aria-pressed={voice} aria-label={t("nav.voiceAria")}
      title={voice ? t("nav.voiceOn") : t("nav.voiceOff")}
      className={`flex h-12 items-center justify-center gap-2 rounded-xl border px-3 ${voice ? "border-primary/40 bg-primary-soft text-primary-deep" : "border-line bg-surface text-muted"}`}>
      <Icon className="h-5 w-5" aria-hidden="true" />
      {withLabel && <span className="text-sm font-semibold">{voice ? t("nav.voiceOn") : t("nav.voiceOff")}</span>}
    </button>
  );
}

/** Text size, contrast and voice in one popover so the desktop navbar stays on one line. */
function DisplayMenu() {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="true" aria-label={t("nav.settings")}
        className="btn-ghost px-3">
        <SlidersHorizontal className="h-5 w-5" aria-hidden="true" />
        <span className="hidden 2xl:inline">{t("nav.settings")}</span>
      </button>
      {open && (
        <div className="card absolute right-0 top-[calc(100%+8px)] z-50 w-72 space-y-4 p-4 shadow-lift" role="group" aria-label={t("nav.settings")}>
          <div>
            <p className="eyebrow mb-2">{t("nav.textSize")}</p>
            <TextSizeControl />
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="font-semibold">{t("nav.contrast")}</span>
            <ContrastToggle />
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="font-semibold">{t("nav.voiceAria")}</span>
            <VoiceToggle />
          </div>
        </div>
      )}
    </div>
  );
}

const LINKS = [
  ["/care", "nav.getCare"], ["/caregivers", "nav.caregivers"], ["/how-it-works", "nav.how"],
  ["/developers", "nav.developers"], ["/bookings", "nav.bookings"], ["/memory", "nav.memory"],
];

function useViewportWidth() {
  const [w, setW] = useState(() => window.innerWidth);
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

function Navbar() {
  const { t, bookings, basePx } = useApp();
  const [open, setOpen] = useState(false);
  // breakpoints scale with the chosen text size, so large text collapses the nav instead of overflowing
  const vw = useViewportWidth();
  const scale = basePx / 18;
  const fullNav = vw >= 1280 * scale;
  const showControls = vw >= 1024 * scale;
  const showWordmark = vw >= 360 * scale;
  const loc = useLocation();
  useEffect(() => { setOpen(false); }, [loc.pathname]);

  const linkCls = ({ isActive }) =>
    `relative whitespace-nowrap rounded-lg px-2.5 py-2 font-semibold transition-colors ${isActive ? "text-primary-deep bg-primary-soft" : "text-ink/80 hover:text-ink hover:bg-sunken"}`;

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/95 backdrop-blur">
      <div className="container-page flex h-[72px] items-center gap-3">
        <Link to="/" className="flex items-center gap-2.5 rounded-lg pr-2" aria-label={t("meta.homeAria")}>
          <Logo />
          {showWordmark && <span className="font-display text-xl font-bold tracking-tight">{t("meta.brandA")}<span className="text-primary">{t("meta.brandB")}</span></span>}
        </Link>
        {fullNav && <nav className="ml-4 flex items-center gap-1" aria-label="Main">
          {LINKS.map(([to, key]) => (
            <NavLink key={to} to={to} className={linkCls}>
              {t(key)}
              {to === "/bookings" && bookings.length > 0 && (
                <span className="ml-1.5 rounded-full bg-accent px-1.5 text-xs font-bold text-white">{bookings.length}</span>
              )}
            </NavLink>
          ))}
        </nav>}
        <div className="ml-auto flex items-center gap-2">
          {fullNav && <ModeToggle />}
          {showControls && (
            <div className="flex items-center gap-2">
              <DisplayMenu />
              <LanguageToggle />
            </div>
          )}
          <EmergencyButton compact />
          {!fullNav && <button type="button" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-line bg-surface"
            onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-nav" aria-label={open ? t("nav.closeMenu") : t("nav.menu")}>
            {open ? <X className="h-6 w-6" aria-hidden="true" /> : <Menu className="h-6 w-6" aria-hidden="true" />}
          </button>}
        </div>
      </div>
      <AnimatePresence>
        {open && !fullNav && (
          <motion.div id="mobile-nav" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-line bg-bg">
            <nav className="container-page flex flex-col gap-1 py-3" aria-label="Mobile">
              {LINKS.map(([to, key]) => (
                <NavLink key={to} to={to} className={({ isActive }) => `${linkCls({ isActive })} min-h-[48px] flex items-center`}>{t(key)}</NavLink>
              ))}
              <div className="mt-2 border-t border-line pt-3"><ModeToggle /></div>
              {!showControls && <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                <span className="eyebrow w-full">{t("nav.settings")}</span>
                <TextSizeControl />
                <ContrastToggle />
                <VoiceToggle withLabel />
                <LanguageToggle />
              </div>}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

function Footer() {
  const { t } = useApp();
  return (
    <footer className="mt-24 border-t border-line bg-sunken/60">
      <div className="container-page grid gap-10 py-12 md:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5"><Logo className="h-8 w-8" /><span className="font-display text-lg font-bold">{t("meta.brandA")}<span className="text-primary">{t("meta.brandB")}</span></span></div>
          <p className="mt-3 max-w-md text-muted">{t("footer.tagline")}</p>
          <p className="mt-5 text-sm font-semibold">{t("footer.team")}</p>
          <p className="text-sm text-muted">{t("footer.event")}</p>
        </div>
        <div>
          <h2 className="eyebrow mb-3 font-sans">{t("footer.explore")}</h2>
          <ul className="space-y-2">
            {LINKS.map(([to, key]) => <li key={to}><Link to={to} className="hover:text-primary hover:underline">{t(key)}</Link></li>)}
          </ul>
        </div>
        <div>
          <h2 className="eyebrow mb-3 font-sans">{t("footer.resources")}</h2>
          <ul className="space-y-2">
            <li><a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="hover:text-primary hover:underline">{t("footer.apiDocs")}</a></li>
            <li><a href="https://github.com/Ayush824216/carecompass" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-primary hover:underline">
              <Github className="h-4 w-4" aria-hidden="true" />{t("footer.github")}</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="container-page space-y-2 py-6 text-sm text-muted">
          <p className="font-semibold text-ink">{t("footer.disclaimer")}</p>
          <p>{t("footer.dpdp")}</p>
          <p><span className="font-semibold text-ink">{t("footer.sources")}:</span> {t("footer.sourcesNote")} · <a href="/how-it-works" className="underline hover:text-primary">{t("nav.how")}</a></p>
        </div>
      </div>
    </footer>
  );
}

function Toasts() {
  const { toasts, dismissToast, t } = useApp();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
      <AnimatePresence>
        {toasts.map((x) => (
          <motion.div key={x.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}
            className="pointer-events-auto card flex items-start gap-3 p-4 shadow-lift">
            {x.tone === "error"
              ? <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-emergency" aria-hidden="true" />
              : <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-routine" aria-hidden="true" />}
            <p className="flex-1 font-semibold">{x.message}</p>
            <button type="button" onClick={() => dismissToast(x.id)} aria-label={t("common.close")} className="-m-2 p-2 text-muted hover:text-ink">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export default function Layout() {
  const { t } = useApp();
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 btn-primary">{t("nav.skip")}</a>
      <Navbar />
      <main id="main" className="flex-1">
        <Outlet />
        <ConsentNotice />
      </main>
      <Footer />
      <Toasts />
    </div>
  );
}
