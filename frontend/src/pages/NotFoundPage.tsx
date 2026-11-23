import { Link, useNavigate } from "react-router-dom";
import { PageFrame } from "@/components/PageFrame";

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <PageFrame
      width="focus"
      className="flex min-h-[70vh] flex-col items-center justify-center text-center"
    >
      <p className="text-6xl font-bold text-primary/30">404</p>
      <h1 className="mt-4 font-display text-3xl font-medium">Page not found</h1>
      <p className="mt-2 text-muted-foreground">
        This page doesn&apos;t exist. Your library is still safe.
      </p>
      <div className="mt-6 flex gap-3">
        <button
          className="min-h-11 rounded-full bg-primary px-5 font-semibold text-primary-foreground focus-ring"
          onClick={() => void navigate("/library")}
        >
          Go to library
        </button>
        <Link
          className="flex min-h-11 items-center rounded-full border border-border px-5 text-foreground focus-ring"
          to="/add"
        >
          Enter by hand
        </Link>
      </div>
    </PageFrame>
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
    <PageFrame
      width="focus"
      className="flex min-h-[70vh] flex-col items-center justify-center text-center"
    >
      <h1 className="font-display text-3xl font-medium">
        Something went wrong
      </h1>
      <p className="mt-2 text-muted-foreground">
        {error.message ?? "The page could not be loaded."}
      </p>
      <button
        className="mt-6 min-h-11 rounded-full bg-primary px-5 font-semibold text-primary-foreground focus-ring"
        onClick={reset}
      >
        Try again
      </button>
    </PageFrame>
  );
}
