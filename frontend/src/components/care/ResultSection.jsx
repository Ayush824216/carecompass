import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, LayoutList, Map as MapIcon, MapPin, UsersRound } from "lucide-react";
import { useApp } from "../../context/AppContext.jsx";
import { api } from "../../lib/api.js";
import { haversineKm, kmLabel, nextSlot, slotLabel } from "../../lib/format.js";
import { inDelhiNcr, locationLabel, nearestLocality } from "../../lib/locations.js";
import NcrNotice from "../NcrNotice.jsx";
import BookingModal from "../BookingModal.jsx";
import AssessmentCard from "./AssessmentCard.jsx";
import CaregiverCard from "../CaregiverCard.jsx";
import CaregiverMap from "../CaregiverMap.jsx";
import { CareGlyph, EmptyState, Skeleton, UrgencyBadge } from "../ui.jsx";

/** "Skin specialists (dermatologists) near you (Saket)" etc. */
function heading(t, response, rows, location) {
  const ct = response.care_type;
  let h;
  if (ct === "specialist_referral") {
    const specs = rows.map((r) => r.cg?.specialty).filter(Boolean);
    const top = specs[0];
    h = top && specs.filter((s) => s === top).length >= Math.ceil(specs.length / 2)
      ? t("result.specialistHeading", { spec: t(`specialtyPlural.${top}`) }) : t("result.heading.specialist_referral");
  } else {
    h = t(`result.heading.${ct}`);
  }
  const place = location.lat != null && ct !== "gp_teleconsult"
    ? (location.label ? location.label.split(",")[0] : inDelhiNcr(location) ? nearestLocality(location.lat, location.lng)?.name : null)
    : null;
  return place ? `${h} ${t("result.inPlace", { place })}` : h;
}

