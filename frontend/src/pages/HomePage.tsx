import { useQuery } from "@tanstack/react-query";

import { getReadiness } from "@/api/health";

export function HomePage() {
  const readiness = useQuery({
    queryKey: ["health", "ready"],
    queryFn: getReadiness,
    retry: false,
  });
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6">
      <p className="text-sm font-semibold uppercase tracking-[0.25em] text-fuchsia-400">
        Personal library
      </p>
      <h1 className="mt-3 text-5xl font-semibold tracking-tight">Akasha</h1>
      <div className="mt-8" aria-live="polite" role="status">
        {readiness.isPending && <p>Checking your library…</p>}
        {readiness.isSuccess && <p>Akasha is ready.</p>}
        {readiness.isError && <p>Akasha is unavailable. Try again shortly.</p>}
      </div>
    </main>
  );
}
