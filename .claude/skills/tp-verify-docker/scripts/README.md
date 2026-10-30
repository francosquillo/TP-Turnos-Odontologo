# scripts/ — placeholder

Deterministic helpers for `tp-verify-docker` go here. None yet — candidates spotted during drafting:

- `check-hard-rules.py` — grep Pydantic `extra='forbid'`, `Annotated` Depends, `any` in TS, hardcoded secrets.
- `verify-quick.sh` / `verify-full.sh` — compose up, port override, alembic upgrade, pytest/vitest/tsc/validate, compose down.

Add a script only when at least two verify runs reinvent the same commands (skill-creator rule: repeated work across test cases → bundle it). Until then the skill runs the commands inline per SKILL.md.
