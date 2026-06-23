"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { useI18n } from "@/lib/i18n-context";

interface RunResult {
  task_id: string;
  status: "COMPLETED" | "FAILED";
  response?: string;
  error?: string;
}

export default function ChatPage() {
  const { t } = useI18n();
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  // 言語切替時に default prompt を更新（未入力 or デフォルト時のみ）
  useEffect(() => {
    setPrompt((current) => (current === "" ? t.defaultPrompt : current));
  }, [t.defaultPrompt]);

  const submit = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const r = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error ?? "request failed");
      setResult(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6">
      <div className="max-w-3xl mx-auto">
        <header className="mb-6 flex items-baseline justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold mb-1">{t.chatTitle}</h1>
            <p className="text-sm text-zinc-500">{t.chatSubtitle}</p>
          </div>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <Link href="/" className="text-sm text-blue-600 hover:underline whitespace-nowrap">
              {t.navApprovals}
            </Link>
          </div>
        </header>

        <div className="rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5 mb-6">
          <label className="block text-xs font-semibold text-zinc-500 mb-1">
            {t.userInput}
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            disabled={loading}
            className="w-full bg-transparent text-base focus:outline-none mb-3 resize-none"
            placeholder={t.promptPlaceholder}
          />
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={submit}
              disabled={loading || !prompt.trim()}
              className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-700 text-white text-sm font-medium disabled:opacity-50"
            >
              {loading ? t.processing : t.submit}
            </button>
            <span className="text-xs text-zinc-400">
              {t.approveTipPrefix}
              <Link href="/" className="underline">
                {t.approveLink}
              </Link>
              {t.approveTipSuffix}
            </span>
          </div>
        </div>

        {loading && (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4 text-sm text-zinc-500">
            {t.thinking}
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {result && (
          <div className="rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
            <div className="flex items-center justify-between mb-3">
              <span
                className={`text-xs font-semibold uppercase ${
                  result.status === "COMPLETED" ? "text-emerald-600" : "text-red-600"
                }`}
              >
                {result.status}
              </span>
              <span className="text-[10px] font-mono text-zinc-400">{result.task_id}</span>
            </div>
            <div className="text-xs text-zinc-500 mb-2">{t.responseLabel}</div>
            <div className="whitespace-pre-wrap text-sm">
              {result.response ?? result.error ?? t.emptyMark}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
