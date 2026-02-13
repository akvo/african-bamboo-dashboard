import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("Home (Landing Page)", () => {
  it("renders the title", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { name: /african bamboo/i })
    ).toBeInTheDocument();
  });

  it("renders the sign-in link", () => {
    render(<Home />);
    const link = screen.getByRole("link", { name: /sign in to dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/login");
  });

  it("renders the subtitle", () => {
    render(<Home />);
    expect(screen.getByText(/carbon sequestration/i)).toBeInTheDocument();
  });
});
