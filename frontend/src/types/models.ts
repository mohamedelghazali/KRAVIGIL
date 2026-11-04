export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type ValidationStatus = "potential" | "confirmed" | "inconclusive" | "rejected" | "needs_review";

export interface Asset {
  id: string;
  name: string;
  primary_address?: string;
  asset_type?: string;
}

export interface Finding {
  id: string;
  title: string;
  severity: Severity;
  validation_status: ValidationStatus;
  asset_id?: string;
  first_seen?: string;
  last_seen?: string;
}

export interface Scan {
  id: string;
  target_id: string;
  status: "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";
  created_at?: string;
}
