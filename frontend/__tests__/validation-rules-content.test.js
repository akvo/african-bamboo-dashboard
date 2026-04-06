import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";

import ValidationRulesContent from "@/components/validation-rules-content";

// Mock react-markdown (ESM-only) — render children as plain text
jest.mock("react-markdown", () => {
  const MockReactMarkdown = ({ children }) => (
    <div data-testid="markdown">{children}</div>
  );
  MockReactMarkdown.displayName = "ReactMarkdown";
  return { __esModule: true, default: MockReactMarkdown };
});

jest.mock("remark-gfm", () => ({
  __esModule: true,
  default: () => {},
}));

const SAMPLE_MD = `# Validation Rules

## On-Device Rules (ODK App)

| Rule | What It Checks |
|------|---------------|
| Min Vertices | At least 3 points |

- Warning one
- Warning two`;

describe("ValidationRulesContent", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("shows loading spinner initially", () => {
    // Never resolve fetch so it stays in loading state
    global.fetch = jest.fn(() => new Promise(() => {}));

    render(<ValidationRulesContent />);

    expect(screen.getByText("Loading validation rules...")).toBeInTheDocument();
  });

  it("renders markdown content after successful fetch", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        text: () => Promise.resolve(SAMPLE_MD),
      }),
    );

    render(<ValidationRulesContent />);

    await waitFor(() => {
      expect(screen.getByTestId("markdown")).toBeInTheDocument();
    });

    expect(screen.getByTestId("markdown")).toHaveTextContent(
      "Validation Rules",
    );
    expect(screen.getByTestId("markdown")).toHaveTextContent("Min Vertices");
    expect(screen.getByTestId("markdown")).toHaveTextContent("Warning one");
  });

  it("shows error message when fetch fails", async () => {
    global.fetch = jest.fn(() => Promise.reject(new Error("Network error")));

    render(<ValidationRulesContent />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Could not load validation rules. Please try again later.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when response is not ok", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 404,
      }),
    );

    render(<ValidationRulesContent />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Could not load validation rules. Please try again later.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("fetches from the correct URL", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        text: () => Promise.resolve("# Test"),
      }),
    );

    render(<ValidationRulesContent />);

    expect(global.fetch).toHaveBeenCalledWith("/docs/validation-rules.md");
  });
});
