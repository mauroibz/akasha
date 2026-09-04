# Documentation map

Every document here carries one of three statuses, stated at its top:

- **canonical** — describes how the system works now. If the code disagrees, one of them is a bug.
- **historical** — an accurate record of a decision or an assessment *at a date*. Never edited to
  match later reality; superseded entries point forward instead.
- **proposal** — written to be accepted or rejected. Once accepted, the thing it proposed is built
  and a canonical document takes over.

The one rule that makes this navigable: **historical documents are not wrong, they are dated.** A
path or a claim inside a closed sprint file describes the repository on the day it closed. Do not
follow one as instructions; follow the canonical documents below.

## Start here

| If you want to… | Read |
|---|---|
| Run or operate it | [`../README.md`](../README.md), then [`operations/runbook.md`](operations/runbook.md) |
| Contribute code | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| **Add a new domain** (games, films, board games…) | **[`guides/adding-a-domain.md`](guides/adding-a-domain.md)** |
| Know what the product does and why | [`specs/product-spec.md`](specs/product-spec.md) |
| Know how it is built | [`specs/technical-spec.md`](specs/technical-spec.md) |
| Know why something is the way it is | [`decisions.md`](decisions.md) |
| See what is being built next | [`sprints/ROADMAP.md`](sprints/ROADMAP.md) |

## Canonical

| Document | What it governs |
|---|---|
| [`specs/product-spec.md`](specs/product-spec.md) | Product behaviour and scope. Authoritative over everything below it. |
| [`specs/technical-spec.md`](specs/technical-spec.md) | Implementation contracts. **§6.6 is the domain contract.** |
| [`guides/adding-a-domain.md`](guides/adding-a-domain.md) | How to build a domain against §6.6, with diagrams and a worked example. |
| [`operations/runbook.md`](operations/runbook.md) | Restore, rollback, upgrades, reverse-proxy guidance. |
| [`operations/publishing-images.md`](operations/publishing-images.md) | How the published image is built, verified, and the one-time owner setup. |
| [`brand/BRAND.md`](brand/BRAND.md) | Palette, typography, the mark and how it is constructed. |
| [`agent/HANDOFF.md`](agent/HANDOFF.md) | Current reality for whoever picks the work up next. |
| [`agent/state.json`](agent/state.json) | The machine-readable sprint pointer. Validated by `scripts/validate_project.py`. |
| [`agent/TESTING.md`](agent/TESTING.md) | Verification cadence, environment triage, walkthrough reuse, and the post-gate rerun matrix. |
| [`sprints/ROADMAP.md`](sprints/ROADMAP.md) | What each sprint delivers, and the contracts for the ones not yet built. |

## Historical

Kept because they are the record, not because they are current.

| Document | What it is | Superseded by |
|---|---|---|
| [`decisions.md`](decisions.md) | Every material decision with its reasoning, append-only. Entries are superseded by later entries, never edited. | — |
| [`agent/worklog.md`](agent/worklog.md) | One entry per working session: what was done, verified, and what went wrong. Append-only. | — |
| [`sprints/`](sprints/) | One file per sprint, each with its acceptance criteria and its outcome. **File paths inside closed sprints predate later refactors** — Sprint 028 moved each domain into its own package, so anything referring to `domain/domains.py`, `domain/goodreads.py`, `domain/calibre.py` or `infrastructure/musicbrainz.py` is describing where those lived at the time. | technical spec §2 and §6.6 |
| [`domain_metadata_roadmap_report.md`](domain_metadata_roadmap_report.md) | Which domains are viable at all, by provider: catalogue breadth, Spanish coverage, licensing. | — for viability; its architecture recommendation is superseded by DEC-052, and its anime verdict by DEC-088, which measured the providers rather than reading their documentation |
| [`movie-domain-viability.md`](movie-domain-viability.md) | Live provider and domain-contract measurement for movies at Sprint 045. | Sprint 046's Outcome for the domain and provider as built, and DEC-099 where its measurements were refined; the importer half awaits Sprint 047 |
| [`spotify-import-and-insights-viability.md`](spotify-import-and-insights-viability.md) | Measured 2026-09-02 against the owner's own Spotify exports and live MusicBrainz: whether `spotify → albums` is buildable, and what an insights (aggregate-by-keyed-field) feature would cost. | Sprints 064 and 065, which were planned from it and are closed |
| [`insights-redesign-proposal.md`](insights-redesign-proposal.md) | Written 2026-09-03 at the owner's request after using what Sprint 065 shipped: what is wrong with the insights *screen*, what replaces it, where it should live, and what that costs. **Accepted as DEC-132 and scheduled as Sprints 066 and 067.** | DEC-132 for the decision; Sprints 066 and 067 for what is built from it |
| [`export-proposal.md`](export-proposal.md) | Written 2026-09-04 at the owner's request: why the shipped export has no door and only one domain can leave in a format another application reads, what an `ExportView` contract replaces it with, and what that costs. **Proposal — drafted as Sprints 068, 069 and 070, none scheduled.** | — |
| [`ui-cohesion-proposal.md`](ui-cohesion-proposal.md) | Written 2026-09-04 at the owner's request: the seven rules Sprints 066 and 067 established, eleven places the rest of the application disagrees with them, and what one surface would cost. **Proposal — drafted as Sprints 071 and 072, neither scheduled.** | — |
| [`series-domain-viability.md`](series-domain-viability.md) | Live provider, poster, export and anime-overlap measurement for television series, taken 2026-08-31 while planning Sprints 049–053. | Sprint 049's and 050's Outcomes for the domain and providers as built; DEC-104–107 for the decisions it produced |
| [`operations/release-notes-v1.md`](operations/release-notes-v1.md), [`release-notes-v1.1.md`](operations/release-notes-v1.1.md), [`release-notes-v1.2.md`](operations/release-notes-v1.2.md), [`release-notes-v1.3.md`](operations/release-notes-v1.3.md), [`release-notes-v1.4.md`](operations/release-notes-v1.4.md), [`release-notes-v1.5.md`](operations/release-notes-v1.5.md), [`release-notes-v1.5.1.md`](operations/release-notes-v1.5.1.md), [`release-notes-v1.5.3.md`](operations/release-notes-v1.5.3.md), [`release-notes-v1.5.4.md`](operations/release-notes-v1.5.4.md), [`release-notes-v1.5.5.md`](operations/release-notes-v1.5.5.md), [`release-notes-v1.5.6.md`](operations/release-notes-v1.5.6.md), [`release-notes-v1.5.7.md`](operations/release-notes-v1.5.7.md), [`release-notes-v1.6.md`](operations/release-notes-v1.6.md), [`release-notes-v1.7.md`](operations/release-notes-v1.7.md) | What shipped, per release. | — |
| [`brand/brand-handoff.md`](brand/brand-handoff.md) | The brand work as delivered. | `brand/BRAND.md` |

Superseded one-off proposals and assessments (domain architecture, unified search, the post-Sprint-013
audit, the domain-expansion assessment, the entry-depth verdict) have been removed now that their
decisions are built and recorded in `decisions.md` (DEC-024–026, DEC-052, DEC-065, DEC-077) — see
`git log` for the originals if the underlying measurements are ever needed again.

## For agents

[`../AGENTS.md`](../AGENTS.md) is the entrypoint and the protocol;
[`agent/WORKFLOW.md`](agent/WORKFLOW.md) expands it; and
[`agent/TESTING.md`](agent/TESTING.md) defines the verification cadence. All three are canonical and
binding on any session that changes this repository.
