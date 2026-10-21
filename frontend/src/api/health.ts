export type ReadyHealth = { status: "ready" };

export interface ProviderStatus {
  name: string;
  available: boolean;
  reason: string | null;
  /** From the provider's recent calls (Sprint 101); `available` only says configured. */
  state?: "working" | "degraded" | "down";
}

export interface ProviderHealth {
  providers: ProviderStatus[];
  degraded: boolean;
}

/** Which metadata providers are configured and answering. Search still works while degraded. */
export async function getProviderHealth(): Promise<ProviderHealth> {
  const response = await request("/api/health/providers", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw await apiFailure(response, "Provider status is unavailable");
  return (await response.json()) as ProviderHealth;
}

export async function getReadiness(): Promise<ReadyHealth> {
  const response = await request("/api/health/ready", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await apiFailure(response, "Akasha is unavailable");
  return (await response.json()) as ReadyHealth;
}
import { apiFailure, request } from "./request";
