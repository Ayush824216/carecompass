import { useCallback, useEffect, useMemo, useState } from "react";
import { LayoutGrid, Map as MapIcon, Search, SlidersHorizontal, UsersRound } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import CaregiverCard from "../components/CaregiverCard.jsx";
import CaregiverMap from "../components/CaregiverMap.jsx";
import BookingModal from "../components/BookingModal.jsx";
import NcrNotice from "../components/NcrNotice.jsx";
import { EmptyState, ErrorState, Skeleton } from "../components/ui.jsx";
import { useApp } from "../context/AppContext.jsx";
import { api } from "../lib/api.js";
import { CARE_ORDER, ROLE_FOR_CARE } from "../lib/care.js";
import { haversineKm, isFreeToday, nextSlot } from "../lib/format.js";

const ROLES = ["paramedic", "nurse", "gp", "specialist"];
const CARE_FOR_ROLE = Object.fromEntries(CARE_ORDER.filter((c) => ROLE_FOR_CARE[c]).map((c) => [ROLE_FOR_CARE[c], c]));
const EMPTY = { q: "", role: "", language: "", today: false, maxKm: 0, minRating: 0 };

function Filters({ f, set, langs, t, onReset, idp }) {
  const field = "mb-1.5 block font-semibold";
  return (
    <div className="space-y-5">
      <div>
        <label htmlFor={`${idp}-f-q`} className={field}>{t("directory.search")}</label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input id={`${idp}-f-q`} type="search" value={f.q} onChange={(e) => set({ q: e.target.value })} className="input pl-10" />
        </div>
      </div>
      <fieldset>
        <legend className={field}>{t("directory.role")}</legend>
        <div className="flex flex-wrap gap-2">
          {["", ...ROLES].map((r) => (
            <button key={r || "all"} type="button" aria-pressed={f.role === r} onClick={() => set({ role: r })}
              className={`chip min-h-[44px] px-4 font-semibold ${f.role === r ? "border-primary bg-primary text-primary-ink" : "hover:border-primary"}`}>
              {r ? t(`roles.${r}`) : t("common.all")}
            </button>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor={`${idp}-f-lang`} className={field}>{t("directory.language")}</label>
        <select id={`${idp}-f-lang`} value={f.language} onChange={(e) => set({ language: e.target.value })} className="input">
          <option value="">{t("common.all")}</option>
          {langs.map((l) => <option key={l} value={l}>{t(`langNames.${l}`)}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
        <div>
          <label htmlFor={`${idp}-f-km`} className={field}>{t("directory.distance")}</label>
          <select id={`${idp}-f-km`} value={f.maxKm} onChange={(e) => set({ maxKm: Number(e.target.value) })} className="input">
            <option value={0}>{t("directory.anyDistance")}</option>
            {[5, 10, 20].map((k) => <option key={k} value={k}>{k} {t("common.km")}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={`${idp}-f-rating`} className={field}>{t("directory.rating")}</label>
          <select id={`${idp}-f-rating`} value={f.minRating} onChange={(e) => set({ minRating: Number(e.target.value) })} className="input">
            <option value={0}>{t("directory.anyRating")}</option>
            {[4, 4.5].map((r) => <option key={r} value={r}>{r}+</option>)}
          </select>
        </div>
      </div>
      <label className="flex min-h-[48px] cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-4">
        <input type="checkbox" checked={f.today} onChange={(e) => set({ today: e.target.checked })} className="h-5 w-5 accent-[rgb(var(--primary))]" />
        <span className="font-semibold">{t("directory.today")}</span>
      </label>
      <button type="button" onClick={onReset} className="btn-ghost w-full">{t("directory.reset")}</button>
    </div>
  );
}

export default function Caregivers() {
  const { t, location } = useApp();
  const [all, setAll] = useState(null);
  const [error, setError] = useState(false);
  const [f, setF] = useState(EMPTY);
  const [view, setView] = useState("grid");
  const [booking, setBooking] = useState(null);
  const set = (patch) => setF((x) => ({ ...x, ...patch }));

  const load = useCallback(() => {
    setError(false); setAll(null);
    api.caregivers().then(setAll).catch(() => setError(true));
  }, []);
  useEffect(() => { load(); }, [load]);

  const langs = useMemo(() => [...new Set((all || []).flatMap((c) => c.languages || []))].sort(), [all]);
  const rows = useMemo(() => {
    if (!all) return [];
    const q = f.q.trim().toLowerCase();
    return all
      .map((cg) => ({ cg, km: haversineKm(location, cg), slot: nextSlot(cg) }))
      .filter(({ cg, km }) =>
        (!q || cg.name.toLowerCase().includes(q) || (cg.skills || []).some((s) => s.replace(/_/g, " ").includes(q)))
        && (!f.role || cg.role === f.role)
        && (!f.language || (cg.languages || []).includes(f.language))
        && (!f.today || isFreeToday(cg))
        && (!f.maxKm || (km != null && km <= f.maxKm))
        && (!f.minRating || cg.rating >= f.minRating))
      .sort((a, b) => (a.km ?? 1e9) - (b.km ?? 1e9));
  }, [all, f, location]);

  return (
    <>
      <PageHeader title={t("directory.title")} subtitle={t("directory.subtitle")} />
      <div className="container-page grid gap-8 py-10 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-[92px] lg:self-start" aria-label={t("directory.filters")}>
          <details className="card p-5 lg:hidden">
            <summary className="flex min-h-[44px] cursor-pointer items-center gap-2 font-bold"><SlidersHorizontal className="h-5 w-5" aria-hidden="true" />{t("directory.filters")}</summary>
            <div className="mt-4"><Filters idp="m" f={f} set={set} langs={langs} t={t} onReset={() => setF(EMPTY)} /></div>
          </details>
          <div className="card hidden p-5 lg:block">
            <h2 className="mb-4 flex items-center gap-2 font-sans text-lg font-bold"><SlidersHorizontal className="h-5 w-5" aria-hidden="true" />{t("directory.filters")}</h2>
            <Filters idp="d" f={f} set={set} langs={langs} t={t} onReset={() => setF(EMPTY)} />
          </div>
        </aside>

        <section aria-live="polite">
          <NcrNotice className="mb-5" />
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-lg font-semibold">{all ? t("directory.results", { n: rows.length }) : t("common.loading")}</p>
            <div className="inline-flex rounded-xl border border-line bg-surface p-1" role="tablist" aria-label={`${t("common.list")} / ${t("common.map")}`}>
              {[["grid", LayoutGrid, t("common.list")], ["map", MapIcon, t("common.map")]].map(([k, Icon, label]) => (
                <button key={k} type="button" role="tab" aria-selected={view === k} onClick={() => setView(k)}
                  className={`flex min-h-[44px] items-center gap-2 rounded-lg px-4 font-semibold ${view === k ? "bg-primary text-primary-ink" : "text-muted hover:text-ink"}`}>
                  <Icon className="h-4 w-4" aria-hidden="true" />{label}
                </button>
              ))}
            </div>
          </div>

          {error ? <ErrorState onRetry={load} />
            : !all ? <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[330px]" />)}</div>
            : rows.length === 0 ? (
              <EmptyState icon={UsersRound} title={t("directory.empty")}>
                <button type="button" className="btn-primary" onClick={() => setF(EMPTY)}>{t("directory.reset")}</button>
              </EmptyState>
            ) : view === "map" ? (
              <CaregiverMap user={location.lat != null ? location : null} height={620}
                items={rows.map((r, i) => ({ cg: r.cg, label: i + 1, top: false, sub: t(`roles.${r.cg.role}`) }))} />
            ) : (
              <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
                {rows.map((r, i) => (
                  <CaregiverCard key={r.cg.caregiver_id} cg={r.cg} distanceKm={r.km} slot={r.slot} index={Math.min(i, 8)}
                    teleconsult={r.cg.role === "gp"} onBook={(cg) => setBooking({ cg, slot: r.slot })} />
                ))}
              </div>
            )}
        </section>
      </div>
      {booking && (
        <BookingModal cg={booking.cg} preferredSlot={booking.slot} careType={CARE_FOR_ROLE[booking.cg.role]} urgency="routine"
          onClose={() => setBooking(null)} />
      )}
    </>
  );
}
