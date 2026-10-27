import { Leaf } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ShareBar } from "@/components/a2f/a2f-card";
import data from "@/data/planting.json";

// Figures from the client's workbooks, rebuilt per
// AB_KPI_Guidance_AKVO.docx by `manage.py build_planting_kpis`.
const month = (iso, style) =>
  new Date(iso).toLocaleDateString("en-US", {
    month: style,
    year: "numeric",
    timeZone: "UTC",
  });
const [firstYear, lastYear] = data.planting_years;
const PLANTING_DATE =
  firstYear === lastYear
    ? `Planting lists ${firstYear}`
    : `Planting lists ${firstYear}–${lastYear}`;
const MONITORING_DATE = `Monitoring visits up to ${month(data.monitoring_up_to, "long")}`;

const SPECIES = data.species;
const TOTAL_SEEDLINGS = SPECIES.reduce((sum, s) => sum + s.seedlings, 0);

const num = (n) => n.toLocaleString("en-US");

const KPIS = [
  {
    title: "Estimated carbon removals over the project lifetime",
    value: num(data.carbon.tco2e),
    note: `tCO2e, projected ${month(data.carbon.period_start, "short")} – ${month(data.carbon.period_end, "short")}`,
    highlight: true,
  },
  {
    // Lists without a plot size column count at their nominal area.
    title: "Hectares planted",
    value: num(data.hectares),
    note: "Includes estimated plot areas",
    footer: PLANTING_DATE,
  },
  {
    title: "Farmers' plots planted on",
    value: num(data.plots),
    note: "Plots on the planting lists",
    footer: PLANTING_DATE,
  },
  {
    title: "Seedlings planted",
    value: num(TOTAL_SEEDLINGS),
    note: "Across four species",
    footer: PLANTING_DATE,
  },
  {
    title: "Survival rate",
    value: `${data.survival_rate}%`,
    note: `${num(data.monitored_plots)} monitored plots`,
    footer: MONITORING_DATE,
  },
];

function Kpi({ title, value, note, footer, highlight = false }) {
  return (
    <Card className={highlight ? "border-amber-300 bg-amber-50" : undefined}>
      <CardHeader>
        <CardTitle className="text-md font-medium text-foreground">
          {title}
        </CardTitle>
        {highlight && (
          <CardAction>
            <Leaf className="size-4 text-amber-500" aria-hidden="true" />
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex-1">
        <div className="text-3xl font-bold">{value}</div>
        <p className="mt-1 text-sm text-muted-foreground">{note}</p>
      </CardContent>
      <CardFooter>
        <p className="text-xs text-muted-foreground">{footer}</p>
      </CardFooter>
    </Card>
  );
}

export function PlantingSection() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {KPIS.map((kpi) => (
          <Kpi key={kpi.title} {...kpi} />
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-md font-medium text-foreground">
            Species planted
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 text-sm text-muted-foreground">
            <span className="flex-1">Species</span>
            <span className="w-20 text-right">Seedlings</span>
            <span className="w-16 text-right">Survival</span>
          </div>
          <ul className="mt-2 space-y-3">
            {SPECIES.map((s) => (
              <li key={s.name} className="flex items-end gap-4">
                <div className="flex-1">
                  <span className="text-sm">{s.name}</span>
                  <ShareBar share={s.seedlings / TOTAL_SEEDLINGS} />
                </div>
                <span className="w-20 text-right text-sm">
                  <span className="sr-only">Seedlings: </span>
                  {num(s.seedlings)}
                </span>
                <span className="w-16 text-right text-sm">
                  <span className="sr-only">Survival: </span>
                  {s.survival_rate}%
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
        <CardFooter>
          <p className="text-xs text-muted-foreground">
            {PLANTING_DATE} · {MONITORING_DATE}
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
