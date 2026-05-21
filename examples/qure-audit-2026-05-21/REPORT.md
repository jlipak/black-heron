# Black Heron — Audit Report

> Generated 2026-05-21 15:17 UTC

**Repository:** `C:\Users\DOBY\Desktop\qure-clean-staging`
**Files audited:** 116 (primary language: TypeScript)
**TODO markers found in source:** 0

## Lens raw output

| Lens | Raw findings |
|---|---|
| code_quality | 9 |
| governance | 7 |
| drift | 9 |

After adversarial verifier: **15 kept**, **10 rejected**.

## P0 findings (2)

### P0.1 — NOTICE.md states 'The full upstream MIT license text is preserved in `poc/qure_compliance/LICENSE`' but no `LICENSE` file appears anywhere under `poc/qure_compliance/` in the file listing.

- **Lens:** drift
- **File:** `NOTICE.md` lines `L7`
- **Confidence:** 0.97

**Evidence:**
```
The full upstream MIT license text is preserved in `poc/qure_compliance/LICENSE`.
```
**Why it matters:** The attribution obligation from the upstream MIT-licensed code (claude-video-vision) cannot be verified or fulfilled if the LICENSE file does not exist, creating a compliance gap between the stated and actual state of the repository.
**Verifier note:** Legal/attribution gap with explicit textual claim vs. absent file — high-impact and easy for a reviewer to verify.

### P0.2 — The smoke test asserts three registered MCP tools — `compliance_scan`, `video_info`, and `video_setup` — but only `compliance_scan` has a corresponding source file in the repository; `src/tools/video_info.ts` and `src/tools/video_setup.ts` are absent from the file listing.

- **Lens:** drift
- **File:** `poc/qure_compliance/scripts/smoke-mcp.ts` lines `L21-L23`
- **Confidence:** 0.90

**Evidence:**
```
const expected = ["compliance_scan", "video_info", "video_setup"];
const missing = expected.filter((e) => !toolNames.includes(e));
```
**Why it matters:** The smoke test will exit 1 on every run because two of the three tools it expects cannot exist without their source files, meaning `npm run smoke` is broken and the claimed tool surface area is fiction.
**Verifier note:** Tools may be registered inline in a server file rather than as separate source files, but the absence of the files combined with the hard assertion is concrete enough to flag — reviewer should confirm registration site.

## P1 findings (7)

### P1.1 — The transcript extraction script references `evals/golden/v1.1.0/videos/` as its video source directory, but no `videos/` subdirectory exists under `evals/golden/v1.1.0/` in the file listing.

- **Lens:** drift
- **File:** `evals/golden/v1.1.0/_extract_transcripts.py` lines `L10`
- **Confidence:** 0.90

**Evidence:**
```
VIDEOS_DIR = "evals/golden/v1.1.0/videos"
```
**Why it matters:** The script will silently skip all 10 videos with 'video not found' messages and produce no transcripts, making the golden-set preparation workflow non-functional without any obvious error to a new contributor.
**Verifier note:** Concrete missing-directory claim that breaks the documented golden-set workflow; videos directories are often gitignored but the script's silent-skip behavior is the real defect.

### P1.2 — The eval README documents that `runner.ts` reads video files from `../../../evals/golden/v1.0.0/videos/*.mp4`, but no `videos/` subdirectory exists under `evals/golden/v1.0.0/` or `evals/golden/v1.1.0/` in the file listing.

- **Lens:** drift
- **File:** `poc/qure_compliance/evals/README.md` lines `L17-L24`
- **Confidence:** 0.85

