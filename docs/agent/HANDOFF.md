# Handoff — Sprint 084 (ready): any list, any domain

`docs/agent/state.json` reads `project_status: ready` with **Sprint 084 active**
(`docs/sprints/084-any-list-any-domain.md`, `Status: ready`, plan revision 42,
DEC-160). v2.1.0 is released (PR #20 merged, tag `v2.1.0`, image on ghcr,
GitHub Release published); this sprint reopens the plan a second time, at the
owner's direction, to make the custom-list importer domain-selectable.

## What Sprint 084 delivers (read the sprint file for the contract)

The owner's structural question — the flow is "read file, iterate rows, search
each", so why is the domain fixed? — measured as *nothing structural blocks
it*: `item_types` already drives every seam (multi-target preview with
`chosen_targets`; the per-row domain-scoped provider search; confirm's
re-staging; commit's per-record domain resolution). The book-specific parts are
only the header word lists, the package import and the label copy. The sprint:
the reader moves to the registry declaring every registered domain; the word
lists and the creators-column label become per-domain declarations; the screen
gains a single-pick domain dropdown whose choice composes the fingerprint (one
list, one domain); the search-then-confirm machinery is reused unchanged and
re-proven against a non-book domain's recorded fixtures plus a live non-book
walkthrough.

## Where the release session left things (2026-09-14)

- **v2.1.0 is out**: PR #20 (merge commit on main, tag `v2.1.0`), the Release
  workflow published `ghcr.io/mauroibz/akasha:2.1.0` + `:2.1` + `:latest`,
  verified by anonymous manifest inspect; the GitHub Release carries
  `docs/operations/release-notes-v2.1.md` with links rewritten.
- **One CI flake was triaged as a real bound, not a flake**: the checks job
  failed three times on `test_a_bundle_over_the_declared_caps_is_refused` —
  not the v2.0.0 sandbox stall but pytest-timeout's 30 s firing inside the
  10,001-part multipart parse (max_files + 1 is the connector's real declared
  cap; Sprint 051 measured this test at 11.7 s on a workstation, and a shared
  runner's I/O ate the headroom). The fix — a per-test
  `@pytest.mark.timeout(120)` with the reason in its docstring — is on main
  in commit `d077489` and in the PR. A rerun-only response stopped being
  right on the second identical failure.
- The release-session worklog entry and the post-release HANDOFF are appended.

## Known and left, in the order they are likely to bite

1. **The version surfaces all read `2.1.0`** and the validator gates them;
   Sprint 084 adds no release and must not bump them.
2. **DEC-154's residual proof** (Tailscale tailnet walkthrough) is still owed
   by the owner.
3. **Contended insights at 10k entries** (DEC-155) remains unowned by a sprint.
4. **The dev machine's standing container** runs a locally-built image under
   the reused `1.5.7` tag (compose.build.yaml overlay) — it now carries 2.1.0
   plus everything since; the board still needs its own `AKASHA_VERSION=2.1.0`
   pull to upgrade.
5. **Non-book provider relevance** for hand-written text is Sprint 084's own
   risk item: MusicBrainz text search for Spanish-titled albums may be weaker
   than Open Library's. The top-10 + edit + discard + exclude affordances are
   the designed answer; record observed relevance, do not fix providers.

## Protocol notes for whoever executes

- This was a docs-only planning session riding a release session: the release
  (code + tag + publish) was owner-directed; the plan revision is the six-artifact
  set (ROADMAP revision 42, state.json, DEC-160, FINAL_SPRINT 83 → 84 in the
  validator with the move recorded, this HANDOFF, the sprint file at `ready`).
- Claim the sprint with `python scripts/sync_sprint_state.py --sprint 084
  in_progress` when starting. The sprint file's Commit checkpoints, Verification
  and explicit non-scope are binding.
- The v2.1.0 regression suite is the contract Sprint 084 must not weaken: every
  existing list-import assertion (books) stays green byte-for-byte while the
  connector generalizes.
