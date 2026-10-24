import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function Bookings() {
  const { t } = useApp();
  return <PageHeader title={t("bookingsPage.title")} />;
}
