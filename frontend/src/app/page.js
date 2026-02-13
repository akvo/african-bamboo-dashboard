import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { LogIn } from "lucide-react";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#1a1a1a] px-6 text-white">
      <div className="flex flex-col items-center gap-8 text-center">
        <Logo size={120} />
        <div className="space-y-3">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            African Bamboo
          </h1>
          <p className="max-w-md text-lg text-white/60">
            Carbon Sequestration Dashboard — Digital MRV Data Monitoring &
            Verification
          </p>
        </div>
        <Button asChild size="lg" className="mt-4 h-14 px-10 text-lg">
          <Link href="/login">
            <LogIn className="size-5" />
            Sign in to Dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
