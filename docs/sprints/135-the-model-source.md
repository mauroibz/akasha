# Sprint 135 — The model source

**Sprint:** 135
**Status:** planned
**Roadmap revision:** 54
**Depends on:** 134
**Owner:** Mauro

## Objective

A language model behind any OpenAI-compatible endpoint, local or hosted, can be a recommendation
source for every domain, with its candidates shown only after the domain resolves them.

## Required context

- DEC-183 point 7; Sprints 133–134 Outcomes; `domain/recommendations.py`; `config.py`;
  `.env.example`; the runbook's configuration section.

## Deliverables

1. Configuration: `AKASHA_RECS_MODEL_URL` (base URL), `AKASHA_RECS_MODEL`, optional
   `AKASHA_RECS_MODEL_KEY`, and a daily call budget. Unset means `not_configured`.
2. `model` source: builds a compact prompt from the seed (or profile: top scores, recent
   finishes, dismissed, the pile's titles so it does not repeat them) for one domain, asks for
   strict JSON (`title`, `creator`, `year`, `reason`) with up to eight items, validates it, and
   returns candidates. A malformed reply fails the round with a recorded reason.
3. Every domain declares `"model"` after its existing sources; a model candidate that the
   domain's resolve cannot find is stored `unresolved` and never shown.
4. The sheet's *Model* segment; Settings shows whether the source is configured and what it
   sends (titles and scores, nothing else).
5. Recordings: real responses from a real endpoint. Preferred: a local server on this machine
   (Ollama or llama.cpp run from the scratchpad, no system install); a hosted one only with the
   owner's key.

## Acceptance criteria

1. Against a recorded reply, a book seed yields resolved candidates and drops an invented title
   (tested with a recorded reply that contains one).
2. Unset configuration: the segment says how to configure it; nothing fails.
3. The prompt contains no data beyond titles, creators, years and scores (tested).
4. Budget exhaustion stops further calls (tested).

## Verification

Per DEC-167; one live round against the real endpoint used for the recordings; a walkthrough of
the *Model* segment.

## Explicit non-scope

Embeddings (136); choosing a hosted provider for the owner.

## Risks and decisions to surface

If no real endpoint can be run, the sprint stays blocked rather than shipping hand-written
recordings (AGENTS.md: external boundaries are proven against recorded real responses).

## Outcome

_Not started._
