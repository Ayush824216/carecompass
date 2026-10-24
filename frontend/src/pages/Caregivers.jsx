import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function Caregivers() {
  const { t } = useApp();
  return <PageHeader title={t("directory.title")} />;
}
