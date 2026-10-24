import { motion } from "framer-motion";
import { Award, BriefcaseMedical, CalendarClock, House, Languages, MapPin, Sparkles, Video, Building2 } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { kmLabel, slotLabel } from "../lib/format.js";
import { Avatar, ScoreBar, Stars } from "./ui.jsx";

const MODE_ICON = { home_visit: House, teleconsult: Video, clinic: Building2 };

function skillLabel(s) {
  return s.replace(/_/g, " ");
}

/**
 * One caregiver. With `match` it shows rank, match score and the "why this match" reason from the API;
 * without it (directory), just the profile.
 */
export default function CaregiverCard({ cg, match, rank, distanceKm, slot, onBook, teleconsult = false, index = 0, highlight = false }) {
  const { t, lang } = useApp();
  if (!cg) return null;
  const top = rank === 1;
  const modes = cg.consultation_modes?.length ? cg.consultation_modes : [teleconsult ? "teleconsult" : "home_visit"];
  const shownSkills = (cg.skills || []).filter((s) => s !== cg.specialty).slice(0, 4);
  return (
    <motion.article id={`cg-${cg.caregiver_id}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.25 }}
      className={`card flex flex-col p-5 transition-shadow ${top ? "border-2 border-primary shadow-lift" : ""} ${highlight ? "ring-4 ring-accent/60" : ""}`}
      aria-label={cg.name}>
      <div className="flex items-start gap-4">
        <div className="relative">
          <Avatar name={cg.name.replace(/^Dr\.\s*/, "")} seed={parseInt(cg.caregiver_id.replace(/\D/g, ""), 10) || 0} />
          {rank && (
            <span className={`absolute -left-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold ${top ? "bg-accent text-white" : "bg-ink text-bg"}`}
              aria-label={`${t("common.rank")} ${rank}`}>{rank}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          {top && match && <p className="mb-0.5 text-xs font-bold uppercase tracking-wider text-accent">{t("result.bestHere")}</p>}
          <h3 className="font-sans text-lg font-bold leading-tight">{cg.name}</h3>
          <p className="text-muted">
            {t(`roles.${cg.role}`)}{cg.specialty ? ` · ${t(`specialty.${cg.specialty}`)}` : ""}
          </p>
          <div className="mt-1"><Stars rating={cg.rating} /></div>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.away")}</dt>
          <dd className="font-semibold">
            {teleconsult ? t("result.teleconsult") : distanceKm != null ? `${kmLabel(distanceKm, t)} ${t("common.away")}` : "—"}
            {cg.locality && <span className="block text-xs font-normal text-muted">{cg.locality}</span>}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.nextFree")}</dt>
          <dd><span className="block text-xs text-muted">{t("common.nextFree")}</span><span className="font-semibold">{slotLabel(slot, t, lang)}</span></dd>
        </div>
        {cg.qualification && (
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            <dt className="sr-only">{t("card.qualification")}</dt>
            <dd>{cg.qualification}</dd>
          </div>
        )}
        {cg.years_experience != null && (
          <div className="flex items-center gap-2">
            <BriefcaseMedical className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            <dt className="sr-only">{t("card.experience", { n: "" })}</dt>
            <dd>{t("card.experience", { n: cg.years_experience })}</dd>
          </div>
        )}
        <div className="flex items-start gap-2 sm:col-span-2">
          <Languages className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <dt className="sr-only">{t("common.languages")}</dt>
          <dd>{(cg.languages || []).map((l) => t(`langNames.${l}`)).join(", ")}</dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <span className="sr-only">{t("card.mode")}:</span>
        {modes.map((m) => {
          const Icon = MODE_ICON[m] || House;
          return (
            <span key={m} className="inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary-soft/60 px-2 py-0.5 text-xs font-bold text-primary-deep">
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />{t(`modes.${m}`)}
            </span>
          );
        })}
        {shownSkills.map((s) => (
          <span key={s} className="rounded-md bg-sunken px-2 py-0.5 text-xs font-semibold capitalize text-ink/80">{skillLabel(s)}</span>
        ))}
      </div>

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
