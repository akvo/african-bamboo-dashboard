import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { PlantingSection } from "@/components/planting-section";

describe("PlantingSection", () => {
  it("renders the headline figures", () => {
    render(<PlantingSection />);
    expect(screen.getByText("14,404,611")).toBeInTheDocument();
    expect(screen.getByText("169.8")).toBeInTheDocument();
    expect(screen.getByText("799")).toBeInTheDocument();
    expect(screen.getByText("167,056")).toBeInTheDocument();
    expect(screen.getByText("90.9%")).toBeInTheDocument();
    expect(screen.getByText("264 monitored plots")).toBeInTheDocument();
  });

  it("renders each species with seedlings and survival", () => {
    render(<PlantingSection />);
    const rows = [
      ["Yushania alpina (highland bamboo)", "39,520", "91.3%"],
      ["Millettia ferruginea", "26,624", "88.4%"],
      ["Hagenia abyssinica", "26,624", "90.8%"],
      ["Morus alba (mulberry)", "74,288", "91.6%"],
    ];
    for (const [name, seedlings, survival] of rows) {
      const row = screen.getByText(name).closest("li");
      expect(row).toHaveTextContent(`Seedlings: ${seedlings}`);
      expect(row).toHaveTextContent(`Survival: ${survival}`);
    }
  });

  it("sizes each species bar by its share of all seedlings", () => {
    render(<PlantingSection />);
    const row = screen.getByText("Morus alba (mulberry)").closest("li");
    const bar = row.querySelector("[style]");
    expect(parseFloat(bar.style.width)).toBeCloseTo((74288 / 167056) * 100);
  });
});
