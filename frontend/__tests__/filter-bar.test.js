import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { FilterBar } from "@/components/filter-bar";

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

  it("renders date range controls", () => {
    render(<FilterBar />);
    expect(screen.getByText("Date range")).toBeInTheDocument();
    expect(screen.getByText("Pick dates")).toBeInTheDocument();
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

  it("renders reset button when date range is active", () => {
    render(<FilterBar startDate={new Date(2025, 0, 1)} endDate={new Date(2025, 0, 31)} />);
    expect(
      screen.getByRole("button", { name: /reset/i }),
    ).toBeInTheDocument();
  });

  it("displays formatted date range when dates are provided", () => {
    render(
      <FilterBar
        startDate={new Date(2025, 0, 1)}
        endDate={new Date(2025, 0, 31)}
      />,
    );
    expect(screen.getByText("01 Jan 2025 - 31 Jan 2025")).toBeInTheDocument();
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

  it("renders advanced filters button when only availableFilters are provided", () => {
    render(<FilterBar availableFilters={mockAvailableFilters} />);
    expect(
      screen.getByRole("button", { name: /advanced filters/i }),
    ).toBeInTheDocument();
  });
});

const mockAvailableFilters = [
  {
    name: "species",
    label: "Species",
    type: "select_one",
    options: [
      { name: "bamboo", label: "Bamboo" },
      { name: "eucalyptus", label: "Eucalyptus" },
    ],
  },
  {
    name: "variety",
    label: "Variety",
    type: "select_one",
    options: [
      { name: "highland", label: "Highland" },
      { name: "lowland", label: "Lowland" },
    ],
  },
];

describe("FilterBar - Manage Filters", () => {
  it("shows manage filters section in advanced filters dialog", () => {
    render(
      <FilterBar
        dynamicFilters={mockDynamicFilters}
        availableFilters={mockAvailableFilters}
        activeFilterFields={["species"]}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /advanced filters/i }),
    );
    expect(screen.getByText("Manage Filters")).toBeInTheDocument();
  });

  it("shows toggle switches for available filters", () => {
    render(
      <FilterBar
        dynamicFilters={mockDynamicFilters}
        availableFilters={mockAvailableFilters}
        activeFilterFields={["species"]}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /advanced filters/i }),
    );
    expect(screen.getByText("Variety")).toBeInTheDocument();
  });

  it("does not show manage filters when no available filters", () => {
    render(
      <FilterBar
        dynamicFilters={mockDynamicFilters}
        availableFilters={[]}
        activeFilterFields={[]}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /advanced filters/i }),
    );
    expect(screen.queryByText("Manage Filters")).not.toBeInTheDocument();
  });
});
