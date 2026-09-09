import { type FormEvent, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { AuthRequestError, type AuthUser, login } from "@/api/auth";
import { AuthFrame } from "@/components/AuthFrame";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface LoginLocationState {
  returnTo?: unknown;
  interrupted?: boolean;
}

function returnDestination(state: unknown): string {
  const candidate = (state as LoginLocationState | null)?.returnTo;
  return typeof candidate === "string" &&
    candidate.startsWith("/") &&
    !candidate.startsWith("//")
    ? candidate
    : "/";
}

export function LoginPage({
  onAuthenticated,
  onNavigate,
}: {
  onAuthenticated: (user: AuthUser) => void;
  onNavigate?: (destination: string) => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const passwordRef = useRef<HTMLInputElement>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState(
    (location.state as LoginLocationState | null)?.interrupted
      ? "Your session ended. Sign in again to continue."
      : "",
  );
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    try {
      const user = await login(username, password);
      const destination = returnDestination(location.state);
      onAuthenticated(user);
      if (onNavigate) {
        onNavigate(destination);
      } else {
        void navigate(destination, { replace: true });
      }
    } catch (error) {
      setPassword("");
      setMessage(
        error instanceof AuthRequestError && error.code === "login_rate_limited"
          ? "Too many attempts. Wait a few minutes and try again."
          : "Username or password is incorrect.",
      );
      requestAnimationFrame(() => passwordRef.current?.focus());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFrame>
      <form action="/api/auth/login" method="post" onSubmit={submit}>
        <div className="space-y-2">
          <Label htmlFor="login-username">Username</Label>
          <Input
            id="login-username"
            name="username"
            autoComplete="username"
            className="min-h-11"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
            required
          />
        </div>
        <div className="mt-5 space-y-2">
          <Label htmlFor="login-password">Password</Label>
          <Input
            ref={passwordRef}
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
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
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthFrame>
  );
}
