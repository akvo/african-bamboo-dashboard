import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { PlantingSection } from "@/components/planting-section";

// Fixed figures, so a yearly rebuild of planting.json leaves these
// tests alone.
jest.mock("../src/data/planting.json", () => ({
  planting_years: [2024, 2025],
  hectares: 12.5,
  plots: 1234,
  monitoring_up_to: "2026-07-25",
  survival_rate: 90.9,
  monitored_plots: 266,
  species: [
    { name: "Yushania alpina", seedlings: 1000, survival_rate: 91.3 },
    { name: "Morus alba", seedlings: 3000, survival_rate: 88 },
  ],
  carbon: {
    tco2e: 14404611,
    period_start: "2024-08-01",
    period_end: "2064-07-31",
  },
}));

describe("PlantingSection", () => {
  it("renders the headline figures", () => {
    render(<PlantingSection />);
    expect(screen.getByText("14,404,611")).toBeInTheDocument();
    expect(screen.getByText("tCO2e, projected")).toBeInTheDocument();
    expect(
      screen.getByText("Crediting period Aug 2024 – Jul 2064"),
    ).toBeInTheDocument();
    expect(screen.getByText("12.5")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("4,000")).toBeInTheDocument();
    expect(screen.getByText("90.9%")).toBeInTheDocument();
    expect(screen.getByText("266 monitored plots")).toBeInTheDocument();
  });

  it("labels the planting years and the last monitoring month", () => {
    render(<PlantingSection />);
    expect(
      screen.getAllByText("Planting lists 2024–2025").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText("Monitoring visits up to July 2026"),
    ).toBeInTheDocument();
  });

  it("renders each species with seedlings and survival", () => {
    render(<PlantingSection />);
    const rows = [
      ["Yushania alpina", "1,000", "91.3%"],
      ["Morus alba", "3,000", "88%"],
    ];
    for (const [name, seedlings, survival] of rows) {
      const row = screen.getByText(name).closest("li");
      expect(row).toHaveTextContent(`Seedlings: ${seedlings}`);
      expect(row).toHaveTextContent(`Survival: ${survival}`);
    }
  });

  it("sizes each species bar by its share of all seedlings", () => {
    render(<PlantingSection />);
    const row = screen.getByText("Morus alba").closest("li");
    const bar = row.querySelector("[style]");
    expect(parseFloat(bar.style.width)).toBeCloseTo(75);
  });
});
