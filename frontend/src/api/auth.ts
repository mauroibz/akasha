export interface AuthUser {
  id: number;
  username: string;
  display_name: string | null;
  is_admin: boolean;
}

export interface AuthState {
  auth: "off" | "on";
  authenticated: boolean;
  setup_required: boolean;
  user: AuthUser | null;
}

export const AUTH_STATE_QUERY_KEY = ["auth", "me"] as const;

export class AuthRequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "AuthRequestError";
  }
}

async function authJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new AuthRequestError(
      body?.error?.code ?? "auth_failed",
      body?.error?.message ?? "Authentication failed",
    );
  }
  return response.json() as Promise<T>;
}

export function login(username: string, password: string): Promise<AuthUser> {
  return fetch("/api/auth/login", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).then(authJson<AuthUser>);
}

/**
 * Probe the deployment once before mounting a private route.
 *
 * Auth routes deliberately return 404 in the default off mode, so that response
 * is the mode signal rather than an authentication failure.
 */
export async function getAuthState(): Promise<AuthState> {
  const response = await fetch("/api/auth/me", {
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) {
    return {
      auth: "off",
      authenticated: false,
      setup_required: false,
      user: null,
    };
  }
  return authJson<AuthState>(response);
}
