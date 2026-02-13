export function DashboardHeader() {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold">
          African Bamboo - Carbon Sequestration Dashboard
        </h1>
        <p className="text-sm text-muted-foreground">
          Digital MRV Data Monitoring & Verification
        </p>
      </div>
    </div>
  );
}
