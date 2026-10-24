import { useState } from "react";
import { Database, Download, EyeOff, Trash2 } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { DEVICE_KEYS, exportMemory, forgetAll, forgetAssessment, forgetItem, loadMemory, updateItem } from "../lib/memory.js";
import { load, remove } from "../lib/storage.js";

const AGE_GROUPS = ["infant", "child", "adult", "elderly"];

/** "My health memory": everything this browser keeps about you, with edit / forget / delete all / export. */
export default function Memory() {
  const { t, incognito, setSosContacts } = useApp();
  const [m, setM] = useState(loadMemory);
  const [device, setDevice] = useState(() => Object.fromEntries(Object.entries(DEVICE_KEYS).map(([k, key]) => [k, load(key, null)])));
  const items = Object.values(m.items);
  const forgetDevice = (k) => { remove(DEVICE_KEYS[k]); if (k === "emergencyContact") setSosContacts([]); setDevice((d) => ({ ...d, [k]: null })); };
  const ForgetBtn = ({ onClick }) => (
    <button type="button" onClick={onClick} className="btn-ghost min-h-[44px] px-3 text-sm"><Trash2 className="h-4 w-4" aria-hidden="true" />{t("memory.forget")}</button>
  );
  const deviceValue = (k, v) => k === "location" ? (v?.label || (v?.lat != null ? `${v.lat.toFixed(3)}, ${v.lng.toFixed(3)}` : null))
    : k === "emergencyContact" ? (Array.isArray(v) && v.length ? v.map((c) => c.name).join(", ") : null) : v;

  return (
    <div className="container-page max-w-3xl py-8 md:py-10">
      <h1 className="flex items-center gap-3 text-3xl font-semibold md:text-4xl"><Database className="h-8 w-8 text-primary" aria-hidden="true" />{t("memory.title")}</h1>
      <p className="mt-2 text-lg text-muted">{t("memory.lead")}</p>
      {incognito && <p className="mt-4 chip inline-flex items-center gap-2 bg-ink font-semibold text-bg"><EyeOff className="h-4 w-4" aria-hidden="true" />{t("privacy.incognitoBadge")}</p>}

      <section className="card mt-6 p-5" aria-labelledby="mem-items">
        <h2 id="mem-items" className="text-xl font-semibold">{t("memory.profile")}</h2>
        {items.length === 0 && <p className="mt-2 text-muted">{t("memory.empty")}</p>}
        <ul className="mt-3 divide-y divide-line">
          {items.map((it) => (
            <li key={it.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <span>
                <span className="font-semibold">{it.label}</span>
                {it.sensitive && <span className="chip ml-2 bg-sameday-soft text-xs font-bold">{t("memory.sensitive")}</span>}
                <span className="block text-sm text-muted">{t("memory.savedOn", { d: (it.saved_at || "").slice(0, 10) })}</span>
              </span>
              <span className="flex items-center gap-2">
                {it.kind === "age" && (
                  <select aria-label={t("memory.editAge")} className="input min-h-[44px]" value={it.value}
                    onChange={(e) => setM(updateItem(it.id, { value: e.target.value, label: t(`memory.age.${e.target.value}`) }))}>
                    {AGE_GROUPS.map((g) => <option key={g} value={g}>{t(`memory.age.${g}`)}</option>)}
                  </select>
                )}
                {it.kind !== "age" && (
                  <label className="flex min-h-[44px] items-center gap-2 text-sm">
                    <input type="checkbox" className="h-5 w-5" checked={it.value === true} onChange={(e) => setM(updateItem(it.id, { value: e.target.checked }))} />
                    {t("memory.stillTrue")}
                  </label>
                )}
                <ForgetBtn onClick={() => setM(forgetItem(it.id))} />
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card mt-6 p-5" aria-labelledby="mem-past">
        <h2 id="mem-past" className="text-xl font-semibold">{t("memory.past")}</h2>
        {m.assessments.length === 0 && <p className="mt-2 text-muted">{t("memory.empty")}</p>}
        <ul className="mt-3 divide-y divide-line">
          {m.assessments.map((a, i) => (
            <li key={`${a.date}-${i}`} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <span>{a.date} · {a.category ? t(`memory.cat.${a.category}`) : "—"}{a.stage ? ` · ${a.stage}` : ""} · {t(`careTypes.${a.care_type}.name`)}</span>
              <ForgetBtn onClick={() => setM(forgetAssessment(i))} />
            </li>
          ))}
        </ul>
        <p className="mt-2 text-sm text-muted">{t("memory.noChat")}</p>
      </section>

      <section className="card mt-6 p-5" aria-labelledby="mem-device">
        <h2 id="mem-device" className="text-xl font-semibold">{t("memory.device")}</h2>
        <ul className="mt-3 divide-y divide-line">
          {Object.keys(DEVICE_KEYS).map((k) => (
            <li key={k} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <span><span className="font-semibold">{t(`memory.deviceKeys.${k}`)}</span>
                <span className="block text-sm text-muted">{deviceValue(k, device[k]) || t("memory.notSaved")}</span></span>
              {device[k] != null && <ForgetBtn onClick={() => forgetDevice(k)} />}
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-6 flex flex-wrap gap-3">
        <button type="button" className="btn-ghost min-h-[48px]" onClick={exportMemory}><Download className="h-4 w-4" aria-hidden="true" />{t("memory.export")}</button>
        <button type="button" className="btn-ghost min-h-[48px] text-emergency" onClick={() => {
          if (window.confirm(t("memory.deleteAllConfirm"))) { setM(forgetAll()); setSosContacts([]); setDevice({ language: null, location: null, emergencyContact: null }); }
        }}><Trash2 className="h-4 w-4" aria-hidden="true" />{t("memory.deleteAll")}</button>
      </div>
      <p className="mt-4 text-sm text-muted">{t("memory.serverNote")}</p>
    </div>
  );
}
