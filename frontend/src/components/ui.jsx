import { AlertCircle, Inbox, RefreshCw, Star } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { CARE_ICON, URGENCY_STYLE } from "../lib/care.js";

export function UrgencyBadge({ urgency, size = "md", compact = false }) {
  const { t } = useApp();
  const s = URGENCY_STYLE[urgency];
  if (!s) return null;
  const Icon = s.icon;
  const pad = size === "lg" ? "px-4 py-2 text-base" : "px-3 py-1 text-sm";
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-1.5 rounded-full border font-bold ${s.chip} ${pad}`}>
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
        <Icon className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} aria-hidden="true" />
        {t(`urgency.${urgency}.label`)}
      </span>
      {!compact && <span className="whitespace-nowrap font-semibold opacity-80">· {t(`urgency.${urgency}.desc`)}</span>}
    </span>
  );
}

export function CareGlyph({ careType, className = "h-12 w-12", iconClass = "h-6 w-6" }) {
  const Icon = CARE_ICON[careType];
  const emergency = careType === "emergency_referral";
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-2xl ${emergency ? "bg-emergency-soft text-emergency" : "bg-primary-soft text-primary-deep"} ${className}`}>
      {Icon && <Icon className={iconClass} aria-hidden="true" />}
    </span>
  );
}

const AVATAR_TONES = ["bg-primary-soft text-primary-deep", "bg-accent-soft text-[rgb(140_70_10)]", "bg-routine-soft text-routine", "bg-sunken text-ink"];

export function Avatar({ name = "?", seed = 0, className = "h-14 w-14 text-lg" }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full font-display font-semibold ${AVATAR_TONES[seed % AVATAR_TONES.length]} ${className}`} aria-hidden="true">
      {initials || "?"}
    </span>
  );
}

export function Stars({ rating = 0 }) {
  const { t } = useApp();
  const full = Math.round(rating);
  return (
    <span className="inline-flex items-center gap-1" aria-label={`${t("common.rating")} ${rating} / 5`}>
      <span className="inline-flex" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star key={i} className={`h-4 w-4 ${i <= full ? "fill-accent text-accent" : "text-line"}`} />
        ))}
      </span>
      <span className="text-sm font-bold">{Number(rating).toFixed(1)}</span>
    </span>
  );
}

export function ScoreBar({ score }) {
  const { t } = useApp();
  const pct = Math.round((score || 0) * 100);
  return (
    <div className="w-full" aria-label={`${t("result.matchScore")} ${pct}%`}>
      <div className="mb-1 flex justify-between text-xs font-semibold text-muted">
        <span>{t("result.matchScore")}</span><span className="text-ink">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-sunken">
        <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-xl bg-sunken ${className}`} aria-hidden="true" />;
}

export function ErrorState({ message, onRetry }) {
  const { t } = useApp();
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl2 border border-emergency/40 bg-emergency-soft p-4 text-emergency-deep">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-semibold">{message || t("common.serverDown")}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="mt-2 inline-flex min-h-[44px] items-center gap-2 font-bold underline">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />{t("common.retry")}
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, hint, children }) {
  return (
    <div className="flex flex-col items-center rounded-xl2 border border-dashed border-line bg-surface/60 px-6 py-12 text-center">
      <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-sunken text-muted"><Icon className="h-7 w-7" aria-hidden="true" /></span>
      <p className="text-lg font-semibold">{title}</p>
      {hint && <p className="mt-1 max-w-md text-muted">{hint}</p>}
      {children && <div className="mt-5">{children}</div>}
    </div>
  );
}

export function Spinner({ className = "h-4 w-4" }) {
  return <span className={`inline-block animate-spin rounded-full border-2 border-current border-r-transparent ${className}`} aria-hidden="true" />;
}
