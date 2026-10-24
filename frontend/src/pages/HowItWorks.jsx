import {
  Activity, ArrowDown, ArrowRight, Brain, CalendarCheck, Cpu, Droplets, ExternalLink, FlaskConical, Gauge, HeartPulse, Languages, MessageCircleQuestion, Mic,
  ShieldAlert, ShieldCheck, Siren, Thermometer, UsersRound, Utensils, Wind,
} from "lucide-react";
import PageHeader from "../components/PageHeader.jsx";
import { useApp } from "../context/AppContext.jsx";
import { SEVERITY_STAGES, URGENCY_STYLE } from "../lib/care.js";

const FLOW = [
  ["input", Mic], ["lang", Languages], ["safety", ShieldCheck, true], ["pathways", Gauge], ["intake", MessageCircleQuestion],
  ["triage", Cpu], ["recheck", ShieldCheck, true], ["match", UsersRound], ["book", CalendarCheck],
];

function Node({ k, Icon, t, gate }) {
  return (
    <div className={`flex items-start gap-4 rounded-xl2 border bg-surface p-4 shadow-card ${gate ? "border-2 border-primary" : "border-line"}`}>
      <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${gate ? "bg-primary text-white" : "bg-primary-soft text-primary-deep"}`}>
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="font-bold">{t(`how.flow.${k}`)}</p>
        <p className="text-sm text-muted">{t(`how.flow.${k}D`)}</p>
      </div>
    </div>
  );
}

function Flowchart({ t }) {
  return (
    <figure aria-label={t("how.flowTitle")}>
      <ol className="space-y-0">
        {FLOW.map(([k, Icon, gate], i) => (
          <li key={k}>
            <div className="grid items-center gap-3 lg:grid-cols-[minmax(0,1fr)_140px_minmax(0,0.85fr)]">
              <Node k={k} Icon={Icon} t={t} gate={gate} />
              {gate ? (
                <>
                  <div className="flex items-center gap-2 pl-6 text-sm font-bold text-emergency lg:flex-col lg:gap-1 lg:pl-0" aria-hidden="true">
                    <span>{t("how.flow.yes")}</span>
                    <ArrowRight className="hidden h-6 w-6 lg:block" />
                    <ArrowDown className="h-5 w-5 lg:hidden" />
                  </div>
                  <div className="flex items-start gap-3 rounded-xl2 border-2 border-emergency bg-emergency-soft p-4">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emergency text-white"><Siren className="h-6 w-6" aria-hidden="true" /></span>
                    <div>
                      <p className="font-bold text-emergency-deep">{t("how.flow.emergency")}</p>
                      <p className="text-sm text-emergency-deep/80">{t("how.flow.emergencyD")}</p>
                    </div>
                  </div>
                </>
              ) : <div className="hidden lg:block" />}
            </div>
            {i < FLOW.length - 1 && (
              <div className="flex items-center gap-2 py-2 pl-[38px] text-sm font-semibold text-muted" aria-hidden="true">
                <ArrowDown className="h-5 w-5 text-primary" />
                {gate && <span className="rounded-full bg-routine-soft px-2 py-0.5 text-routine">{t("how.flow.no")}</span>}
              </div>
            )}
          </li>
        ))}
      </ol>
    </figure>
  );
}

const PATHWAY_ICON = { fever: Thermometer, cough: Wind, breathing: Activity, chest_pain: HeartPulse, headache: Brain,
  abdominal: Utensils, vomiting: Droplets, urinary: FlaskConical };
const STAGE_URGENCY = { S0: "routine", S1: "same_day", S2: "same_day", S3: "immediate" };

function Pathways({ t }) {
  const list = t("how.pathwayList");
  return (
    <section aria-labelledby="pathways-h">
      <h2 id="pathways-h" className="text-3xl font-semibold">{t("how.pathwaysTitle")}</h2>
      <p className="mt-2 max-w-3xl text-muted">{t("how.pathwaysSub")}</p>

      <h3 className="mt-8 font-sans text-xl font-bold">{t("how.ladderTitle")}</h3>
      <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {SEVERITY_STAGES.map((st) => {
          const style = URGENCY_STYLE[STAGE_URGENCY[st]];
          const Icon = style.icon;
          return (
            <li key={st} className={`rounded-xl2 border-2 p-4 ${style.chip}`}>
              <p className="flex items-center gap-2 font-mono text-lg font-bold"><Icon className="h-5 w-5" aria-hidden="true" />{st}</p>
              <p className="mt-1 font-bold">{t(`severity.${st}.name`)}</p>
              <p className="text-sm">{t(`severity.${st}.route`)}</p>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 max-w-3xl text-sm text-muted">{t("how.ladderNote")}</p>

      <ul className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {list.map((pw) => {
          const Icon = PATHWAY_ICON[pw.id] || Gauge;
          return (
            <li key={pw.id} className="card p-5">
              <p className="flex items-center gap-3 text-lg font-bold">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary-deep"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                {pw.name}
              </p>
              <p className="mt-3 text-sm text-muted">{pw.asks}</p>
              <p className="mt-3 rounded-lg bg-sunken px-3 py-2 text-sm font-semibold">{pw.example}</p>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 flex items-center gap-2 font-semibold"><ShieldCheck className="h-5 w-5 text-primary" aria-hidden="true" />{t("how.notDiagnosis")}</p>
    </section>
  );
}

export default function HowItWorks() {
  const { t } = useApp();
  const layers = t("how.layers");
  const data = t("how.data");
  const choices = t("how.choices");
  return (
    <>
      <PageHeader title={t("how.title")} subtitle={t("how.subtitle")} />
      <div className="container-page space-y-20 py-14">
        <section aria-labelledby="flow-h">
          <h2 id="flow-h" className="mb-8 text-3xl font-semibold">{t("how.flowTitle")}</h2>
          <Flowchart t={t} />
        </section>

        <Pathways t={t} />

        <section aria-labelledby="layers-h" className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <h2 id="layers-h" className="text-3xl font-semibold">{t("how.layersTitle")}</h2>
            <p className="mt-2 text-muted">{t("how.layersSub")}</p>
          </div>
          <ol className="space-y-2">
            {layers.map((l, i) => (
              <li key={l.name} className="grid grid-cols-[56px_1fr] overflow-hidden rounded-xl2 border border-line bg-surface"
                style={{ marginLeft: `${i * 2}%`, marginRight: `${(layers.length - 1 - i) * 2}%` }}>
                <span className={`flex items-center justify-center font-display text-2xl font-semibold ${i === 2 ? "bg-primary text-white" : "bg-primary-soft text-primary-deep"}`}>{i + 1}</span>
                <div className="px-4 py-3">
                  <p className="font-bold">{l.name}{i === 2 && <ShieldAlert className="ml-2 inline h-4 w-4 text-primary" aria-hidden="true" />}</p>
                  <p className="text-sm text-muted">{l.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="data-h">
          <h2 id="data-h" className="text-3xl font-semibold">{t("how.dataTitle")}</h2>
          <p className="mt-2 text-muted">{t("how.dataSub")}</p>
          <div className="mt-6 overflow-hidden rounded-xl2 border border-line bg-surface">
            <table className="w-full text-left">
              <tbody className="divide-y divide-line">
                {data.map((d) => (
                  <tr key={d.name} className="flex flex-col md:table-row">
                    <th scope="row" className="px-5 pt-4 font-bold md:w-[34%] md:py-4">{d.name}</th>
                    <td className="px-5 pt-1 text-muted md:py-4">{d.desc}</td>
                    <td className="px-5 pb-4 pt-1 md:w-[1%] md:whitespace-nowrap md:py-4">
                      {d.link ? (
                        <a href={d.link} target="_blank" rel="noreferrer" className="inline-flex min-h-[44px] items-center gap-1.5 font-semibold text-primary hover:underline">
                          Kaggle<ExternalLink className="h-4 w-4" aria-hidden="true" /><span className="sr-only">{d.name}</span>
                        </a>
                      ) : <span className="text-sm font-semibold text-muted">synthetic</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section aria-labelledby="choices-h">
          <h2 id="choices-h" className="text-3xl font-semibold">{t("how.choicesTitle")}</h2>
          <div className="mt-6 grid gap-x-10 gap-y-6 md:grid-cols-2">
            {choices.map((c, i) => (
              <div key={c.name} className="border-l-4 border-accent pl-5">
                <p className="font-display text-sm font-semibold text-accent">0{i + 1}</p>
                <h3 className="font-sans text-xl font-bold">{c.name}</h3>
                <p className="mt-1 text-muted">{c.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
