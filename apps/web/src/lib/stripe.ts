const API = "https://api.stripe.com/v1";

function key(): string {
  const k = process.env.STRIPE_SECRET_KEY;
  if (!k) throw new Error("STRIPE_SECRET_KEY 未設定");
  return k;
}

export interface CheckoutSession {
  id: string;
  payment_status: "paid" | "unpaid" | "no_payment_required";
  amount_total: number | null;
  currency: string | null;
  customer_email: string | null;
  status: "open" | "complete" | "expired" | null;
  line_items?: {
    data: { description: string; quantity: number; amount_total: number; currency: string }[];
  };
}

export async function retrieveSession(sessionId: string): Promise<CheckoutSession> {
  const u = `${API}/checkout/sessions/${encodeURIComponent(sessionId)}?expand[]=line_items`;
  const r = await fetch(u, {
    headers: {
      Authorization: `Bearer ${key()}`,
      "User-Agent": "wallet-agent-web/0.1",
    },
    cache: "no-store",
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Stripe ${r.status}: ${t.slice(0, 500)}`);
  }
  return (await r.json()) as CheckoutSession;
}
