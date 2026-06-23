---
title: "The day I gave an AI a wallet — building an approval-gated shopping agent with Sonnet 4.6, AgentCore Payments, Rakuten and Stripe"
published: false
description: "A PoC that runs Bedrock AgentCore Payments (x402 micropayments) and Rakuten + Stripe checkout from a single Strands Agent — gated by a human-in-the-loop approval card. Includes Vercel production deploy + 8-language UI."
tags: bedrock, agentcore, nextjs, ai
cover_image: https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/blog/wallet-agent-thumb-en.png
canonical_url: https://github.com/yama3133/wallet-agent
---

> **TL;DR**
> I built a PoC that wires up **Bedrock AgentCore Payments (x402 + USDC)** *and* **Rakuten + Stripe Checkout** behind a single Strands Agent — and made sure **the agent can't spend a single cent without a human approval card**. Production-deployed on Vercel, with an 8-language UI.
>
> - Production: https://wallet-agent.vercel.app/
> - Repo: https://github.com/yama3133/wallet-agent

![wallet-agent thumbnail](https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/blog/wallet-agent-thumb-en.png)

## Why I built this

I have **five different talks / CFPs** lined up — re:Invent 2026 COM Track, Qiita Tech Festa, iOSDC LT, re:Deploy Security, and a Slack Hackathon — all centred on the same idea: **"the day you give an AI a wallet, and what an approval gate looks like."**

Slides alone weren't going to carry the message. I needed a **shared implementation base** that I could spin up live in front of an audience.

The shape of the goal was simple:

> User asks something in natural language → the agent picks an option → **an approval card pops up** → human approves / rejects → on approval, the actual payment runs → result is summarised back to the user.

I wanted to prove this in **two axes**: pay-per-call paid APIs (microtransactions) and real-world product purchases.

## Architecture

