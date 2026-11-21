import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  AuthRequestError,
  type AuthUser,
  MIN_PASSWORD_LENGTH,
  PASSWORD_TOO_SHORT,
  setup,
} from "@/api/auth";
import { AuthFrame } from "@/components/AuthFrame";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function setupFailure(error: unknown): string {
  if (error instanceof AuthRequestError) {
    if (error.code === "setup_code_invalid")
      return "That setup code is not right. Copy it again from the server log.";
    if (error.code === "login_rate_limited")
      return "Too many attempts. Wait a few minutes and try again.";
    if (error.code === "setup_already_completed")
      return "This library has already been claimed. Sign in instead.";
  }
  return "The library could not be claimed. Try again.";
}

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
  const [setupCode, setSetupCode] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) {
      setMessage(PASSWORD_TOO_SHORT);
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      const user = await setup(
        username,
        displayName,
        password,
        setupCode.trim(),
      );
      const destination = returnDestination(location.state);
      onAuthenticated(user);
      if (onNavigate) onNavigate(destination);
      else void navigate(destination, { replace: true });
    } catch (error) {
      setMessage(setupFailure(error));
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
            aria-describedby="setup-password-help"
            required
          />
          <p id="setup-password-help" className="text-sm text-muted-foreground">
            At least {MIN_PASSWORD_LENGTH} characters.
          </p>
        </div>
        <div className="mt-5 space-y-2">
          <Label htmlFor="setup-code">Setup code</Label>
          <Input
            id="setup-code"
            name="setup_code"
            type="text"
            autoCapitalize="none"
            autoComplete="one-time-code"
            spellCheck={false}
            className="min-h-11"
            value={setupCode}
            onChange={(event) => setSetupCode(event.target.value)}
            aria-describedby="setup-code-help"
            required
          />
          <p id="setup-code-help" className="text-sm text-muted-foreground">
            Printed in the server log when Akasha starts (docker compose logs
            akasha).
          </p>
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
