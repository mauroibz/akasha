import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { type AuthUser, setup } from "@/api/auth";
import { AuthFrame } from "@/components/AuthFrame";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function returnDestination(state: unknown): string {
  const candidate = (state as { returnTo?: unknown } | null)?.returnTo;
  return typeof candidate === "string" &&
    candidate.startsWith("/") &&
    !candidate.startsWith("//")
    ? candidate
    : "/";
}

export function SetupPage({
  onAuthenticated,
  onNavigate,
}: {
  onAuthenticated: (user: AuthUser) => void;
  onNavigate?: (destination: string) => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    try {
      const user = await setup(username, displayName, password);
      const destination = returnDestination(location.state);
      onAuthenticated(user);
      if (onNavigate) onNavigate(destination);
      else void navigate(destination, { replace: true });
    } catch {
      setMessage("The library could not be claimed. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFrame>
      <p className="mb-5 text-sm leading-6 text-muted-foreground">
        This claims the library already on this install and makes you its admin.
      </p>
      <form action="/api/auth/setup" method="post" onSubmit={submit}>
        <div className="space-y-2">
          <Label htmlFor="setup-username">Username</Label>
          <Input
            id="setup-username"
            name="username"
            type="text"
            inputMode="text"
            autoCapitalize="none"
            spellCheck={false}
            autoComplete="username"
            className="min-h-11"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
            required
          />
        </div>
        <div className="mt-5 space-y-2">
          <Label htmlFor="setup-display-name">Display name</Label>
          <Input
            id="setup-display-name"
            name="display_name"
            autoComplete="name"
            className="min-h-11"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            required
          />
        </div>
        <div className="mt-5 space-y-2">
          <Label htmlFor="setup-password">Password</Label>
          <Input
            id="setup-password"
            name="password"
            type="password"
            autoComplete="new-password"
            className="min-h-11"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        <p
          className="mt-4 min-h-5 text-sm text-destructive"
          role="status"
          aria-live="polite"
        >
          {message}
        </p>
        <Button className="mt-4 w-full" type="submit" disabled={submitting}>
          {submitting ? "Claiming library…" : "Claim library"}
        </Button>
      </form>
    </AuthFrame>
  );
}