![architecture](https://raw.githubusercontent.com/yama3133/wallet-agent/main/docs/images/wallet-agent-architecture-en.png)

- **Frontend**: Next.js 16 on Vercel (approval list + chat + checkout result)
- **State**: DynamoDB — `wallet_agent_tasks` / `approvals` / `txns`, Streams + PITR
- **Agent**: AgentCore Runtime (ARM64 container) + Strands Agent + Claude Sonnet 4.6
- **Payments — Phase 1**: AgentCore Payments → Privy (StripePrivy) → x402 → base-sepolia USDC
- **Payments — Phase 2**: Rakuten Ichiba `IchibaItem/Search` → Stripe Checkout (test mode)
- **Localisation**: ja / en / zh / ko / fr / it / es / **ar (RTL)** — 8 languages, `localStorage` + `navigator.language` auto-detect, **LINE Seed JP Bold** as the base font

All of it — code, CloudFormation, demo script — lives in [yama3133/wallet-agent](https://github.com/yama3133/wallet-agent).

## The agent itself

The agent is just six `@tool` functions wired into a Strands Agent.

```python
@tool
def search_paid_resources(query: str = "") -> list[dict]: ...  # x402 catalog

@tool
def request_payment_approval(resource_id: str, amount_usd: str, justification: str) -> dict:
    """Write a pending approval to DynamoDB / local JSON and block until a decision lands."""

@tool
def execute_x402_payment(resource_id: str, payment_session_id: str | None = None) -> dict:
    """Drive AgentCore Payments' generate_payment_header through to a successful x402 settle."""

@tool
def search_rakuten_items(keyword: str, max_jpy: int | None = None, hits: int = 5) -> list[dict]: ...

@tool
def request_purchase_approval(item_id: str, title: str, amount_jpy: int, justification: str) -> dict: ...

@tool
def execute_stripe_checkout(item_id: str, title: str, amount_jpy: int, image_url: str = "") -> dict:
    """Create a Stripe Checkout Session and return the URL."""
```

The trick is that `request_*_approval` **writes a row to DynamoDB and waits**. The tool chain literally can't progress until a human flips the row to `APPROVED`. That single primitive keeps the LLM from going off the rails.

## Phase 1 — the AgentCore Payments signer trap

This is where I lost the most time.

```
ProcessPayment → AccessDeniedException
"Privy credentials are invalid. Please verify the credential configuration."
```

I could create `PaymentManager`, `PaymentConnector`, and `PaymentInstrument` (an Embedded Crypto Wallet) from boto3 just fine. `ProcessPayment` was the one call that wouldn't go through.

Looking at the Privy dashboard, the wallet that AWS's `CreatePaymentInstrument` had created was **owned by an internally-generated Privy User**, and my Authorization Key was **not registered as a signer on any wallet at all**.

The fix is to run Privy's official template, [privy-io/aws-agentcore-sdk](https://github.com/privy-io/aws-agentcore-sdk), locally and click through the **"Connect agent"** UI in a browser. That UI hits Privy's internal API and adds your Authorization Key to `additional_signers` on the wallet.

```bash
git clone https://github.com/privy-io/aws-agentcore-sdk ~/wallet-agent-privy-template
cd ~/wallet-agent-privy-template
# Drop NEXT_PUBLIC_PRIVY_APP_ID / PRIVY_APP_SECRET / NEXT_PUBLIC_PRIVY_SIGNER_ID into .env.local
pnpm dev
# → browse to localhost:3001 → log in → Connect agent
```

After that, `process_payment` returns **`PROOF_GENERATED`** and the merchant (`https://drvd12nxpcyd5.cloudfront.net/market-recap`, a public x402 demo endpoint) accepts the payload.

```
[bedrock_agentcore.payments.manager] Successfully processed payment for user test-user-yama3133
[bedrock_agentcore.payments.manager] Successfully generated payment header for user test-user-yama3133
```

The lesson: **you cannot finish AgentCore Payments setup purely server-side**. Design your demo flow with the Privy frontend baked in from day one.

## Phase 2 — Rakuten and the Referer pitfall

Phase 2 was a much more pedestrian WebAPI face-plant.

I registered a new Rakuten webservice application, took the `Application ID` (UUID form), and hit `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401`. Got:

```json
{"errors":{"errorCode":403,"errorMessage":"REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING"}}
```

Adding `Referer: https://wallet-agent.vercel.app/` didn't help. The actual culprit was **User-Agent bot detection** — `User-Agent: wallet-agent/0.1` is rejected. Swapping to a browser-ish `Mozilla/5.0 ...` makes the request go through.

The final `tools/rakuten.py` looks like this:

```python
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": referer,             # WALLET_AGENT_PUBLIC_URL
    "Origin": referer.rstrip("/"),
}
if access_key:
    headers["accessKey"] = access_key
    params["accessKey"] = access_key
```

From there: a pair of black socks at ¥1,980, a Stripe Checkout Session, test card `4242 4242 4242 4242`, and a redirect to `https://wallet-agent.vercel.app/checkout/success?session_id=cs_test_...` showing **"Paid / 1,980 JPY."**

## DynamoDB and the Vercel frontend

The approval state lives in **`wallet_agent_approvals`** on DynamoDB. Local dev falls back to `agent/.approvals.json` — flipped by `WALLET_AGENT_STORAGE=local|dynamo`.

The Next.js 16 App Router side is a small handful of route handlers:

```typescript
// /api/approvals (GET) — list PENDING
const r = await ddb().send(new ScanCommand({
  TableName: TABLES.approvals,
  FilterExpression: "#s = :p",
  ExpressionAttributeNames: { "#s": "status" },
  ExpressionAttributeValues: { ":p": "PENDING" },
}));

// /api/approvals/[id] (POST) — decide
await ddb().send(new UpdateCommand({
  TableName: TABLES.approvals,
  Key: { approval_id: id },
  UpdateExpression: "SET #s = :d, decision = :d, #r = :r, decided_at = :t",
  ExpressionAttributeNames: { "#s": "status", "#r": "reason" },
  ExpressionAttributeValues: { ":d": body.decision, ":r": body.reason ?? "", ":t": String(Date.now()/1000), ":pending": "PENDING" },
  ConditionExpression: "attribute_exists(approval_id) AND #s = :pending",
}));
```

I bit the **`error` is a DynamoDB reserved word** trap once — you need `ExpressionAttributeNames: { "#e": "error" }` to update it, otherwise you get `ValidationException: Invalid UpdateExpression`.

## 8-language UI and LINE Seed JP

`apps/web/src/lib/i18n.ts` is just a flat dictionary of 8 languages × 31 keys, wired into a tiny `useI18n()` Context. The Arabic locale flips `document.documentElement.dir` to `"rtl"`:

```tsx
useEffect(() => {
  document.documentElement.lang = locale;
  document.documentElement.dir = getDir(locale); // "ltr" | "rtl"
}, [locale]);
```

The font is **LINE Seed JP Bold** via `next/font/google`, exposed as a CSS variable `--font-line-seed` and dropped into Tailwind's `font-sans`. It gives Japanese text a friendly rounded-bold feel that reads well alongside the LINE-app universe.

## Things I learned

1. **The Privy signer wall is not solvable server-side.** Build the "Connect agent" frontend step into the demo on day one.
2. **`agentcore configure` is interactive by default.** With `-ni`, a hand-rolled ECR repo, and a Dockerfile in the bundle, you can drive it from CI just fine.
3. **Vercel's 60-second Hobby timeout** does not play nicely with synchronously invoking a long-running agent. Plan for `waitUntil` or a polling pattern.
4. **One "human approval card" tool is enough** to make the LLM safe-by-construction. The same primitive solves Phase 1 and Phase 2 without modification.

## Links

- 🐙 GitHub: [yama3133/wallet-agent](https://github.com/yama3133/wallet-agent)
- 🚀 Production: https://wallet-agent.vercel.app/
- 📐 Architecture diagram (PNG): [docs/images/wallet-agent-architecture-en.png](https://github.com/yama3133/wallet-agent/blob/main/docs/images/wallet-agent-architecture-en.png)
- 🎬 Demo script: [docs/demo-script.md](https://github.com/yama3133/wallet-agent/blob/main/docs/demo-script.md)

This PoC is meant to power **five different talks** with one shared implementation. I'll be improving it as those events get closer. Feedback welcome.

— [@yama3133](https://github.com/yama3133) (AWS Community Builder, AI Engineering / 2026)
