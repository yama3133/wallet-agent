import Link from "next/link";
import { retrieveSession } from "@/lib/stripe";

export const dynamic = "force-dynamic";

interface Params {
  searchParams: Promise<{ session_id?: string }>;
}

export default async function CheckoutSuccessPage({ searchParams }: Params) {
  const { session_id } = await searchParams;
  if (!session_id) {
    return (
      <main className="min-h-screen p-6 bg-zinc-50 dark:bg-zinc-950">
        <div className="max-w-2xl mx-auto">
          <p className="text-red-600">session_id がありません</p>
          <Link href="/" className="underline text-blue-600">
            ホームに戻る
          </Link>
        </div>
      </main>
    );
  }

  let body: React.ReactNode;
  try {
    const s = await retrieveSession(session_id);
    const paid = s.payment_status === "paid" || s.status === "complete";
    const total =
      s.amount_total != null && s.currency
        ? `${s.amount_total.toLocaleString()} ${s.currency.toUpperCase()}`
        : "—";
    const item = s.line_items?.data?.[0]?.description ?? "—";
    body = (
      <>
        <div
          className={`inline-block px-3 py-1 rounded-full text-xs font-semibold mb-4 ${
            paid
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200"
              : "bg-amber-100 text-amber-700"
          }`}
        >
          {paid ? "決済完了 / Paid" : `状態: ${s.status ?? "unknown"}`}
        </div>
        <h1 className="text-3xl font-bold mb-2">ご注文ありがとうございました</h1>
        <p className="text-zinc-500 mb-6">
          Stripe テストモードでの決済シミュレーションです。
        </p>

        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 mb-6">
          <div className="text-xs text-zinc-500 mb-1">商品</div>
          <div className="mb-3">{item}</div>
          <div className="text-xs text-zinc-500 mb-1">金額</div>
          <div className="text-2xl font-bold mb-3">{total}</div>
          <div className="text-xs text-zinc-500 mb-1">Session ID</div>
          <div className="text-[11px] font-mono break-all text-zinc-400">
            {s.id}
          </div>
        </div>

        <Link href="/" className="underline text-blue-600">
          ← 承認カード一覧に戻る
        </Link>
      </>
    );
  } catch (e) {
    body = (
      <>
        <p className="text-red-600 mb-3">
          Stripe Session の取得に失敗しました
        </p>
        <pre className="text-xs bg-zinc-100 dark:bg-zinc-800 p-3 rounded mb-3 overflow-auto">
          {e instanceof Error ? e.message : String(e)}
        </pre>
        <Link href="/" className="underline text-blue-600">
          ホームに戻る
        </Link>
      </>
    );
  }

  return (
    <main className="min-h-screen p-6 bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-2xl mx-auto">{body}</div>
    </main>
  );
}
