import { NextResponse } from "next/server";
import { ScanCommand } from "@aws-sdk/lib-dynamodb";
import { ddb, TABLES } from "@/lib/aws";
import { Approval } from "@/lib/types";

// GET /api/approvals → status=PENDING の一覧
export async function GET() {
  try {
    const r = await ddb().send(
      new ScanCommand({
        TableName: TABLES.approvals,
        FilterExpression: "#s = :p",
        ExpressionAttributeNames: { "#s": "status" },
        ExpressionAttributeValues: { ":p": "PENDING" },
      })
    );
    const items = (r.Items ?? []) as Approval[];
    items.sort((a, b) => Number(b.created_at) - Number(a.created_at));
    return NextResponse.json({ approvals: items });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
