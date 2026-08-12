"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Briefcase, LayoutDashboard, Search, FileCheck2, BarChart3, MessageSquareText, Kanban, Menu, X } from "lucide-react";
import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { ButtonLink } from "@/components/button-link";
import { useAuthStore } from "@/lib/auth-store";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const links = [
  { href: "/jobs", label: "Jobs", icon: Search },
  { href: "/ats", label: "ATS Score", icon: FileCheck2 },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/advisor", label: "Advisor", icon: MessageSquareText },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tracker", label: "Tracker", icon: Kanban },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { token, email, logout, hydrated } = useAuthStore();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Briefcase className="h-5 w-5 text-primary" />
          <span>Career OS</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {links.map((l) => {
            const active = pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                )}
              >
                <l.icon className="h-4 w-4" />
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-2">
          {hydrated && token ? (
            <DropdownMenu>
              <DropdownMenuTrigger className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-2")}>
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="text-xs">{email?.[0]?.toUpperCase() ?? "U"}</AvatarFallback>
                </Avatar>
                <span className="max-w-[140px] truncate">{email}</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => router.push("/dashboard")}>Dashboard</DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push("/tracker")}>Application tracker</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                >
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <ButtonLink href="/login" variant="ghost" size="sm">Log in</ButtonLink>
              <ButtonLink href="/register" size="sm">Sign up</ButtonLink>
            </>
          )}
        </div>

        <button className="md:hidden p-2" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t px-4 py-3 flex flex-col gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium hover:bg-secondary"
            >
              <l.icon className="h-4 w-4" />
              {l.label}
            </Link>
          ))}
          <div className="border-t my-2" />
          {hydrated && token ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                logout();
                setOpen(false);
                router.push("/");
              }}
            >
              Log out ({email})
            </Button>
          ) : (
            <div className="flex gap-2">
              <ButtonLink href="/login" onClick={() => setOpen(false)} variant="outline" size="sm" className="flex-1">
                Log in
              </ButtonLink>
              <ButtonLink href="/register" onClick={() => setOpen(false)} size="sm" className="flex-1">
                Sign up
              </ButtonLink>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
