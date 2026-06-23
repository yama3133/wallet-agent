"use client";

import { useState } from "react";
import Link from "next/link";

interface RunResult {
  task_id: string;
  status: "COMPLETED" | "FAILED";
  response?: string;
  error?: string;
}

export default function ChatPage() {
  const [prompt, setPrompt] = useState(
    "プレミアムな市況サマリが欲しい、上限0.005ドルで"
  );
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

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
        <header className="mb-6 flex items-baseline justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-1">wallet-agent / chat</h1>
            <p className="text-sm text-zinc-500">
              AgentCore Runtime に依頼を投げる
            </p>
          </div>
          <Link
            href="/"
            className="text-sm text-blue-600 hover:underline"
          >
            ← 承認カード一覧
          </Link>
        </header>

        <div className="rounded-2xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5 mb-6">
          <label className="block text-xs font-semibold text-zinc-500 mb-1">
            ユーザー入力
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            disabled={loading}
            className="w-full bg-transparent text-base focus:outline-none mb-3 resize-none"
            placeholder="例: プレミアムな市況サマリが欲しい、上限0.005ドルで"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={submit}
              disabled={loading || !prompt.trim()}
              className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-700 text-white text-sm font-medium disabled:opacity-50"
            >
              {loading ? "処理中..." : "依頼を送る"}
            </button>
            <span className="text-xs text-zinc-400">
              ※ 別タブ「<Link href="/" className="underline">承認カード一覧</Link>」で承認操作してください
            </span>
          </div>
        </div>

        {loading && (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4 text-sm text-zinc-500">
            エージェントが思考中... 承認カードが発行されたら別タブで承認してください（最大 60 秒）
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
            <div className="text-xs text-zinc-500 mb-2">エージェントの応答</div>
            <div className="whitespace-pre-wrap text-sm">
              {result.response ?? result.error ?? "(空)"}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
