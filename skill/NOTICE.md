# NOTICE — Third-party attribution & influence

Black Heron Skill is an original work distributed under the MIT License. This NOTICE documents:

1. **Influences and prior art** that shaped the design (no code copied).
2. **Companion projects** in the Black Heron family.

## Influences (no code, design only)

### Karpathy claude.md pattern
The skill-as-markdown distribution model is inspired by Andrej Karpathy's pattern of using `claude.md` (or `agents.md`) as a project-level instruction file that LLM-based agents read on startup. Black Heron Skill applies this pattern to a multi-prompt orchestration: `SKILL.md` is the entry point, lens prompts and verifier prompt are referenced files. No code is borrowed; the pattern is methodological.

### Apollo Lex Audit (private — author's prior project)
The decision to add an adversarial verifier on a different model checkpoint comes from a multi-agent audit project that initially achieved a 37% false-positive rate without verification. The evidence-presence pre-check (verbatim substring match against input bundle) was introduced after a Phase 1 lens fabricated a quote against a non-existent file path. These lessons are documented inline in `LAW.md` (laws I, VI, VIII).

### EZEKIEL trading system (private — author's prior project)
The kill-switch discipline (cost cap, time cap, finding cap), the local-only-by-default posture, and the "verify before done" insistence all come from a real-money trading project where the circuit breaker fired correctly the first overnight and saved the operator a four-figure mistake. Documented in `LAW.md` law X.

### AKIRA collapse (private — author's prior project)
The "never rewrite — always patch" rule (`LAW.md` law III) is the post-mortem lesson from a 968-session project where 544 documented rewrite events silently lost accumulated bug fixes. The session-digest + memory-file discipline (referenced in the skill's workflow but not enforced at runtime — that's the Python edition's job) is the operational antidote.

## Companion project

### Python Black Heron — full implementation
[jlipak/black-heron](https://github.com/jlipak/black-heron) is the Python package edition. It implements the same lens prompts, same LAW.md, same adversarial verifier — but with deterministic SARIF generation, content-hash cache (`--no-cache` to bypass), baseline drift mode (`--baseline previous.json`), MCP server exposure, and a 109-test pytest suite. Suitable for production CI/CD where you need stable, machine-comparable outputs.

This skill is **the lightweight distribution** — same brain, different distribution model.

## License

This distribution is MIT-licensed. See [`LICENSE`](LICENSE).

---

*Author: Josip Lipak · 2026.*
