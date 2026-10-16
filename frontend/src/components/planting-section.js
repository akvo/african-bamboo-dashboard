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

// Static figures (#61), derived from the client's workbooks per
// AB_KPI_Guidance_AKVO.docx.
const PLANTING_DATE = "Planting lists as of 19 May 2026";
const MONITORING_DATE = "Monitoring visits up to June 2026";

const SPECIES = [
  // Seedlings: species columns of the three planting lists.
  // Survival: latest visit per farmer, AB_Survival_Monitoring_2026.xlsx.
  {
    name: "Yushania alpina (highland bamboo)",
    seedlings: 39520,
    survival: "91.3%",
  },
  { name: "Millettia ferruginea", seedlings: 26624, survival: "88.4%" },
  { name: "Hagenia abyssinica", seedlings: 26624, survival: "90.8%" },
  { name: "Morus alba (mulberry)", seedlings: 74288, survival: "91.6%" },
];
const TOTAL_SEEDLINGS = SPECIES.reduce((sum, s) => sum + s.seedlings, 0);

const num = (n) => n.toLocaleString("en-US");

const KPIS = [
  {
    // AB_ER_Model_2026.xlsx, Net GHG Benefit!S54 (after risk buffer).
    title: "Estimated carbon removals over the project lifetime",
    value: num(14404611),
    note: "tCO2e, projected Aug 2024 – Jul 2064",
    footer: "Source: AB_ER_Model_2026.xlsx, Net GHG Benefit!S54",
    highlight: true,
  },
  {
    // 99.8 summed plot sizes (100 ha list) + 50 + 20 (ER model Inputs!D20).
    title: "Hectares planted",
    value: "169.8",
    note: "Includes estimated plot areas",
    footer: PLANTING_DATE,
  },
  {
    title: "Farmers' plots planted on",
    value: num(799),
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
    value: "90.9%",
    note: "264 monitored plots",
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
                  {s.survival}
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
