import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function Home() {
  const { t } = useApp();
  return <PageHeader title={t("home.title")} />;
}