**Evidence:**
```
| `../../../evals/golden/v1.0.0/videos/*.mp4` | the actual videos (downloaded by `scripts/download-golden-set.ts`) |
```
**Why it matters:** Anyone following the documented eval workflow will encounter a missing-file error immediately; the golden set videos are either never downloaded or the download script's output path diverged from what the runner expects.
**Verifier note:** Video binaries are typically gitignored, so absence is expected, but the README should explicitly say so — keep as a documentation/UX defect rather than a true correctness bug.

### P1.3 — EXISTING_G001 is a hardcoded absolute-style relative path pointing to a specific dated audit output directory that is unlikely to exist in other developer environments or CI.

- **Lens:** code_quality
- **File:** `evals/golden/v1.1.0/_extract_transcripts.py` lines `L18-L19`
- **Confidence:** 0.92

**Evidence:**
```
EXISTING_G001 = "poc/qure_compliance/audit_output/qure-2026-05-20-065/transcript.json"
```
**Why it matters:** The path encodes a specific run timestamp; on any other machine or after audit output is cleaned, os.path.exists returns False and the script prints 'video not found' for g001, producing a silently incomplete golden set that skews eval metrics.
**Verifier note:** Hardcoded timestamped path is a clear reproducibility defect for the golden-set build pipeline.

### P1.4 — The fallback branch silently returns a video-only (no audio) file when yt-dlp produces per-stream fragments but no merged output, without throwing or logging a warning that audio-dependent criteria (C6, C7) will silently fail.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/extractors/source.ts` lines `L95-L99`
- **Confidence:** 0.85

**Evidence:**
```
// Fallback: any .mp4 (even per-stream video-only — audio will be missing)
const pick = files.find((f) => /\.mp4$/i.test(f)) ?? files[0];
return { localPath: join(workDir, pick), originalSource: url };
```
**Why it matters:** Downstream transcript-based rubric criteria (C6, C7) are hard_fail criteria; silently processing a muted file will produce systematically wrong verdicts without any indication of the root cause.
**Verifier note:** The inline comment itself acknowledges the silent failure mode — downgraded from P0 to P1 because impact depends on rare yt-dlp output state and the comment shows the author is aware.

### P1.5 — requireAnthropicKey's placeholder guard `k.startsWith("sk-ant-...")` only catches the literal placeholder substring, providing no structural validation beyond a 10-char length check; misconfigured keys can pass.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/config.ts` lines `L43-L48`
- **Confidence:** 0.80

**Evidence:**
```
if (!k || k.startsWith("sk-ant-...") || k.length < 10) {
```
**Why it matters:** The guard gives false confidence that a real key is present; a fabricated 10-char string passes startup validation and is forwarded to the live API, obscuring configuration errors at runtime.
**Verifier note:** Real defect but P0 overstates it — invalid keys still fail at the API call boundary; downgrading and consolidating with the duplicate Finding 15.

### P1.6 — writeAuditJson performs an atomic write via temp+rename but does not clean up the .tmp file on failure, leaving orphaned temporary files.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/audit/serializer.ts` lines `L130-L135`
- **Confidence:** 0.80

**Evidence:**
```
const tempPath = `${finalPath}.tmp`;
const json = JSON.stringify(audit, null, 2);
await writeFile(tempPath, json, "utf-8");
await rename(tempPath, finalPath);
```
**Why it matters:** If writeFile succeeds but rename fails, the .tmp file persists and may be mistaken for a valid audit file by directory-listing logic in nextAuditId.
**Verifier note:** Real robustness gap in atomic-write pattern; the directory-listing collision risk only materializes if readdir doesn't filter by suffix, which reviewer can verify.

### P1.7 — The vision_model default is hardcoded to 'claude-sonnet-4-6', which does not correspond to any publicly documented Anthropic model identifier.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/src/config.ts` lines `L36-L38`
- **Confidence:** 0.70

**Evidence:**
```
vision_model: env.QURE_VISION_MODEL ?? "claude-sonnet-4-6",
```
**Why it matters:** A wrong default model ID causes every production scan that doesn't override QURE_VISION_MODEL to fail or be routed to an unintended model, with no startup validation.
**Verifier note:** Model ID looks malformed (Anthropic uses formats like `claude-sonnet-4-5-20250929`); worth surfacing for the reviewer to confirm.

## P2 findings (6)

### P2.1 — The audit record persists `models_used` with optional `snapshot` field but does not capture the raw prompt text sent to the model.

- **Lens:** governance
- **File:** `poc/qure_compliance/src/audit/serializer.ts` lines `L51-L75`
- **Confidence:** 0.75

**Evidence:**
```
models_used: input.modelsUsed, ... typed as `Array<{ role: string; model_id: string; snapshot?: string }>` — no prompt or raw-response field is present in `SerializeInput`.
```
**Why it matters:** Without persisting the exact prompt, a future auditor cannot verify the model was queried under the rubric version active at the time, nor reproduce the inference.
**Verifier note:** Valid governance/reproducibility concern for an audit-trail system; severity appropriately P2 since prompts can be reconstructed from code+rubric version.

### P2.2 — The thresholds `max_frames: 120` and `target_fps: 0.5` are hardcoded defaults with no inline citation to the rubric file, spec document, or evaluation result that justifies those values.

- **Lens:** governance
- **File:** `poc/qure_compliance/src/config.ts` lines `L37-L39`
- **Confidence:** 0.80

**Evidence:**
```
max_frames: Number(env.QURE_MAX_FRAMES ?? "120"), target_fps: Number(env.QURE_TARGET_FPS ?? "0.5"),
```
**Why it matters:** Threshold defaults without cited rationale cannot be defended to a regulator; overrides via env vars also lack range validation.
**Verifier note:** Reasonable governance flag for a compliance-audit tool where defensibility of magic numbers matters.

### P2.3 — No `.env.example` file appears in the 116-file listing, even though `config.ts` references at least six environment variables that operators must supply.

- **Lens:** governance
- **File:** `poc/qure_compliance/src/config.ts` lines `L1-L60`
- **Confidence:** 0.85

**Evidence:**
```
config.ts L44: ANTHROPIC_API_KEY ... L50: OPENAI_API_KEY ... no `.env.example` file appears in the repository listing.
```
**Why it matters:** Without a `.env.example`, a new operator cannot determine the full set of required secrets without reading source code, increasing misconfiguration risk.
**Verifier note:** Standard onboarding/operability gap; P2 is appropriate.

### P2.4 — The module docstring references 'poc/base/mcp-server/src/backends/local.ts' but no `poc/base/` directory exists in the repository.

- **Lens:** drift
- **File:** `poc/qure_compliance/scripts/whisper-local.py` lines `L6`
- **Confidence:** 0.70

**Evidence:**
```
Pattern adapted from poc/base/mcp-server/src/backends/local.ts (MIT, Jordan Vasconcelos).
```
**Why it matters:** The referenced upstream file path is a stale attribution that cannot be verified within the repository.
**Verifier note:** Provenance comment likely references a sibling repo not in this checkout; minor but worth fixing for attribution clarity.

### P2.5 — `package.json` declares version `0.1.0` while `dashboard/index.html` displays `v1.1.0` and eval golden sets are `v1.0.0`/`v1.1.0`, creating an inconsistent version narrative.

- **Lens:** drift
- **File:** `poc/qure_compliance/package.json` lines `L3`
- **Confidence:** 0.70

**Evidence:**
```
package.json: "version": "0.1.0" / dashboard/index.html: "v1.1.0 short-form golden set · 10 videos"
```
**Why it matters:** A reader cannot determine whether `0.1.0` pre-dates `v1.0.0` eval or is a separate versioning axis, creating confusion about which software version produced published eval results.
**Verifier note:** Software version vs. rubric/eval version are legitimately separate axes, but the docs don't say so — minor clarity gap.

### P2.6 — rootDir is './src' but tests/ and evals/ are excluded from compilation, so type errors in test utilities are not surfaced by tsc.

- **Lens:** code_quality
- **File:** `poc/qure_compliance/tsconfig.json` lines `L8`
- **Confidence:** 0.70

**Evidence:**
```
"rootDir": "./src", ... "exclude": ["node_modules", "dist", "tests"]
```
**Why it matters:** Test files import from src under strict mode assumptions but are never type-checked by tsc; type regressions go undetected until vitest runtime.
**Verifier note:** Common TS project pattern; vitest does type-check via tsx, so impact is modest but the gap is real.

## Rejected findings (transparency)

These were proposed by a lens but rejected by the adversarial verifier. Listed here so a reader can see what was filtered.

- *nextAuditId catches readdir errors and silently swallows them with a comment 'dir didn't exist', but mkdir with recursive:true on line L105 already creates the directory, so the catch block is dead code that also hides real I/O errors.* — rejected: The catch is defensive against TOCTOU and non-ENOENT errors (e.g., EACCES post-mkdir); calling it 'dead code' is incorrect, and the duplicate-ID risk is speculative — reviewer noise outweighs signal.
- *scripts/scan-secrets.sh exits 0 silently when both stdin and TOOL_INPUT are empty, providing no defence when invoked outside the expected hook context.* — rejected: Exit 0 on empty input is correct hook behavior — there is nothing to scan; flagging this as a security gap misreads the script's contract.
- *ModelCall and Trace are imported from types.ts but ModelCall is never referenced in this file's code.* — rejected: Unused-import nitpick; TS compiler/linter handles this and it does not warrant audit-report space.
- *The rubric file name encodes 'v1' but the file itself was not sampled, so it is unconfirmed whether a machine-readable `version` field exists inside the JSON.* — rejected: Speculative finding admitting the evidence was not examined; the cited loader test (`expect(r.version).toBe("1.0.0")`) actually confirms the field exists and is read.
- *The compliance rubric documentation file was not sampled; it cannot be confirmed whether it carries a `version` field or change-log.* — rejected: Pure speculation based on not having read the file — not a defensible audit finding.
- *Duplicate of placeholder-key guard finding (governance P2 version covering config.ts L44-L48).* — rejected: Duplicates Finding 1/15 already kept once at P1; suppressing the duplicate per dedup rule.
- *The transcript-extraction script hardcodes a path to a specific prior audit output as a production data source for g001, creating an undocumented dependency on a local artifact.* — rejected: Duplicates Finding 4 (same file/line/issue) already kept under code_quality lens.
- *tsconfig sets rootDir to ./src and outDir to ./dist, yet evals/README.md instructs users to run `node dist/evals/runner.js` — evals/ sits outside src/ and would not be compiled.* — rejected: Could not verify the README instruction text from cited evidence; the runner may live at src/evals/runner.ts and emit to dist/evals/, which is consistent with the config. Insufficient evidence to ship.
- *The vision client (`src/vision/client.ts`) has no corresponding test file under `tests/vision/`, while every other src/ subdirectory has matching tests.* — rejected: Absence-of-test observation is structural commentary, not a defect with concrete evidence of a regression; risk of false-positive noise in audit report.
- *Neither `src/backends/transcription.ts` nor `src/extractors/ffmpeg.ts` nor `src/extractors/source.ts` has a corresponding test file, despite being adapted from upstream MIT code.* — rejected: Subprocess-wrapping code is notoriously hard to unit-test and is typically covered by smoke/integration tests; flagging coverage gaps without evidence of a defect is speculative.

---

## Honest scope (v0.1)

This is Black Heron v0.1 MVP. Things it does NOT do yet:
- No GitHub URL ingest — local path only
- No baseline persistence / drift-over-time
- No content-hash-based caching
- Only 3 lenses (code_quality, governance, drift)
- No HITL UI for ambiguous findings

See `README.md` Roadmap for v0.2 plans.