# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Send a private report to **lipakjosip442@gmail.com** with:

- what the problem is and where (file, function, command),
- steps or a small repo that reproduces it,
- the impact you expect (secret exposure, code execution, spend without a cap, ...).

You will get an acknowledgement within 7 days and a fix or a decision within 30 days. Credit in the changelog is given if you want it.

## Supported versions

Only the latest 1.x release receives fixes.

## What the tool does with your code

Black Heron reads the repository you point it at and sends file samples, entry-point contents and recent commit messages to the Anthropic API using the key in `ANTHROPIC_API_KEY`. Nothing is sent anywhere else. Optional `--enrich` adapters spawn third-party MCP servers (context7, firecrawl, playwright, sequential-thinking) that may contact their own services; they are off by default.

Secrets found in the repository are treated like any other text: they can appear in `REPORT.md` and `findings.json` if a lens quotes them as evidence. Scrub the output before sharing it.
