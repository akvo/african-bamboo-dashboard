import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { FilterBar, getDateRange } from "@/components/filter-bar";

const mockRegions = [
  { value: "ET04", label: "Amhara" },
  { value: "ET07", label: "Oromia" },
];

const mockSubRegions = [
  { value: "ET0408", label: "Bahir Dar" },
  { value: "ET0412", label: "Gondar" },
];

const mockDynamicFilters = [
  {
    name: "species",
    label: "Species",
    options: [
      { name: "bamboo", label: "Bamboo" },
      { name: "eucalyptus", label: "Eucalyptus" },
    ],
  },
];

describe("FilterBar", () => {
  it("renders region and sub-region dropdowns", () => {
    render(
      <FilterBar regions={mockRegions} sub_regions={mockSubRegions} />,
    );
    expect(screen.getByText("Region")).toBeInTheDocument();
    expect(screen.getByText("Sub-region")).toBeInTheDocument();
  });

  it("renders date range selector", () => {
    render(<FilterBar />);
    expect(screen.getByText("Date range")).toBeInTheDocument();
  });

  it("renders reset button when region filter is active", () => {
    render(<FilterBar region="ET04" />);
    expect(
      screen.getByRole("button", { name: /reset/i }),
    ).toBeInTheDocument();
  });

  it("does not render reset button when no filters are active", () => {
    render(<FilterBar />);
    expect(
      screen.queryByRole("button", { name: /reset/i }),
    ).not.toBeInTheDocument();
  });

  it("renders reset button when datePreset is active", () => {
    render(<FilterBar datePreset="7days" />);
    expect(
      screen.getByRole("button", { name: /reset/i }),
    ).toBeInTheDocument();
  });

  it("does not render advanced filters button when no filters available", () => {
    render(<FilterBar />);
    expect(
      screen.queryByRole("button", { name: /advanced filters/i }),
    ).not.toBeInTheDocument();
  });

  it("renders advanced filters button when dynamic filters are provided", () => {
    render(<FilterBar dynamicFilters={mockDynamicFilters} />);
    expect(
      screen.getByRole("button", { name: /advanced filters/i }),
    ).toBeInTheDocument();
  });

  it("renders advanced filters button when only regions are provided", () => {
    render(<FilterBar regions={mockRegions} />);
    expect(
      screen.getByRole("button", { name: /advanced filters/i }),
    ).toBeInTheDocument();
  });

  it("renders advanced filters button when only sub-regions are provided", () => {
    render(<FilterBar sub_regions={mockSubRegions} />);
    expect(
      screen.getByRole("button", { name: /advanced filters/i }),
    ).toBeInTheDocument();
  });

  it("does not render region dropdown when regions array is empty", () => {
    render(<FilterBar regions={[]} sub_regions={mockSubRegions} />);
    expect(screen.queryByText("Region")).not.toBeInTheDocument();
  });

  it("does not render sub-region dropdown when sub_regions array is empty", () => {
    render(<FilterBar regions={mockRegions} sub_regions={[]} />);
    expect(screen.queryByText("Sub-region")).not.toBeInTheDocument();
  });

  it("renders active filter chips when region is selected", () => {
    render(<FilterBar region="ET04" regions={mockRegions} />);
    const chip = screen.getByTestId("filter-chip-region");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("Amhara");
  });

  it("clears region when chip dismiss is clicked", () => {
    const onRegionChange = jest.fn();
    render(
      <FilterBar
        region="ET04"
        regions={mockRegions}
        onRegionChange={onRegionChange}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /remove amhara filter/i }),
    );
    expect(onRegionChange).toHaveBeenCalledWith("");
  });

  it("renders dynamic filter chip with label prefix", () => {
    render(
      <FilterBar
        dynamicFilters={mockDynamicFilters}
        dynamicValues={{ species: "bamboo" }}
      />,
    );
    expect(screen.getByText("Species: Bamboo")).toBeInTheDocument();
  });

  it("clears dynamic filter when chip dismiss is clicked", () => {
    const onDynamicFilterChange = jest.fn();
    render(
      <FilterBar
        dynamicFilters={mockDynamicFilters}
        dynamicValues={{ species: "bamboo" }}
        onDynamicFilterChange={onDynamicFilterChange}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /remove species: bamboo filter/i,
      }),
    );
    expect(onDynamicFilterChange).toHaveBeenCalledWith("species", "");
  });

  it("shows correct count badge on filter button", () => {
    render(
      <FilterBar
        region="ET04"
        regions={mockRegions}
        datePreset="7days"
      />,
    );
    // region chip + datePreset = 2
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not render chips when no filters are active", () => {
    render(<FilterBar regions={mockRegions} />);
    expect(
      screen.queryByTestId("filter-chip-region"),
    ).not.toBeInTheDocument();
  });

  it("shows dynamic filters and region/sub-region in dialog", () => {
    render(
      <FilterBar
        regions={mockRegions}
        sub_regions={mockSubRegions}
        dynamicFilters={mockDynamicFilters}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /advanced filters/i }),
    );
    expect(screen.getByText("Advanced Filters")).toBeInTheDocument();
    expect(screen.getByText("Species")).toBeInTheDocument();
    // Region and sub-region are also shown inside the dialog
    expect(screen.getByText("Select region")).toBeInTheDocument();
    expect(screen.getByText("Select sub-region")).toBeInTheDocument();
  });
});

describe("getDateRange", () => {
  it("returns null dates for no preset", () => {
    const { start, end } = getDateRange(null);
    expect(start).toBeNull();
    expect(end).toBeNull();
  });

  it("returns a 7-day range", () => {
    const { start, end } = getDateRange("7days");
    expect(end - start).toBe(7 * 86400000);
  });

  it("returns a 30-day range", () => {
    const { start, end } = getDateRange("30days");
    expect(end - start).toBe(30 * 86400000);
  });

  it("returns a 90-day range", () => {
    const { start, end } = getDateRange("90days");
    expect(end - start).toBe(90 * 86400000);
  });

  it("returns null dates for unknown preset", () => {
    const { start, end } = getDateRange("unknown");
    expect(start).toBeNull();
    expect(end).toBeNull();
  });
});
