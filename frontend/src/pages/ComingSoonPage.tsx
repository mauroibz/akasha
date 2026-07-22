import { Link } from "react-router-dom";

export function ComingSoonPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6">
      <p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-400">
        Akasha
      </p>
      <h1 className="mt-3 text-3xl font-semibold">Adding books arrives next</h1>
      <p className="mt-3 text-zinc-400">
        The library is ready; search and add is part of Sprint 006.
      </p>
      <Link
        className="mt-6 min-h-11 self-start rounded-full bg-fuchsia-500 px-5 py-3 font-semibold text-zinc-950 focus-ring"
        to="/"
      >
        Back to library
      </Link>
    </main>
  );
}