export default function ResultSection({ response, debug }) {
  const { t, lang, location } = useApp();
  const reduce = useReducedMotion();
  const [details, setDetails] = useState({});
  const [view, setView] = useState("list");
  const [booking, setBooking] = useState(null);
  const [selected, setSelected] = useState(null);
  const sectionRef = useRef(null);
  const ids = useMemo(() => response.matched_caregivers.map((m) => m.caregiver_id), [response]);
  const tele = response.care_type === "gp_teleconsult";
  const serverRows = useMemo(() => Object.fromEntries((debug?.matching || []).map((m) => [m.caregiver_id, m])), [debug]);

  useEffect(() => {
    let alive = true;
    setDetails({});
    Promise.all(ids.map((id) => api.caregiver(id).catch(() => null))).then((list) => {
      if (alive) setDetails(Object.fromEntries(ids.map((id, i) => [id, list[i]])));
    });
    return () => { alive = false; };
  }, [ids]);

  // results sit below the chat: bring them into view once a decision arrives
  useEffect(() => {
    const id = setTimeout(() => sectionRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }), 900);
    return () => clearTimeout(id);
  }, [response, reduce]);

  const loaded = ids.every((id) => id in details);
  const rows = response.matched_caregivers.map((m, i) => {
    const cg = details[m.caregiver_id];
    const srv = serverRows[m.caregiver_id];
    const km = srv?.distance_km ?? (cg ? haversineKm(location, cg) : null);
    const slot = srv?.next_slot ? new Date(srv.next_slot) : cg ? nextSlot(cg, response.urgency) : null;
    return { m, cg, rank: i + 1, km, slot };
  });

  const select = (id) => {
    setSelected(id);
    document.getElementById(`cgl-${id}`)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  };

  return (
    <section ref={sectionRef} className="mt-10 scroll-mt-24 space-y-10" aria-labelledby="result-title">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        className="card grid gap-6 p-6 md:grid-cols-[1.5fr_1fr] md:p-8">
        <div>
          <p className="eyebrow mb-3">{t("result.title")}</p>
          <div className="flex items-start gap-4">
            <CareGlyph careType={response.care_type} className="h-16 w-16" iconClass="h-8 w-8" />
            <div>
              <h2 id="result-title" className="text-3xl font-semibold md:text-4xl">{t(`careTypes.${response.care_type}.name`)}</h2>
              <p className="mt-1 text-lg text-muted">{t(`careTypes.${response.care_type}.meaning`)}</p>
            </div>
          </div>
          <div className="mt-5"><UrgencyBadge urgency={response.urgency} size="lg" /></div>
          <div className="mt-5 rounded-xl border-l-4 border-primary bg-primary-soft/40 px-4 py-3">
            <p className="eyebrow mb-1 text-primary-deep">{t("panel.why")}</p>
            <p className="text-lg leading-relaxed">{response.reasoning}</p>
          </div>
        </div>
        <div className="rounded-xl2 bg-sunken/60 p-5">
          <h3 className="font-sans text-lg font-bold">{t("result.todo")}</h3>
          <ul className="mt-3 space-y-3">
            {t("result.tips").map((tip) => (
              <li key={tip} className="flex gap-2.5"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-routine" aria-hidden="true" />{tip}</li>
            ))}
          </ul>
        </div>
      </motion.div>

      {debug?.assessment && (
        <AssessmentCard card={debug.assessment}
          onGoToCaregivers={() => document.getElementById("caregivers")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" })} />
      )}

      <div id="caregivers" className="scroll-mt-24">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-2xl font-semibold md:text-3xl">{loaded ? heading(t, response, rows, location) : t("result.caregivers")}</h2>
            <p className="text-muted">{t("result.caregiversSub")}</p>
            {location.lat != null && !tele && (
              <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold"><MapPin className="h-4 w-4 text-accent" aria-hidden="true" />{locationLabel(location, t)}</p>
            )}
          </div>
          {rows.length > 0 && (
            <div className="inline-flex rounded-xl border border-line bg-surface p-1" role="tablist" aria-label={`${t("common.list")} / ${t("common.map")}`}>
              {[["list", LayoutList, t("common.list")], ["map", MapIcon, t("common.map")]].map(([k, Icon, label]) => (
                <button key={k} type="button" role="tab" aria-selected={view === k} onClick={() => setView(k)}
                  className={`flex min-h-[44px] items-center gap-2 rounded-lg px-4 font-semibold ${view === k ? "bg-primary text-primary-ink" : "text-muted hover:text-ink"}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />{label}
                </button>
              ))}
            </div>
          )}
        </div>
        {!tele && <NcrNotice className="mb-5" />}

        {rows.length === 0 ? (
          <EmptyState icon={UsersRound} title={t("result.noCaregivers")} />
        ) : !loaded ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{rows.map((r) => <Skeleton key={r.m.caregiver_id} className="h-[460px]" />)}</div>
        ) : view === "list" ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((r, i) => (
              <CaregiverCard key={r.m.caregiver_id} cg={r.cg} match={r.m} rank={r.rank} distanceKm={r.km} slot={r.slot}
                teleconsult={tele} index={i} onBook={(cg) => setBooking({ cg, slot: r.slot })} />
            ))}
          </div>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
            <CaregiverMap user={location.lat != null ? location : null} height={520} onSelect={select} selectedId={selected}
              items={rows.filter((r) => r.cg).map((r) => ({ cg: r.cg, label: r.rank, top: r.rank === 1, sub: r.m.reason }))} />
            <ol className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
              {rows.filter((r) => r.cg).map((r) => (
                <li key={r.m.caregiver_id} id={`cgl-${r.m.caregiver_id}`}
                  className={`card flex items-start gap-3 p-4 transition-shadow ${selected === r.m.caregiver_id ? "ring-4 ring-accent/60" : ""}`}>
                  <button type="button" onClick={() => setSelected(r.m.caregiver_id)} aria-label={`${t("common.rank")} ${r.rank}: ${r.cg.name}`}
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-bold ${r.rank === 1 ? "bg-primary text-white" : "bg-ink text-bg"}`}>{r.rank}</button>
                  <div className="min-w-0 flex-1">
                    <p className="font-bold">{r.cg.name}</p>
                    <p className="text-sm text-muted">
                      {t(`roles.${r.cg.role}`)}{r.cg.specialty ? ` · ${t(`specialty.${r.cg.specialty}`)}` : ""}
                      {!tele && r.km != null ? ` · ${kmLabel(r.km, t)}` : ""} · {slotLabel(r.slot, t, lang)}
                    </p>
                    <p className="mt-1 text-sm">{r.m.reason}</p>
                  </div>
                  <button type="button" className="btn-primary shrink-0 px-4" onClick={() => setBooking({ cg: r.cg, slot: r.slot })}>{t("result.book")}</button>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {booking && (
        <BookingModal cg={booking.cg} preferredSlot={booking.slot} careType={response.care_type} urgency={response.urgency}
          onClose={() => setBooking(null)} />
      )}
    </section>
  );
}
