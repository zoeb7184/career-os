"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore, isApiError } from "@/lib/auth-store";
import { cn } from "@/lib/utils";
import { Loader2, Briefcase, Check, CheckCircle2, XCircle } from "lucide-react";

// ── Password strength scoring ──────────────────────────────────────
// Plain client-side heuristic, no external library. Score is additive out
// of 100, then clamped to 10 if the password is a well-known weak one —
// length/character-class bonuses on "password123" shouldn't outscore that.

const COMMON_PASSWORDS = [
  "password", "123456", "qwerty", "abc123", "password123", "admin", "letmein", "welcome",
];
const SPECIAL_CHAR_RE = /[!@#$%^&*]/;

function scorePassword(password: string): number {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 8) score += 20;
  if (password.length >= 12) score += 10;
  if (password.length >= 16) score += 10;
  if (/[A-Z]/.test(password)) score += 15;
  if (/[a-z]/.test(password)) score += 10;
  if (/[0-9]/.test(password)) score += 15;
  if (SPECIAL_CHAR_RE.test(password)) score += 20;
  if (COMMON_PASSWORDS.includes(password.toLowerCase())) score = Math.min(score, 10);
  return Math.min(score, 100);
}

function strengthLabel(score: number): string {
  if (score <= 40) return "Weak";
  if (score <= 70) return "Fair";
  if (score <= 90) return "Strong";
  return "Very Strong";
}

// Colors reuse the app's existing status tokens rather than raw Tailwind
// reds/greens, so the meter stays on-palette in both themes.
function strengthColorVar(score: number): string {
  if (score <= 40) return "var(--status-critical)";
  if (score <= 70) return "var(--status-serious)";
  return "var(--status-good)";
}

const MIN_SUBMIT_SCORE = 40;

function passwordChecklist(password: string) {
  return [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "Uppercase letter (A-Z)", met: /[A-Z]/.test(password) },
    { label: "Lowercase letter (a-z)", met: /[a-z]/.test(password) },
    { label: "Number (0-9)", met: /[0-9]/.test(password) },
    { label: "Special character (!@#$%^&*)", met: SPECIAL_CHAR_RE.test(password) },
  ];
}

function PasswordStrengthMeter({ password }: { password: string }) {
  if (!password) return null;
  const score = scorePassword(password);
  const color = strengthColorVar(score);
  const checklist = passwordChecklist(password);

  return (
    <div className="flex flex-col gap-2 pt-1">
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${score}%`, backgroundColor: color }}
          />
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums" style={{ color }}>
          {strengthLabel(score)} · {score}%
        </span>
      </div>
      <ul className="grid grid-cols-1 gap-y-1 sm:grid-cols-2 sm:gap-x-3">
        {checklist.map((item) => (
          <li
            key={item.label}
            className={cn(
              "flex items-center gap-1.5 text-xs",
              item.met ? "text-[color:var(--status-good)]" : "text-muted-foreground"
            )}
          >
            <span className={cn(
              "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border",
              item.met ? "border-transparent bg-[color:var(--status-good)] text-white" : "border-muted-foreground/40"
            )}>
              {item.met && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
            </span>
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordScore = scorePassword(password);
  const passwordsMatch = confirm.length > 0 && password === confirm;
  const tooWeak = passwordScore < MIN_SUBMIT_SCORE;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
      toast.success("Account created!");
      router.push("/dashboard");
    } catch (err) {
      setError(isApiError(err) ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-16">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Briefcase className="h-5 w-5" />
          </div>
          <CardTitle className="text-xl">Create an account</CardTitle>
          <CardDescription>Start tracking your job search</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
              />
              <PasswordStrengthMeter password={password} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                required
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
              />
              {confirm.length > 0 && (
                <div className={cn(
                  "flex items-center gap-1.5 text-xs font-medium",
                  passwordsMatch ? "text-[color:var(--status-good)]" : "text-destructive"
                )}>
                  {passwordsMatch ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5" />
                  )}
                  {passwordsMatch ? "Passwords match" : "Passwords do not match"}
                </div>
              )}
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div
              className="mt-1 block"
              title={tooWeak ? "Please choose a stronger password" : undefined}
            >
              <Button type="submit" disabled={loading || tooWeak} className="w-full">
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Sign up
              </Button>
            </div>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
