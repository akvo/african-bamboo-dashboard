import { Logo } from "@/components/logo";
import { LoginForm } from "./login-form";

export const metadata = {
  title: "Sign In - African Bamboo Dashboard",
  description: "Sign in with your KoboToolbox credentials",
};

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center text-foreground">
          <Logo size={80} />
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
