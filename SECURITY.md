# Security

## The threat model, stated plainly

**Akasha has no authentication, and that is deliberate for v1.** It is built to
run on one machine on a trusted home network, for one person. There are no user
accounts, no login, no sessions, and no authorization checks anywhere in the
codebase.

Anyone who can reach the port can read and change every rating, note and shelf.

This means:

- Do not expose Akasha to the internet.
- Do not forward a port to it.
- Do not put it behind a reverse proxy that terminates on a public address.
- A reverse proxy on the LAN (e.g. Nginx Proxy Manager at `books.home.lan`) is
  the supported deployment, and it is documented in
  [the operator runbook](docs/operations/runbook.md).

**"There is no authentication" is not a vulnerability report.** It is the
documented boundary. A report that Akasha exposed on a public IP can be read by
strangers describes the licence's absence of warranty and this file, not a
defect.

## What *is* in scope

Within that boundary, the application is expected to hold the following. A
failure of any of these is a real vulnerability and worth reporting:

- **Path containment.** The SPA static handler and the Calibre adapter both
  resolve and confine paths. Escaping either — reading a file outside the static
  root or outside the Calibre mount — is in scope.
- **Calibre is read-only.** It is mounted `:ro` and opened with `mode=ro` plus
  `PRAGMA query_only`. Any write reaching a Calibre library is in scope.
- **Upload and fetch limits.** A 5 MiB cap on Goodreads CSV uploads; byte,
  pixel, host-allowlist and redirect caps on cover fetching; a 2 MiB payload cap
  and 5 s timeout on provider responses. A way past any of these — memory
  exhaustion, SSRF to an unlisted host, a decompression bomb — is in scope.
- **Log redaction.** Notes, review text, import rows, API keys and tokens are
  redacted before anything is written, and configured secrets are scrubbed out
  of arbitrary strings. A path that leaks any of them into a log is in scope.
- **Backup integrity.** A restore that silently produces a corrupt or partial
  database rather than failing loudly is in scope.
- **Dependency vulnerabilities** with a plausible path to exploitation in this
  application's actual usage.

## What is out of scope

- The absence of authentication, authorization, rate limiting per user, CSRF
  tokens, or audit logging. All follow from the single-user LAN model above.
- Anything requiring the operator to have already ignored the deployment
  guidance, such as exposing the port publicly.
- Findings from an automated scanner with no demonstrated impact here.

## Reporting

Open a **private security advisory** through GitHub's *Security* tab on this
repository. That keeps the report confidential until there is a fix.

Please include what you did, what happened, and what you expected. A minimal
reproduction against a local container is ideal.

This is a personal project maintained by one person in their own time. Expect a
first response within a couple of weeks, and no bounty — there is no budget for
one. Credit in the release notes is offered gladly if you would like it.

## Supported versions

The `main` branch is the only supported version. There is no backporting.
