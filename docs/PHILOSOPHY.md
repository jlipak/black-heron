# Philosophy — Why Black Heron

> A canopy-feeding heron spreads its wings to cast a still, dark shadow over the water. Fish, mistaking the shadow for shelter, swim under it — and then the strike. **Stillness draws the catch; precision delivers it.**

Black Heron applies the same posture to a code repository: spread a wide multi-lens cover, let the issues surface under it on their own, then strike with a sharp, deduplicated, verifier-filtered audit report.

## Why this exists

Most "AI code review" tools have one of two failure modes:

1. **Noise dump.** Every linter warning, every unused import, every TODO becomes a "finding". The reader stops reading by page two. The report becomes ignorable, which means the system has failed.
2. **Hype filter.** The tool only ever says "looks good!" because flagging real issues risks being wrong. The reader gains nothing. The system has also failed — just quieter.

Black Heron's working hypothesis is that **the missing discipline is adversarial verification**. Three independent lenses propose findings. A separate verifier — operating with no stake in any lens being right — challenges every one of them. KEEP / REJECT / DOWNGRADE is the only output the verifier produces. The report ships what survives.

## Design principles

### 1. Three lenses, separate prompts, no shared state

`code_quality`, `governance`, and `drift` each receive the same repo context and produce findings independently. They cannot cross-contaminate. A finding that surfaces in two lenses is a stronger signal than one that surfaces in one — but Black Heron doesn't auto-promote on duplicate sightings; the verifier sees the duplicate and decides.

### 2. Cite or kill

A finding must point to a file path and line range. The evidence field must quote 1–3 lines verbatim from the source. If a lens cannot cite, it must not raise. The system prompt enforces this; the verifier rejects findings whose evidence doesn't support the claim.

### 3. Verifier holds the kill switch

If any lens produces more than 50 P0+P1 findings on a single repo, the verifier aborts the run rather than ship noise. The assumption: the lens has a bug or the prompt drifted; better to silence than poison. The kill threshold is a config value, not a wish.

### 4. The verifier is a separate model

The lenses run on Sonnet. The verifier runs on Opus. The cost differential is intentional — adversarial work is where deeper reasoning earns its keep, and lens work is where consistent structured output earns its keep.

### 5. Honest scope in the report

Every report includes a footer naming what Black Heron does NOT do yet. v0.1 doesn't ingest from GitHub URLs, doesn't persist a baseline for drift-over-time, doesn't cache by content hash. A reader who finds a missing feature should find the gap acknowledged before they find it themselves.

### 6. Severity is calibrated, not inflated

- **P0** is reserved for issues that materially break correctness, security, or compliance. Hardcoded secrets. Missing audit trail on a decision path. Hallucinated tools in a smoke test.
- **P1** is maintainability erosion or governance gaps that compound over time. Threshold magic numbers without citation. Atomic-write that doesn't clean up its temp file on failure.
- **P2** is polish — minor staleness, single-file inconsistencies, onboarding-friction-but-not-blocker.

If everything reads as P0, the verifier should be downgrading; if nothing reads as P0, the lens prompts are probably tuned too cautious.

## What Black Heron will NEVER be

- **A linter.** Black Heron is one read pass at a slice in time. It is not a CI gate. It is an audit, in the legal sense — a snapshot meant to inform a reviewer's decision.
- **A test runner.** It does not execute code under audit.
- **A patch generator.** It surfaces issues; it does not propose fixes inline.
- **A replacement for a code reviewer.** It is a tool the reviewer uses, not the reviewer.

## Provenance

This system was built in a focused sprint as a side artifact alongside a separate governance-focused deliverable. The recursive bit: Black Heron's first audit target was that other deliverable. The honest result of that first audit — verified findings, downgrades, rejections, and the v0.1 false-positive rate — ships with the project in `examples/`.
