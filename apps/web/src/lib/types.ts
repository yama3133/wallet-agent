export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";

export interface Approval {
  approval_id: string;
  task_id: string;
  status: ApprovalStatus;
  resource: string;
  amount_usd: string;
  justification: string;
  created_at: string;
  expires_at: string;
  decision: ApprovalStatus | null;
  reason?: string;
  decided_at?: string;
}

export interface Task {
  task_id: string;
  user_id: string;
  status:
    | "PLANNING"
    | "WAITING_APPROVAL"
    | "EXECUTING"
    | "COMPLETED"
    | "FAILED";
  prompt: string;
  final_response?: string;
  created_at: string;
  finished_at?: string;
}

export interface Txn {
  txn_id: string;
  task_id: string;
  approval_id: string;
  amount_usd: string;
  network: string;
  asset: string;
  payment_session_id?: string;
  status: "PENDING" | "PAID" | "FAILED";
  proof_hash?: string;
  created_at: string;
}
