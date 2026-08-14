"use client";

import Link from "next/link";
import { ButtonLink } from "@/components/button-link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageContainer } from "@/components/page-container";
import {
  Search, FileCheck2, Sparkles, BarChart3, MessageSquareText, Kanban,
  ArrowRight, Database, FileSpreadsheet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { analytics, type DashboardSummary } from "@/lib/api";

const features = [
  {
    icon: Search,
    title: "Live job search",
    desc: "Search real listings ingested daily from Adzuna, Reed, and Remotive — filter by keyword, country, remote type, and salary.",
    href: "/jobs",
  },
  {
    icon: FileCheck2,
    title: "ATS resume scoring",
    desc: "Upload your resume against any job and get a 0–100 ATS score broken down by skill match, semantic similarity, structure, and keywords.",
    href: "/ats",
  },
  {
    icon: Sparkles,
    title: "Personalised recommendations",
    desc: "Vector search over your resume finds the jobs that actually fit — re-ranked by skill overlap and recency.",
    href: "/dashboard",
  },
  {
    icon: BarChart3,
    title: "Market intelligence",
    desc: "Top skills, salaries, hiring companies, and demand forecasts — built from the live jobs database.",
    href: "/analytics",
  },
  {
    icon: MessageSquareText,
    title: "AI career advisor",
    desc: "Ask career questions and get answers grounded in the live job market via retrieval-augmented generation.",
    href: "/advisor",
  },
  {
    icon: Kanban,
    title: "Application tracker",
    desc: "Save jobs and move them through a Kanban board — saved → applied → interview → offer.",
    href: "/tracker",
  },
];

export default function LandingPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    analytics.summary().then(setSummary).catch(() => {});
  }, []);

  return (
    <div className="flex-1">
      <section className="relative overflow-hidden border-b bg-[linear-gradient(180deg,var(--secondary)_0%,var(--background)_65%)]">
        {/* ambient glow accents — teal from the top-left, amber from the top-right */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full opacity-25 blur-3xl"
          style={{ background: "var(--primary)" }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 right-[-6rem] h-80 w-80 rounded-full opacity-20 blur-3xl"
          style={{ background: "var(--brand)" }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 [background-image:radial-gradient(circle_at_1px_1px,var(--foreground)_1px,transparent_0)] [background-size:28px_28px] opacity-[0.03]"
        />

        <PageContainer className="relative py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border bg-card/80 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
              <Database className="h-3.5 w-3.5 text-primary" />
              {summary ? `${summary.total_active_jobs.toLocaleString()} live jobs · ${summary.total_companies.toLocaleString()} companies` : "Live job market data"}
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
              Your AI Career<br className="hidden sm:block" />{" "}
              <span className="bg-[linear-gradient(90deg,var(--primary)_0%,var(--brand)_100%)] bg-clip-text text-transparent">
                Operating System
              </span>
            </h1>
            <p className="mt-6 text-lg text-muted-foreground">
              Search real jobs, score your resume against them, get personalised recommendations,
              and ask an AI advisor grounded in live market data — one platform, no guesswork.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <ButtonLink href="/jobs" size="lg">
                Browse jobs <ArrowRight className="h-4 w-4" />
              </ButtonLink>
              <ButtonLink href="/ats" size="lg" variant="outline">Score my resume</ButtonLink>
              <ButtonLink
                href="/import"
                size="lg"
                variant="outline"
                className="border-brand/40 text-brand hover:bg-brand/10 hover:text-brand dark:border-brand/50"
              >
                <Sparkles className="h-4 w-4" /> Smart Import
              </ButtonLink>
            </div>
          </div>
        </PageContainer>
      </section>

      <PageContainer className="py-16 sm:py-20">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <Link key={f.title} href={f.href} className="group">
              <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:border-primary/50 group-hover:shadow-md">
                <CardHeader>
                  <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <f.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">{f.title}</CardTitle>
                  <CardDescription>{f.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    Explore <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}

          {/* Smart Import — the newest addition, called out in the brand amber */}
          <Link href="/import" className="group sm:col-span-2 lg:col-span-3">
            <Card className="h-full border-brand/30 bg-[linear-gradient(120deg,color-mix(in_oklch,var(--brand)_8%,var(--card)),var(--card)_55%)] transition-all group-hover:-translate-y-0.5 group-hover:border-brand/60 group-hover:shadow-md">
              <CardContent className="flex flex-col items-start gap-4 py-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-brand/15 text-brand">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">Smart Import</h3>
                      <Badge className="bg-brand text-brand-foreground hover:bg-brand">New</Badge>
                    </div>
                    <p className="mt-1 max-w-xl text-sm text-muted-foreground">
                      Already tracking applications in a spreadsheet? Drop in an Excel or PDF export and
                      we&apos;ll auto-detect columns, normalise statuses, flag duplicates and stale
                      applications, and import everything straight into your tracker.
                    </p>
                  </div>
                </div>
                <span className="inline-flex shrink-0 items-center gap-1 self-end text-sm font-medium text-brand sm:self-center">
                  <FileSpreadsheet className="h-4 w-4" /> Import now <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </CardContent>
            </Card>
          </Link>
        </div>
      </PageContainer>

      <section className="border-t bg-secondary/30">
        <PageContainer className="py-16 text-center">
          <h2 className="text-2xl font-semibold">Built as a real production system</h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
            FastAPI · PostgreSQL · Redis · Qdrant · Prefect · Celery · Groq LLM (Llama 3) — every module
            is a self-contained node with its own health check, structured logs, and error codes.
          </p>
        </PageContainer>
      </section>
    </div>
  );
}
