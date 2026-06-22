import { NextRequest, NextResponse } from "next/server";
import { GetCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { ddb, TABLES } from "@/lib/aws";

interface DecideBody {
  decision: "APPROVED" | "REJECTED";
  reason?: string;
}

// GET /api/approvals/:id
export async function GET(_: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const r = await ddb().send(
      new GetCommand({ TableName: TABLES.approvals, Key: { approval_id: id } })
    );
    if (!r.Item) return NextResponse.json({ error: "not found" }, { status: 404 });
    return NextResponse.json({ approval: r.Item });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

// POST /api/approvals/:id  body: {decision, reason?}
export async function POST(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = (await req.json()) as DecideBody;
  if (body.decision !== "APPROVED" && body.decision !== "REJECTED") {
    return NextResponse.json({ error: "invalid decision" }, { status: 400 });
  }
  try {
    const r = await ddb().send(
      new UpdateCommand({
        TableName: TABLES.approvals,
        Key: { approval_id: id },
        UpdateExpression: "SET #s = :d, decision = :d, #r = :r, decided_at = :t",
        ExpressionAttributeNames: { "#s": "status", "#r": "reason" },
        ExpressionAttributeValues: {
          ":d": body.decision,
          ":r": body.reason ?? "",
          ":t": String(Date.now() / 1000),
          ":pending": "PENDING",
        },
        ConditionExpression: "attribute_exists(approval_id) AND #s = :pending",
        ReturnValues: "ALL_NEW",
      })
    );
    return NextResponse.json({ approval: r.Attributes });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    const status = msg.includes("ConditionalCheckFailed") ? 409 : 500;
    return NextResponse.json({ error: msg }, { status });
  }
}
