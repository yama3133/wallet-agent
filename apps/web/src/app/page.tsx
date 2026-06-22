"use client";

import { useEffect, useState } from "react";
import { Approval } from "@/lib/types";
import ApprovalCard from "@/components/ApprovalCard";

export default function Home() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const r = await fetch("/api/approvals", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error ?? "fetch failed");
      setApprovals(j.approvals ?? []);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6">
      <div className="max-w-3xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold mb-1">wallet-agent</h1>
          <p className="text-sm text-zinc-500">
            AI に財布を渡す日 — 承認カード操作 UI
          </p>
        </header>

        {error && (
          <div className="mb-4 p-3 rounded-lg border border-red-300 bg-red-50 dark:bg-red-950 dark:border-red-800 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        <h2 className="text-lg font-semibold mb-3">承認待ち</h2>

        {loading ? (
          <div className="text-zinc-500">読み込み中...</div>
        ) : approvals.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 p-8 text-center text-zinc-500">
            現在、承認待ちはありません。
            <br />
            <span className="text-xs">
              CLI で <code className="bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">python agent.py</code> を起動して依頼すると、ここに承認カードが並びます。
            </span>
          </div>
        ) : (
          <div className="space-y-4">
            {approvals.map((a) => (
              <ApprovalCard key={a.approval_id} approval={a} onDecide={refresh} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
