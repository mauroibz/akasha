export type ReadyHealth = { status: "ready" };

export async function getReadiness(): Promise<ReadyHealth> {
  const response = await fetch("/api/health/ready", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error("Akasha is unavailable");
  return (await response.json()) as ReadyHealth;
}
