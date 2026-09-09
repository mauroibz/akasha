/** The one signal from API refusal to the router (Sprint 078). */
export const AUTH_REQUIRED_EVENT = "akasha:auth-required";

export class Unauthenticated extends Error {
  constructor() {
    super("Authentication is required");
    this.name = "Unauthenticated";
  }
}

export class SetupRequired extends Error {
  constructor() {
    super("Initial setup is required");
    this.name = "SetupRequired";
  }
}

type AuthRequiredDetail = { kind: "login" | "setup" };

function announce(kind: AuthRequiredDetail["kind"]) {
  window.dispatchEvent(
    new CustomEvent<AuthRequiredDetail>(AUTH_REQUIRED_EVENT, {
      detail: { kind },
    }),
  );
}

/**
 * A deliberately thin fetch wrapper: it recognizes only the two application-wide
 * authentication refusals and otherwise leaves the Response untouched.
 */
export async function request(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401) {
    announce("login");
    throw new Unauthenticated();
  }
  if (response.status === 409) {
    const body = (await response
      .clone()
      .json()
      .catch(() => null)) as { error?: { code?: string } } | null;
    if (body?.error?.code === "setup_required") {
      announce("setup");
      throw new SetupRequired();
    }
  }
  return response;
}
