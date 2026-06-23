import Link from "next/link";

export default function CheckoutCancelPage() {
  return (
    <main className="min-h-screen p-6 bg-zinc-50 dark:bg-zinc-950">
      <div className="max-w-2xl mx-auto">
        <div className="inline-block px-3 py-1 rounded-full text-xs font-semibold mb-4 bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200">
          キャンセル / Canceled
        </div>
        <h1 className="text-3xl font-bold mb-2">決済がキャンセルされました</h1>
        <p className="text-zinc-500 mb-6">
          ご注文は確定していません。再度ご依頼いただけます。
        </p>
        <Link href="/chat" className="underline text-blue-600">
          chat に戻る
        </Link>
      </div>
    </main>
  );
}
