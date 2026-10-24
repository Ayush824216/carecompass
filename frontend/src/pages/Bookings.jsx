import { Link } from "react-router-dom";
import { CalendarCheck, ChevronRight, Trash2 } from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import StatusTimeline, { STATUS_KEYS } from "../components/StatusTimeline.jsx";
import { Avatar, CareGlyph, EmptyState, UrgencyBadge } from "../components/ui.jsx";
import { useApp } from "../context/AppContext.jsx";
import { slotLabel } from "../lib/format.js";

export default function Bookings() {
  const { t, lang, bookings, updateBooking, removeBooking } = useApp();
  return (
    <>
      <PageHeader title={t("bookingsPage.title")} subtitle={t("bookingsPage.subtitle")} />
      <div className="container-page py-10">
        {bookings.length === 0 ? (
          <EmptyState icon={CalendarCheck} title={t("bookingsPage.empty")} hint={t("bookingsPage.emptyHint")}>
            <Link to="/care" className="btn-primary">{t("bookingsPage.emptyCta")}<ChevronRight className="h-5 w-5" aria-hidden="true" /></Link>
          </EmptyState>
        ) : (
          <ul className="space-y-5">
            {bookings.map((b) => {
              const status = b.status ?? 0;
              return (
                <li key={b.booking_id} className="card p-5 md:p-6">
                  <div className="flex flex-wrap items-start gap-4">
                    <Avatar name={b.caregiver_name} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <h2 className="font-sans text-xl font-bold">{b.caregiver_name}</h2>
                        <span className="text-muted">{t(`roles.${b.role}`)}</span>
                      </div>
                      <p className="mt-1 flex flex-wrap items-center gap-2 text-muted">
                        <CareGlyph careType={b.care_type} className="h-8 w-8 rounded-lg" iconClass="h-4 w-4" />
                        <span className="font-semibold text-ink">{t(`careTypes.${b.care_type}.name`)}</span>
                        {b.urgency && <UrgencyBadge urgency={b.urgency} compact />}
                      </p>
                    </div>
                    <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                      <dt className="text-muted">{t("booking.bookingId")}</dt><dd className="font-mono font-bold">{b.booking_id}</dd>
                      <dt className="text-muted">{t("booking.time")}</dt><dd className="font-semibold">{b.slot ? slotLabel(new Date(b.slot), t, lang) : "—"}</dd>
                      <dt className="text-muted">{t("bookingsPage.bookedAt")}</dt><dd>{slotLabel(new Date(b.created_at), t, lang)}</dd>
                      {b.patient_name && <><dt className="text-muted">{t("booking.patientName")}</dt><dd>{b.patient_name}</dd></>}
                    </dl>
                  </div>
                  <div className="mt-6"><StatusTimeline current={status} /></div>
                  <div className="mt-5 flex flex-wrap gap-3 border-t border-line pt-4">
                    <button type="button" className="btn-ghost" disabled={status >= STATUS_KEYS.length - 1}
                      onClick={() => updateBooking(b.booking_id, { status: Math.min(status + 1, STATUS_KEYS.length - 1) })}>
                      {t("bookingsPage.advance")}<ChevronRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <button type="button" className="btn-ghost text-emergency" onClick={() => removeBooking(b.booking_id)}
                      aria-label={`${t("bookingsPage.remove")} ${b.booking_id}`}>
                      <Trash2 className="h-4 w-4" aria-hidden="true" />{t("bookingsPage.remove")}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
