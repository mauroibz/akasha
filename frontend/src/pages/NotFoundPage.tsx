import { Link, useNavigate } from "react-router-dom";

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-6 text-center">
      <p className="text-6xl font-bold text-fuchsia-500/30">404</p>
      <h1 className="mt-4 text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-zinc-400">
        This page doesn&apos;t exist. Your library is still safe.
      </p>
      <div className="mt-6 flex gap-3">
        <button
          className="min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
          onClick={() => void navigate("/")}
        >
          Go to library
        </button>
        <Link
          className="flex min-h-11 items-center rounded-full border border-zinc-800 px-5 text-zinc-300 focus-ring"
          to="/add"
        >
          Add a book
        </Link>
      </div>
    </main>
  );
}

export function RouteErrorPage({
  error,
  reset,
}: {
  error: { message?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-6 text-center">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-zinc-400">
        {error.message ?? "The page could not be loaded."}
      </p>
      <button
        className="mt-6 min-h-11 rounded-full bg-fuchsia-500 px-5 font-semibold text-zinc-950 focus-ring"
        onClick={reset}
      >
        Try again
      </button>
    </main>
  );
}
