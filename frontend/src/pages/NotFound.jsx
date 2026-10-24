import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function NotFound() {
  const { t } = useApp();
  return (
    <PageHeader title={t("notFound.title")}>
      <Link to="/" className="btn-primary mt-6">{t("notFound.cta")}</Link>
    </PageHeader>
  );
}
