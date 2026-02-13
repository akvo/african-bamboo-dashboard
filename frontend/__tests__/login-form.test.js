import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

// Mock the server action module (jose/server-only can't run in jsdom)
jest.mock("../src/app/actions/auth", () => ({
  login: jest.fn(),
}));

import { LoginForm } from "@/app/login/login-form";

describe("LoginForm", () => {
  it("renders all input fields", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText(/kobotoolbox server/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("renders the sign-in button", () => {
    render(<LoginForm />);
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("pre-fills the server URL", () => {
    render(<LoginForm />);
    const serverInput = screen.getByLabelText(/kobotoolbox server/i);
    expect(serverInput).toHaveValue("https://eu.kobotoolbox.org");
  });

  it("renders password toggle button", () => {
    render(<LoginForm />);
    expect(
      screen.getByRole("button", { name: /show password/i })
    ).toBeInTheDocument();
  });
});
