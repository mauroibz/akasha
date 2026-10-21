import { jsonOrApiError, request } from "./request";

/** One change to one of your jobs, as `GET /api/events` sends it (Sprint 089). */
export interface JobEvent {
  id: string;
  batch_id: string | null;
  kind: string;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: { searched?: number; total?: number; [key: string]: unknown };
  error: string | null;
  error_code: string | null;
  attempts: number;
  updated_at: string;
}

export const EVENTS_URL = "/api/events";

export async function retryJob(jobId: string): Promise<void> {
  const response = await request(`/api/import/jobs/${jobId}/retry`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  await jsonOrApiError(response, "The job could not be retried");
}
