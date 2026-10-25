import { Info } from "lucide-react";
import { useApp } from "../context/AppContext.jsx";
import { inDelhiNcr } from "../lib/locations.js";

/** Outside Delhi NCR: the demo caregivers are still listed (nearest first, with distance); 112 / 108 work everywhere. */
export default function NcrNotice({ className = "" }) {
  const { t, location } = useApp();
  if (inDelhiNcr(location) !== false) return null;
  return (
    <p role="note" className={`flex items-start gap-2 rounded-xl border border-accent/40 bg-accent-soft px-4 py-3 text-sm font-semibold ${className}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
      <span>{t("location.outsideNcr")} <span className="font-normal">{t("location.outsideNcrNote")}</span></span>
    </p>
  );
}
