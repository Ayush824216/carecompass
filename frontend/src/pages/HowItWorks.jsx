import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function HowItWorks() {
  const { t } = useApp();
  return <PageHeader title={t("how.title")} />;
}
