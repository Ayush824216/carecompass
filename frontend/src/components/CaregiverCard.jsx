import { motion } from "framer-motion";
import { CalendarClock, Languages, MapPin, Sparkles } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { kmLabel, slotLabel } from "../lib/format.js";
import { Avatar, ScoreBar, Stars } from "./ui.jsx";

function skillLabel(s) {
  return s.replace(/_/g, " ");
}

/**
 * One caregiver. With `match` it shows rank, match score and the "why this match" reason from the API;
 * without it (directory), just the profile.
 */
export default function CaregiverCard({ cg, match, rank, distanceKm, slot, onBook, teleconsult = false, index = 0 }) {
  const { t, lang } = useApp();
  if (!cg) return null;
  const top = rank === 1;
  return (
    <motion.article initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06, duration: 0.25 }}
      className={`card flex flex-col p-5 ${top ? "border-2 border-primary shadow-lift" : ""}`} aria-label={cg.name}>
      <div className="flex items-start gap-4">
        <div className="relative">
          <Avatar name={cg.name} seed={parseInt(cg.caregiver_id.replace(/\D/g, ""), 10) || 0} />
          {rank && (
            <span className={`absolute -left-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold ${top ? "bg-accent text-white" : "bg-ink text-bg"}`}
              aria-label={`${t("common.rank")} ${rank}`}>{rank}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-sans text-lg font-bold leading-tight">{cg.name}</h3>
          <p className="text-muted">{t(`roles.${cg.role}`)}</p>
          <div className="mt-1"><Stars rating={cg.rating} /></div>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.away")}</dt>
          <dd className="font-semibold">{teleconsult ? t("result.teleconsult") : distanceKm != null ? `${kmLabel(distanceKm, t)} ${t("common.away")}` : "—"}</dd>
        </div>
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.nextFree")}</dt>
          <dd className="font-semibold">{slotLabel(slot, t, lang)}</dd>
        </div>
        <div className="flex items-start gap-2 sm:col-span-2">
          <Languages className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.languages")}</dt>
          <dd>{(cg.languages || []).map((l) => t(`langNames.${l}`)).join(", ")}</dd>
        </div>
      </dl>

      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("common.skills")}>
        {(cg.skills || []).slice(0, 4).map((s) => (
          <li key={s} className="rounded-md bg-sunken px-2 py-0.5 text-xs font-semibold capitalize text-ink/80">{skillLabel(s)}</li>
        ))}
      </ul>

      {match && (
        <>
          <div className="mt-4"><ScoreBar score={match.score} /></div>
          <div className="mt-4 rounded-xl bg-primary-soft/50 px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-primary-deep">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />{t("result.why")}
            </p>
            <p className="mt-0.5 text-[0.95rem]">{match.reason}</p>
          </div>
        </>
      )}

      {onBook && <div className="h-5" aria-hidden="true" />}
      {onBook && (
        <button type="button" onClick={() => onBook(cg)} className="btn-primary mt-auto w-full text-lg">
          {t("result.book")}
        </button>
      )}
    </motion.article>
  );
}
