import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { SortableHeader, getAriaSort } from "@/components/table-view";

// Mock lucide-react to render identifiable elements
jest.mock("lucide-react", () => ({
  ArrowDown: (props) => <svg data-testid="arrow-down" {...props} />,
  ArrowUp: (props) => <svg data-testid="arrow-up" {...props} />,
  ArrowUpDown: (props) => <svg data-testid="arrow-up-down" {...props} />,
  FileIcon: (props) => <svg data-testid="file-icon" {...props} />,
}));

describe("SortableHeader", () => {
  const columnKey = "start";

  describe("icon rendering", () => {
    it("shows ArrowUpDown when column is not sorted", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort={null}
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      expect(screen.getByTestId("arrow-up-down")).toBeInTheDocument();
      expect(screen.queryByTestId("arrow-up")).not.toBeInTheDocument();
      expect(screen.queryByTestId("arrow-down")).not.toBeInTheDocument();
    });

    it("shows ArrowUp when column is sorted ascending", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      expect(screen.getByTestId("arrow-up")).toBeInTheDocument();
      expect(screen.queryByTestId("arrow-down")).not.toBeInTheDocument();
      expect(screen.queryByTestId("arrow-up-down")).not.toBeInTheDocument();
    });

    it("shows ArrowDown when column is sorted descending", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="-start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      expect(screen.getByTestId("arrow-down")).toBeInTheDocument();
      expect(screen.queryByTestId("arrow-up")).not.toBeInTheDocument();
      expect(screen.queryByTestId("arrow-up-down")).not.toBeInTheDocument();
    });

    it("shows ArrowUpDown when a different column is sorted", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="kobo_id"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      expect(screen.getByTestId("arrow-up-down")).toBeInTheDocument();
    });
  });

  describe("click cycle: asc → desc → clear", () => {
    it("calls onSort with columnKey on first click (inactive → asc)", () => {
      const onSort = jest.fn();
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort={null}
          onSort={onSort}
        >
          Start date
        </SortableHeader>,
      );
      fireEvent.click(screen.getByRole("button"));
      expect(onSort).toHaveBeenCalledWith("start");
    });

    it("calls onSort with -columnKey on second click (asc → desc)", () => {
      const onSort = jest.fn();
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="start"
          onSort={onSort}
        >
          Start date
        </SortableHeader>,
      );
      fireEvent.click(screen.getByRole("button"));
      expect(onSort).toHaveBeenCalledWith("-start");
    });

    it("calls onSort with null on third click (desc → clear)", () => {
      const onSort = jest.fn();
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="-start"
          onSort={onSort}
        >
          Start date
        </SortableHeader>,
      );
      fireEvent.click(screen.getByRole("button"));
      expect(onSort).toHaveBeenCalledWith(null);
    });
  });

  describe("label rendering", () => {
    it("renders children text", () => {
      render(
        <SortableHeader
          columnKey="area_ha"
          currentSort={null}
          onSort={jest.fn()}
        >
          Area (ha)
        </SortableHeader>,
      );
      expect(screen.getByText("Area (ha)")).toBeInTheDocument();
    });
  });

  describe("icon CSS classes", () => {
    it("uses muted class when inactive", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort={null}
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const icon = screen.getByTestId("arrow-up-down");
      const cls = icon.getAttribute("class") || "";
      expect(cls).toContain("text-muted-foreground/50");
    });

    it("uses active class when ascending", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const icon = screen.getByTestId("arrow-up");
      const cls = icon.getAttribute("class") || "";
      expect(cls).not.toContain("text-muted-foreground/50");
      expect(cls).toContain("size-3.5");
    });

    it("uses active class when descending", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="-start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const icon = screen.getByTestId("arrow-down");
      const cls = icon.getAttribute("class") || "";
      expect(cls).not.toContain("text-muted-foreground/50");
      expect(cls).toContain("size-3.5");
    });
  });

  describe("accessibility", () => {
    it("has an aria-label describing sort state when inactive", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort={null}
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const btn = screen.getByRole("button");
      expect(btn).toHaveAttribute(
        "aria-label",
        "Sort by Start date, not sorted",
      );
    });

    it("has an aria-label describing ascending state", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const btn = screen.getByRole("button");
      expect(btn).toHaveAttribute(
        "aria-label",
        "Sort by Start date, sorted ascending",
      );
    });

    it("has an aria-label describing descending state", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="-start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const btn = screen.getByRole("button");
      expect(btn).toHaveAttribute(
        "aria-label",
        "Sort by Start date, sorted descending",
      );
    });

    it("hides the icon from assistive technology", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort="start"
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const icon = screen.getByTestId("arrow-up");
      expect(icon).toHaveAttribute("aria-hidden", "true");
    });

    it("has focus-visible ring styles on the button", () => {
      render(
        <SortableHeader
          columnKey={columnKey}
          currentSort={null}
          onSort={jest.fn()}
        >
          Start date
        </SortableHeader>,
      );
      const btn = screen.getByRole("button");
      const cls = btn.getAttribute("class") || "";
      expect(cls).toContain("focus-visible:ring-2");
    });
  });
});

describe("getAriaSort", () => {
  it("returns undefined when no sort is active", () => {
    expect(getAriaSort("start", null)).toBeUndefined();
  });

  it("returns undefined when a different column is sorted", () => {
    expect(getAriaSort("start", "kobo_id")).toBeUndefined();
  });

  it("returns 'ascending' when column is sorted ascending", () => {
    expect(getAriaSort("start", "start")).toBe("ascending");
  });

  it("returns 'descending' when column is sorted descending", () => {
    expect(getAriaSort("start", "-start")).toBe("descending");
  });
});
