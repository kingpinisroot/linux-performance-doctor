# Contributing to Linux Performance Doctor

Thank you for your interest in contributing. The repository contains the initial Linux Performance Doctor CLI implementation and deterministic tests. All contributions must preserve the project's core diagnostic principles.

## Core Design Rules

Linux Performance Doctor is a **read-only Linux diagnostic tool**, not an optimizer, cleaner, or tuning script. Changes must preserve these boundaries:

1. Never modify system configuration, start or stop services, kill or alter processes, or write or delete system files.
2. Do not require privileged system mutations.
3. Report missing or inaccessible measurements as partial or unavailable rather than silently omitting them or fabricating values.
4. Keep subsystem collection modular and preserve structured JSON output.
5. Document only implemented commands, flags, collectors, and test results. Distinguish current behavior from future plans.

## Local Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite with `pytest -v`. Tests should use mocked or deterministic system fixtures where host state varies.

## Submitting Changes

1. Create a focused feature or fix branch from `main`.
2. Add or update tests for changed behavior.
3. Ensure `pytest -v` passes locally and CI passes on your pull request.
4. Describe what changed, why, and any limitations or platform assumptions.
