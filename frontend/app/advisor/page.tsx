"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PageContainer } from "@/components/page-container";
import { advisor as advisorApi } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { MessageSquareText, Send, Loader2, Sparkles, User as UserIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  jobCount?: number;
  pending?: boolean;
}

const SUGGESTIONS = [
  "What skills should I learn next to become a Senior Data Scientist?",
  "Which companies are hiring the most Python developers right now?",
  "What's the average salary for remote roles?",
  "How do I transition from software engineering into ML?",
];

function guestId(): string {
  if (typeof window === "undefined") return "guest";
  const key = "career-os-guest-id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = `guest-${crypto.randomUUID()}`;
    localStorage.setItem(key, id);
  }
  return id;
}

export default function AdvisorPage() {
  const { userId } = useAuthStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    const uid = userId ?? guestId();
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "", pending: true }]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let accumulated = "";

    try {
      await advisorApi.stream(
        question,
        uid,
        (token) => {
          accumulated += token;
          setMessages((m) => {
            const next = [...m];
            next[next.length - 1] = { role: "assistant", content: accumulated, pending: true };
            return next;
          });
        },
        controller.signal
      );
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = { ...next[next.length - 1], pending: false };
        return next;
      });
    } catch {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = {
          role: "assistant",
          content: accumulated || "Sorry, I couldn't reach the advisor. Is the backend running?",
          pending: false,
        };
        return next;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer className="flex max-w-3xl flex-1 flex-col">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <MessageSquareText className="h-6 w-6 text-primary" /> Career Advisor
        </h1>
        <p className="mt-1 text-muted-foreground">
          Ask anything about skills, salaries, or hiring trends — answers are grounded in the live job database.
        </p>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <ScrollArea className="h-[55vh] flex-1 px-4">
          <div className="flex flex-col gap-4 py-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-4 py-10 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <p className="text-sm text-muted-foreground">Try asking:</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border px-3 py-1.5 text-sm hover:bg-secondary"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("flex gap-2.5", m.role === "user" && "flex-row-reverse")}>
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                    m.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
                  )}
                >
                  {m.role === "user" ? <UserIcon className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                </div>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                    m.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary"
                  )}
                >
                  {m.content || (m.pending && <Loader2 className="h-4 w-4 animate-spin" />)}
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.sources.map((s, j) => <Badge key={j} variant="outline" className="text-xs font-normal">{s}</Badge>)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <CardContent className="border-t pt-3">
          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
            className="flex items-end gap-2"
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask a career question..."
              rows={1}
              className="min-h-10 flex-1 resize-none"
            />
            <Button type="submit" disabled={loading || !input.trim()} size="icon">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </form>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
