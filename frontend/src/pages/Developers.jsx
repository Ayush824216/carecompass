import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function Developers() {
  const { t } = useApp();
  return <PageHeader title={t("dev.title")} />;
}
