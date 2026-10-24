import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function GetCare() {
  const { t } = useApp();
  return <PageHeader title={t("care.title")} />;
}
