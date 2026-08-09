export type ReadyHealth = { status: "ready" };

export interface ProviderStatus {
  name: string;
  available: boolean;
  reason: string | null;
}

export interface ProviderHealth {
  providers: ProviderStatus[];
  degraded: boolean;
}

/** Which metadata providers are configured. Search still works while degraded. */
export async function getProviderHealth(): Promise<ProviderHealth> {
  const response = await fetch("/api/health/providers", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Provider status is unavailable");
  return (await response.json()) as ProviderHealth;
}

export async function getReadiness(): Promise<ReadyHealth> {
  const response = await fetch("/api/health/ready", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Akasha is unavailable");
  return (await response.json()) as ReadyHealth;
}
