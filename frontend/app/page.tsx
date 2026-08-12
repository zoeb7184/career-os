"use client";

import Link from "next/link";
import { ButtonLink } from "@/components/button-link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { PageContainer } from "@/components/page-container";
import {
  Search, FileCheck2, Sparkles, BarChart3, MessageSquareText, Kanban,
  ArrowRight, Database,
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
      <section className="border-b bg-gradient-to-b from-secondary/40 to-background">
        <PageContainer className="py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
              <Database className="h-3.5 w-3.5" />
              {summary ? `${summary.total_active_jobs.toLocaleString()} live jobs · ${summary.total_companies.toLocaleString()} companies` : "Live job market data"}
            </div>
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
              Your AI Career<br className="hidden sm:block" /> Operating System
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
            </div>
          </div>
        </PageContainer>
      </section>

      <PageContainer className="py-16 sm:py-20">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <Link key={f.title} href={f.href} className="group">
              <Card className="h-full transition-colors group-hover:border-primary/50">
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
