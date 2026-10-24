import { useState } from "react";
import { Link } from "react-router-dom";
import { EyeOff, Pencil, Phone, Plus, Trash2, Users } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { MAX_CONTACTS, cleanPhone, telHref, validPhone } from "../lib/sos.js";

const EMPTY = { name: "", phone: "", relation: "" };

/** SOS family contacts: up to 5, saved only on this device (never in Incognito). */
export default function Sos() {
  const { t, incognito, sosContacts, setSosContacts } = useApp();
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(-1); // -1 = adding
  const [err, setErr] = useState("");
  const full = sosContacts.length >= MAX_CONTACTS && editing < 0;

  const submit = (e) => {
    e.preventDefault();
    const c = { name: form.name.trim(), phone: cleanPhone(form.phone), relation: form.relation.trim() };
    if (!c.name || !validPhone(c.phone)) { setErr(t("sos.invalid")); return; }
    const list = editing >= 0 ? sosContacts.map((x, i) => (i === editing ? c : x)) : [...sosContacts, c].slice(0, MAX_CONTACTS);
    setSosContacts(list); setForm(EMPTY); setEditing(-1); setErr("");
  };

  return (
    <div className="container-page max-w-3xl py-8 md:py-10">
      <h1 className="flex items-center gap-3 text-3xl font-semibold md:text-4xl"><Users className="h-8 w-8 text-emergency" aria-hidden="true" />{t("sos.title")}</h1>
      <p className="mt-2 text-lg text-muted">{t("sos.lead", { n: MAX_CONTACTS })}</p>
      {incognito && <p className="mt-4 chip inline-flex items-center gap-2 bg-ink font-semibold text-bg"><EyeOff className="h-4 w-4" aria-hidden="true" />{t("sos.incognito")}</p>}

      <ul className="card mt-6 divide-y divide-line p-2">
        {sosContacts.length === 0 && <li className="p-4 text-muted">{t("sos.empty")}</li>}
        {sosContacts.map((c, i) => (
          <li key={`${c.phone}-${i}`} className="flex flex-wrap items-center justify-between gap-3 p-3">
            <span><span className="font-semibold">{c.name}</span>{c.relation && <span className="text-muted"> · {c.relation}</span>}
              <span className="block font-mono text-sm">{c.phone}</span></span>
            <span className="flex flex-wrap gap-2">
              <a href={telHref(c.phone)} className="btn-ghost min-h-[44px] px-3 text-sm"><Phone className="h-4 w-4" aria-hidden="true" />{t("sos.call")}</a>
              <button type="button" className="btn-ghost min-h-[44px] px-3 text-sm" onClick={() => { setEditing(i); setForm({ ...EMPTY, ...c }); }}>
                <Pencil className="h-4 w-4" aria-hidden="true" />{t("sos.edit")}</button>
              <button type="button" className="btn-ghost min-h-[44px] px-3 text-sm" onClick={() => setSosContacts(sosContacts.filter((_, j) => j !== i))}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />{t("sos.remove")}</button>
            </span>
          </li>
        ))}
      </ul>

      {!full && (
        <form className="card mt-6 grid gap-3 p-5 sm:grid-cols-3" onSubmit={submit} noValidate>
          <h2 className="text-xl font-semibold sm:col-span-3">{editing >= 0 ? t("sos.editTitle") : t("sos.addTitle")}</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">{t("sos.name")}
            <input className="input min-h-[48px]" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="name" /></label>
          <label className="flex flex-col gap-1 text-sm font-semibold">{t("sos.phone")}
            <input className="input min-h-[48px]" value={form.phone} inputMode="tel" onChange={(e) => setForm({ ...form, phone: e.target.value })} autoComplete="tel" /></label>
          <label className="flex flex-col gap-1 text-sm font-semibold">{t("sos.relation")}
            <input className="input min-h-[48px]" value={form.relation} placeholder={t("sos.relationHint")} onChange={(e) => setForm({ ...form, relation: e.target.value })} /></label>
          {err && <p className="font-semibold text-emergency sm:col-span-3" role="alert">{err}</p>}
          <div className="flex gap-3 sm:col-span-3">
            <button type="submit" className="btn-primary min-h-[48px]"><Plus className="h-4 w-4" aria-hidden="true" />{editing >= 0 ? t("sos.save") : t("sos.add")}</button>
            {editing >= 0 && <button type="button" className="btn-ghost min-h-[48px]" onClick={() => { setEditing(-1); setForm(EMPTY); setErr(""); }}>{t("common.cancel")}</button>}
          </div>
        </form>
      )}
      {full && <p className="mt-4 text-muted">{t("sos.full", { n: MAX_CONTACTS })}</p>}
      <p className="mt-6 text-sm text-muted">{t("sos.privacy")} <Link to="/memory" className="underline">{t("privacy.manage")}</Link></p>
    </div>
  );
}
