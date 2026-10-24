import en from "./en.json";
import hi from "./hi.json";

export const DICTS = { en, hi };

function lookup(dict, key) {
  return key.split(".").reduce((o, k) => (o == null ? undefined : o[k]), dict);
}

/** Translate a dotted key; falls back to English, then to the key itself. `{var}` placeholders are filled from vars. */
export function translate(lang, key, vars) {
  let v = lookup(DICTS[lang] || en, key);
  if (v === undefined) v = lookup(en, key);
  if (v === undefined) return key;
  if (typeof v === "string" && vars) {
    return v.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? `{${k}}`));
  }
  return v;
}
