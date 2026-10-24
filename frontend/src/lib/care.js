import { AlertTriangle, Ambulance, CalendarDays, Clock, HeartPulse, Microscope, Siren, Video } from "lucide-react";

export const CARE_ORDER = ["paramedic_home_visit", "nurse_home_visit", "gp_teleconsult", "specialist_referral", "emergency_referral"];

export const CARE_ICON = {
  paramedic_home_visit: Ambulance,
  nurse_home_visit: HeartPulse,
  gp_teleconsult: Video,
  specialist_referral: Microscope,
  emergency_referral: Siren,
};

export const URGENCY_ORDER = ["routine", "same_day", "immediate"];

// colour is always paired with an icon and a text label
export const URGENCY_STYLE = {
  routine: { icon: CalendarDays, chip: "bg-routine-soft text-routine border-routine/40", bar: "bg-routine" },
  same_day: { icon: Clock, chip: "bg-sameday-soft text-sameday border-sameday/40", bar: "bg-sameday" },
  immediate: { icon: AlertTriangle, chip: "bg-emergency-soft text-emergency border-emergency/40", bar: "bg-emergency" },
};

export const ROLE_FOR_CARE = {
  paramedic_home_visit: "paramedic", nurse_home_visit: "nurse", gp_teleconsult: "gp", specialist_referral: "specialist",
};

export const SEVERITY_STAGES = ["S0", "S1", "S2", "S3"];

/** Red-flag label: the app's own dictionary first, then the pathway labels sent in the debug block. */
export function flagLabel(f, t, debug) {
  const v = t(`flags.${f}`);
  if (v !== `flags.${f}`) return v;
  return debug?.pathways?.flag_labels?.[f] || f.replace(/_/g, " ");
}
