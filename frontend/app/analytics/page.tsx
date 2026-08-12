"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  Line, Area, ComposedChart, ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import {
  analytics, type TopSkill, type RemoteBreakdown, type TopCompany, type TopLocation,
  type DashboardSummary, type SalaryBySkill, type SkillForecast,
} from "@/lib/api";
import { TrendingUp, TrendingDown, Minus, Search, Briefcase, Building2, Globe2, MapPin } from "lucide-react";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="py-5">
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <div className="font-medium">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="text-muted-foreground">{p.name}: <span className="font-medium text-foreground">{p.value.toLocaleString()}</span></div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [topSkills, setTopSkills] = useState<TopSkill[] | null>(null);
  const [remote, setRemote] = useState<RemoteBreakdown[] | null>(null);
  const [companies, setCompanies] = useState<TopCompany[] | null>(null);
  const [locations, setLocations] = useState<TopLocation[] | null>(null);

  const [salarySkill, setSalarySkill] = useState("Python");
  const [salaryData, setSalaryData] = useState<SalaryBySkill | null | undefined>(undefined);
  const [forecast, setForecast] = useState<SkillForecast | null | undefined>(undefined);
  const [forecastSkill, setForecastSkill] = useState("Python");

  useEffect(() => {
    analytics.summary().then(setSummary).catch(() => {});
    analytics.topSkills({ limit: 10 }).then(setTopSkills).catch(() => setTopSkills([]));
    analytics.remoteBreakdown().then(setRemote).catch(() => setRemote([]));
    analytics.topCompanies({ limit: 8 }).then(setCompanies).catch(() => setCompanies([]));
    analytics.topLocations({ limit: 8 }).then(setLocations).catch(() => setLocations([]));
  }, []);

  useEffect(() => {
    fetchSalary(salarySkill);
    fetchForecast(forecastSkill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function fetchSalary(skill: string) {
    setSalaryData(undefined);
    analytics.salaryBySkill(skill).then(setSalaryData).catch(() => setSalaryData(null));
  }

  function fetchForecast(skill: string) {
    setForecast(undefined);
    analytics.forecast(skill).then(setForecast).catch(() => setForecast(null));
  }

  const trendIcon = (trend: string) => {
    if (trend === "growing") return <TrendingUp className="h-4 w-4" style={{ color: "var(--status-good)" }} />;
    if (trend === "declining") return <TrendingDown className="h-4 w-4" style={{ color: "var(--status-critical)" }} />;
    return <Minus className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <PageContainer>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Market Intelligence</h1>
        <p className="mt-1 text-muted-foreground">Built live from the jobs database — updates as new listings are ingested.</p>
      </div>

      {summary && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatTile label="Active jobs" value={summary.total_active_jobs.toLocaleString()} />
          <StatTile label="Companies" value={summary.total_companies.toLocaleString()} />
          <StatTile label="Countries" value={summary.total_countries} />
          <StatTile label="Remote roles" value={summary.remote_jobs.toLocaleString()} />
          <StatTile label="New today" value={summary.new_today.toLocaleString()} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-base"><Briefcase className="h-4 w-4" /> Top skills by demand</CardTitle>
            <CardDescription>Number of active postings requiring each skill</CardDescription>
          </CardHeader>
          <CardContent>
            {!topSkills ? (
              <Skeleton className="h-72 w-full" />
            ) : topSkills.length === 0 ? (
              <EmptyState text="No skill data yet — skill extraction runs shortly after ingestion." />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={[...topSkills].reverse()} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                  <XAxis type="number" tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" allowDecimals={false} />
                  <YAxis type="category" dataKey="skill" width={90} tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--secondary)" }} />
                  <Bar dataKey="job_count" name="Jobs" fill="var(--chart-1)" radius={[0, 4, 4, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-base"><Globe2 className="h-4 w-4" /> Remote vs onsite</CardTitle>
            <CardDescription>Work-type breakdown across active listings</CardDescription>
          </CardHeader>
          <CardContent>
            {!remote ? (
              <Skeleton className="h-72 w-full" />
            ) : remote.length === 0 ? (
              <EmptyState text="No data yet." />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={remote} margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="remote_type" tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" className="capitalize" />
                  <YAxis tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" allowDecimals={false} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--secondary)" }} />
                  <Bar dataKey="count" name="Jobs" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    {remote.map((_, i) => (
                      <Cell key={i} fill={`var(--chart-${(i % 5) + 1})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-base"><Building2 className="h-4 w-4" /> Top hiring companies</CardTitle>
            <CardDescription>By number of open roles</CardDescription>
          </CardHeader>
          <CardContent>
            {!companies ? (
              <Skeleton className="h-72 w-full" />
            ) : companies.length === 0 ? (
              <EmptyState text="No data yet." />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={[...companies].reverse()} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                  <XAxis type="number" tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" allowDecimals={false} />
                  <YAxis type="category" dataKey="company" width={130} tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--secondary)" }} />
                  <Bar dataKey="open_roles" name="Open roles" fill="var(--chart-1)" radius={[0, 4, 4, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-base"><MapPin className="h-4 w-4" /> Top locations</CardTitle>
            <CardDescription>By number of active listings</CardDescription>
          </CardHeader>
          <CardContent>
            {!locations ? (
              <Skeleton className="h-72 w-full" />
            ) : locations.length === 0 ? (
              <EmptyState text="No data yet." />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={[...locations].reverse()} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                  <XAxis type="number" tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" allowDecimals={false} />
                  <YAxis type="category" dataKey="location" width={110} tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--secondary)" }} />
                  <Bar dataKey="job_count" name="Jobs" fill="var(--chart-3)" radius={[0, 4, 4, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Salary by skill</CardTitle>
            <CardDescription>Min / average / max across active postings requiring this skill</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => { e.preventDefault(); fetchSalary(salarySkill); }}
              className="mb-4 flex gap-2"
            >
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={salarySkill} onChange={(e) => setSalarySkill(e.target.value)} placeholder="e.g. Python" className="pl-9" />
              </div>
              <Button type="submit">Look up</Button>
            </form>
            {salaryData === undefined ? (
              <Skeleton className="h-24 w-full" />
            ) : salaryData === null ? (
              <EmptyState text={`No salary data for "${salarySkill}" yet.`} />
            ) : (
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <div className="text-xl font-bold tabular-nums">£{salaryData.salary_min?.toLocaleString() ?? "–"}</div>
                  <div className="text-xs text-muted-foreground">Min</div>
                </div>
                <div>
                  <div className="text-xl font-bold tabular-nums" style={{ color: "var(--chart-1)" }}>£{salaryData.salary_avg?.toLocaleString() ?? "–"}</div>
                  <div className="text-xs text-muted-foreground">Average</div>
                </div>
                <div>
                  <div className="text-xl font-bold tabular-nums">£{salaryData.salary_max?.toLocaleString() ?? "–"}</div>
                  <div className="text-xs text-muted-foreground">Max</div>
                </div>
                <div className="col-span-3 mt-1">
                  <Badge variant="outline">{salaryData.job_count} postings</Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Demand forecast</CardTitle>
            <CardDescription>90-day Prophet forecast built from daily market snapshots</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => { e.preventDefault(); fetchForecast(forecastSkill); }}
              className="mb-4 flex gap-2"
            >
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={forecastSkill} onChange={(e) => setForecastSkill(e.target.value)} placeholder="e.g. Python" className="pl-9" />
              </div>
              <Button type="submit">Forecast</Button>
            </form>
            {forecast === undefined ? (
              <Skeleton className="h-40 w-full" />
            ) : forecast === null ? (
              <EmptyState text="Not enough history yet — the forecaster needs 30+ days of daily market snapshots. Run `make snapshot` daily to build history." />
            ) : (
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-muted-foreground">Current demand</div>
                    <div className="text-2xl font-bold tabular-nums">{forecast.current_demand}</div>
                  </div>
                  <div className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium capitalize">
                    {trendIcon(forecast.trend)} {forecast.trend}
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={160}>
                  <ComposedChart
                    data={[
                      { period: "Now", value: forecast.current_demand },
                      { period: "30d", value: forecast.forecast_30d },
                      { period: "60d", value: forecast.forecast_60d },
                      { period: "90d", value: forecast.forecast_90d, low: forecast.confidence_low, high: forecast.confidence_high },
                    ]}
                    margin={{ left: 8, right: 16 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="period" tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" />
                    <YAxis tick={{ fontSize: 12 }} stroke="var(--muted-foreground)" allowDecimals={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <ReferenceLine y={forecast.current_demand} stroke="var(--muted-foreground)" strokeDasharray="3 3" />
                    <Area dataKey="high" stroke="none" fill="var(--chart-1)" fillOpacity={0.08} />
                    <Line dataKey="value" name="Predicted" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 3 }} />
                  </ComposedChart>
                </ResponsiveContainer>
                <div className="text-xs text-muted-foreground">
                  80% confidence interval at 90 days: {forecast.confidence_low}–{forecast.confidence_high} · based on {forecast.data_points} days of history
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-lg border border-dashed px-6 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}
