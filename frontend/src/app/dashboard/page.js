"use client";

import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DashboardHeader } from "@/components/dashboard-header";
import { StatCard } from "@/components/stat-card";
import { FilterBar } from "@/components/filter-bar";
import { SubmissionsTable } from "@/components/submissions-table";
import { TablePagination } from "@/components/table-pagination";
import { useForms } from "@/hooks/useForms";
import { usePlots } from "@/hooks/usePlots";
import { useSubmissions } from "@/hooks/useSubmissions";

const stats = [];

const DashboardPage = () => {
  const { activeForm } = useForms();

  const { data, count, isLoading, page, totalPages, setPage } = useSubmissions({
    assetUid: activeForm?.asset_uid,
  });
  const { plots } = usePlots({ formId: activeForm?.asset_uid });

  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");

  const filteredData = useMemo(() => {
    return data.filter((row) => {
      if (activeTab !== "all" && row.status !== activeTab) {
      }
      if (search) {
        const plotName = row?.plot_name || row?.instance_name || "";
        return plotName?.toLowerCase()?.includes(search.toLowerCase());
      }
      return true;
    });
  }, [data, activeTab, search]);

  return (
    <div className="space-y-6">
      <DashboardHeader />
      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Filters */}
      <FilterBar />

      {/* Form Section Header */}
      {activeForm && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">{activeForm.name}</h2>
            <Badge variant="secondary">{count} Data points</Badge>
          </div>
          <Button variant="outline" size="sm">
            <Download className="size-4" />
            Export data
          </Button>
        </div>
      )}

      {/* Table Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">View all</TabsTrigger>
            <TabsTrigger value="approved">Approved</TabsTrigger>
            <TabsTrigger value="pending">Pending</TabsTrigger>
            <TabsTrigger value="rejected">Rejected</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Submissions Table */}
      <SubmissionsTable
        data={filteredData}
        isLoading={isLoading}
        plots={plots}
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <TablePagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
};

export default DashboardPage;
