import { NextRequest, NextResponse } from "next/server";
import { PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { ddb, TABLES } from "@/lib/aws";
import { invokeAgent } from "@/lib/agentcore";

// Vercel Hobby は 60秒、Pro は 300秒。エージェント1往復は 30〜60秒程度。
export const maxDuration = 60;
export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = (await req.json()) as { prompt?: string; user_id?: string };
  const prompt = body.prompt?.trim();
  if (!prompt) {
    return NextResponse.json({ error: "prompt is required" }, { status: 400 });
  }
  const userId = body.user_id ?? "anonymous";
  const taskId = `task-${crypto.randomUUID()}`;
  const createdAt = String(Date.now() / 1000);

  // task を PLANNING で作成
  await ddb().send(
    new PutCommand({
      TableName: TABLES.tasks,
      Item: {
        task_id: taskId,
        user_id: userId,
        status: "PLANNING",
        prompt,
        created_at: createdAt,
      },
    })
  );

  // AgentCore Runtime に同期 invoke（Vercel function timeout 内で）
  const result = await invokeAgent(prompt);

  await ddb().send(
    new UpdateCommand({
      TableName: TABLES.tasks,
      Key: { task_id: taskId },
      UpdateExpression:
        "SET #s = :s, final_response = :r, finished_at = :t, #e = :e",
      ExpressionAttributeNames: { "#s": "status", "#e": "error" },
      ExpressionAttributeValues: {
        ":s": result.status === "OK" ? "COMPLETED" : "FAILED",
        ":r": result.response ?? "",
        ":t": String(Date.now() / 1000),
        ":e": result.error ?? "",
      },
    })
  );

  return NextResponse.json({
    task_id: taskId,
    status: result.status === "OK" ? "COMPLETED" : "FAILED",
    response: result.response,
    error: result.error,
  });
}
