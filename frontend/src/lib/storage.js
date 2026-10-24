// localStorage can throw (private mode, blocked storage): every access is guarded.
// In Incognito nothing is written at all: save() and remove() become no-ops until the session ends.
let noStore = false;
export function setNoStore(v) { noStore = Boolean(v); }
export function storageOff() { return noStore; }

export function load(key, fallback) {
  try {
    const v = window.localStorage.getItem(key);
    return v == null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  if (noStore) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

export function remove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}
