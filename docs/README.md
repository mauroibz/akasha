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
| [`brand/BRAND.md`](brand/BRAND.md) | Palette, typography, the mark and how it is constructed. |
| [`agent/HANDOFF.md`](agent/HANDOFF.md) | Current reality for whoever picks the work up next. |
| [`agent/state.json`](agent/state.json) | The machine-readable sprint pointer. Validated by `scripts/validate_project.py`. |
| [`agent/TESTING.md`](agent/TESTING.md) | Verification cadence, environment triage, walkthrough reuse, and the post-gate rerun matrix. |
| [`sprints/ROADMAP.md`](sprints/ROADMAP.md) | What each sprint delivers, and the contracts for the ones not yet built. |
| [`entry-depth-verdict.md`](entry-depth-verdict.md) | Sprint 030's verdict: a child of an entry needs no state of its own; depth is per-domain progress or provider `rows`; sets are ordered shelves. |

## Historical

Kept because they are the record, not because they are current.

| Document | What it is | Superseded by |
|---|---|---|
| [`decisions.md`](decisions.md) | Every material decision with its reasoning, append-only. Entries are superseded by later entries, never edited. | — |
| [`agent/worklog.md`](agent/worklog.md) | One entry per working session: what was done, verified, and what went wrong. Append-only. | — |
| [`sprints/`](sprints/) | One file per sprint, each with its acceptance criteria and its outcome. **File paths inside closed sprints predate later refactors** — Sprint 028 moved each domain into its own package, so anything referring to `domain/domains.py`, `domain/goodreads.py`, `domain/calibre.py` or `infrastructure/musicbrainz.py` is describing where those lived at the time. | technical spec §2 and §6.6 |
| [`assessment.md`](assessment.md) | The 2026-08-08 audit after thirteen sprints closed green on a product that did not work. Diagnosis and remedies. | DEC-024, DEC-025, DEC-026 |
| [`domain-expansion-assessment.md`](domain-expansion-assessment.md) | 2026-08-15, after Sprint 028: did the domain work reach its goal? What is proved, what is missing, and the one open question that could force a redesign. Costed options. | — |
| [`domain_metadata_roadmap_report.md`](domain_metadata_roadmap_report.md) | Which domains are viable at all, by provider: catalogue breadth, Spanish coverage, licensing. | — for viability; its architecture recommendation is superseded by DEC-052 |
| [`operations/release-notes-v1.md`](operations/release-notes-v1.md), [`release-notes-v1.1.md`](operations/release-notes-v1.1.md) | What shipped, per release. | — |
| [`brand/brand-handoff.md`](brand/brand-handoff.md) | The brand work as delivered. | `brand/BRAND.md` |

## Proposals

Accepted, and now built or scheduled. Kept for the measurements that produced them, which the
canonical documents summarise but do not reproduce.

| Document | Status |
|---|---|
| [`domain-architecture-proposal.md`](domain-architecture-proposal.md) | **Accepted** (DEC-052) and **delivered** by Sprints 025–028. The live measurements against MusicBrainz are here; how domains work *now* is technical spec §6.6 and [`guides/adding-a-domain.md`](guides/adding-a-domain.md). |
| [`unified-search-proposal.md`](unified-search-proposal.md) | **Accepted** (DEC-065), amended twice, and **delivered** by Sprint 029. The measurement of the two searches is here; what was actually built — the firing rule, results below the library, `/add` as manual entry — is DEC-073, product spec §7 and technical spec §8. |

## For agents

[`../AGENTS.md`](../AGENTS.md) is the entrypoint and the protocol;
[`agent/WORKFLOW.md`](agent/WORKFLOW.md) expands it; and
[`agent/TESTING.md`](agent/TESTING.md) defines the verification cadence. All three are canonical and
binding on any session that changes this repository.
