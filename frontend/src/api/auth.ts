export interface AuthUser {
  id: number;
  username: string;
  display_name: string | null;
  is_admin: boolean;
}

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
