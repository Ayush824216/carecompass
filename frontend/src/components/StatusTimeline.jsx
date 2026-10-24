import { Check, ClipboardCheck, House, MapPin, UserCheck } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";

export const STATUS_KEYS = ["booked", "assigned", "onTheWay", "arrived"];
const ICONS = [ClipboardCheck, UserCheck, MapPin, House];

/** Mock visit tracker. `current` is the index of the latest reached step. */
export default function StatusTimeline({ current = 0, compact = false }) {
  const { t } = useApp();
  return (
    <ol className={`grid gap-3 ${compact ? "grid-cols-4" : "sm:grid-cols-4"}`} aria-label={t("booking.track")}>
      {STATUS_KEYS.map((k, i) => {
        const Icon = ICONS[i];
        const done = i <= current;
        const now = i === current;
        return (
          <li key={k} className={`relative flex items-center gap-3 ${compact ? "flex-col text-center" : "sm:flex-col sm:text-center"}`}
            aria-current={now ? "step" : undefined}>
            {i < STATUS_KEYS.length - 1 && (
              <span className={`absolute hidden ${compact ? "block" : "sm:block"} left-[calc(50%+24px)] right-[calc(-50%+24px)] top-5 h-0.5 ${i < current ? "bg-routine" : "bg-line"}`} aria-hidden="true" />
            )}
            <span className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 ${done ? "border-routine bg-routine text-white" : "border-line bg-surface text-muted"} ${now ? "ring-4 ring-routine/20" : ""}`}>
              {done && !now ? <Check className="h-5 w-5" aria-hidden="true" /> : <Icon className="h-5 w-5" aria-hidden="true" />}
            </span>
            <span className={`text-sm font-semibold ${done ? "text-ink" : "text-muted"}`}>
              {t(`booking.status.${k}`)}
              <span className="sr-only">{done ? ` (${t("booking.stepDone")})` : ""}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
