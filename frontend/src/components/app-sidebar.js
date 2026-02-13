"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Map,
  Users,
  LifeBuoy,
  Settings,
  // Search,
  PanelLeftClose,
  PanelLeft,
  Menu,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
// import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: BarChart3,
  },
  {
    label: "Map",
    href: "/dashboard/map",
    icon: Map,
  },
  {
    label: "Forms",
    href: "/dashboard/forms",
    icon: FileText,
  },
];

function NavItem({ item, isCollapsed, isActive }) {
  const Icon = item.icon;

  if (isCollapsed) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center gap-1 rounded-md p-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
            >
              <Icon className="size-5" />
              <span className="text-[10px] text-center leading-tight">
                {item.label}
              </span>
            </Link>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{item.label}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
      )}
    >
      <Icon className="size-5 shrink-0" />
      <span className="text-sm">{item.label}</span>
    </Link>
  );
}

function SidebarContent({ isCollapsed, onToggle }) {
  const pathname = usePathname();

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-sidebar-border p-4">
        <div className="flex items-center gap-2">
          <Logo size={isCollapsed ? 24 : 32} />
        </div>
        {!isCollapsed && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggle}
            className="shrink-0"
          >
            <PanelLeftClose className="size-5" />
          </Button>
        )}
        {isCollapsed && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggle}
            className="absolute -right-3 top-4 z-10 size-6 rounded-full border border-sidebar-border bg-sidebar shadow-md"
          >
            <PanelLeft className="size-4" />
          </Button>
        )}
      </div>

      {/* Search */}
      {/* {!isCollapsed && (
        <div className="px-3 py-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-sidebar-foreground/60" />
            <Input
              type="search"
              placeholder="Search..."
              className="pl-8 bg-sidebar-accent/50 border-sidebar-border text-sidebar-foreground placeholder:text-sidebar-foreground/60"
            />
          </div>
        </div>
      )} */}

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-2">
        {navItems.map((item) => (
          <NavItem
            key={item.href}
            item={item}
            isCollapsed={isCollapsed}
            isActive={pathname === item.href}
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="mt-auto border-t border-sidebar-border">
        <div className="space-y-1 px-2 py-2">
          {!isCollapsed && (
            <Link
              href="/dashboard/support"
              className="flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            >
              <LifeBuoy className="size-5 shrink-0" />
              <span className="text-sm">Support</span>
            </Link>
          )}
          {isCollapsed ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link
                    href="/dashboard/settings"
                    className="flex flex-col items-center justify-center gap-1 rounded-md p-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                  >
                    <Settings className="size-5" />
                    <span className="text-[10px]">Settings</span>
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p>Settings</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            >
              <Settings className="size-5 shrink-0" />
              <span className="text-sm">Settings</span>
            </Link>
          )}
        </div>
      </div>
    </>
  );
}

export function AppSidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Header */}
      <div className="flex items-center justify-between border-b bg-background p-4 md:hidden">
        <div className="flex items-center gap-2">
          <Logo size={28} />
          <span className="font-semibold text-lg">African Bamboo</span>
        </div>
        <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon-sm">
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent
            side="left"
            className="w-60 p-0 bg-sidebar text-sidebar-foreground border-sidebar-border"
            showCloseButton={false}
          >
            <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
            <SidebarContent
              isCollapsed={false}
              onToggle={() => setIsMobileOpen(false)}
            />
          </SheetContent>
        </Sheet>
      </div>

      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-all duration-300 relative",
          isCollapsed ? "w-16" : "w-60",
        )}
      >
        <SidebarContent
          isCollapsed={isCollapsed}
          onToggle={() => setIsCollapsed(!isCollapsed)}
        />
      </aside>
    </>
  );
}
