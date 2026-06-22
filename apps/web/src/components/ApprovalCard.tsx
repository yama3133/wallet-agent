"use client";

import { useState } from "react";
import { Approval } from "@/lib/types";

interface Props {
  approval: Approval;
  onDecide: () => void;
}

export default function ApprovalCard({ approval, onDecide }: Props) {
  const [loading, setLoading] = useState<"" | "APPROVED" | "REJECTED">("");
  const [error, setError] = useState<string>("");

  const decide = async (decision: "APPROVED" | "REJECTED") => {
    setLoading(decision);
    setError("");
    try {
      const r = await fetch(`/api/approvals/${approval.approval_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason: decision === "REJECTED" ? "user rejected" : "" }),
      });
      if (!r.ok) {
        const j = await r.json();
        throw new Error(j.error ?? "decide failed");
      }
      onDecide();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading("");
    }
  };

  const expiresIn = Math.max(0, Number(approval.expires_at) - Date.now() / 1000);

  return (
    <div className="rounded-2xl border border-zinc-300 dark:border-zinc-700 p-5 shadow-sm bg-white dark:bg-zinc-900 max-w-xl">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-wide text-amber-600 font-semibold">
          人間承認が必要
        </span>
        <span className="text-xs text-zinc-500">
          残り {Math.floor(expiresIn)}s
        </span>
      </div>

      <div className="text-2xl font-bold mb-1">${approval.amount_usd} USDC</div>
      <div className="text-sm text-zinc-600 dark:text-zinc-300 mb-3">{approval.resource}</div>

      <div className="text-sm bg-zinc-50 dark:bg-zinc-800 p-3 rounded-lg mb-4">
        <div className="text-xs text-zinc-500 mb-1">エージェントの理由</div>
        <div>{approval.justification}</div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => decide("APPROVED")}
          disabled={!!loading}
          className="flex-1 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium"
        >
          {loading === "APPROVED" ? "承認中..." : "承認"}
        </button>
        <button
          onClick={() => decide("REJECTED")}
          disabled={!!loading}
          className="flex-1 px-4 py-2.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-50 font-medium"
        >
          {loading === "REJECTED" ? "拒否中..." : "拒否"}
        </button>
      </div>

      {error && <div className="mt-3 text-sm text-red-600">{error}</div>}

      <div className="mt-3 text-[10px] font-mono text-zinc-400">
        {approval.approval_id}
      </div>
    </div>
  );
}
