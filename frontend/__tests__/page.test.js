import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("Home", () => {
  it("renders the home page", () => {
    render(<Home />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders the deploy link", () => {
    render(<Home />);
    const deployLink = screen.getByRole("link", { name: /deploy now/i });
    expect(deployLink).toBeInTheDocument();
  });

  it("renders the docs link", () => {
    render(<Home />);
    const docsLink = screen.getByRole("link", { name: /read our docs/i });
    expect(docsLink).toBeInTheDocument();
  });
});
