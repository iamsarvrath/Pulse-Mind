# Implementation Plan - Issue 1.2: CI Pipeline

## Goal

Set up a Continuous Integration (CI) pipeline using GitHub Actions to automate linting, security scanning, and testing for the Pulse-Mind project.

## User Review Required

> [!NOTE]
> This plan focuses on Python services as they make up the core of the backend and dashboard. Firmware CI is out of scope for this initial pipeline to keep it lightweight.

## Proposed Changes

### GitHub Workflows

#### [NEW] [.github/workflows/ci.yml](file:///c:/Users/SARVESH%20%20RATHOD/Desktop/Pulse-Mind/.github/workflows/ci.yml)

- **Triggers**: Push to `main`, `develop`; Pull Requests to `main`, `develop`.
- **Jobs**:
  1.  **Linting**:
      - Installs `black` and `flake8`.
      - Checks all python files in `services/`.
  2.  **Security**:
      - Installs `bandit` and `safety`.
      - Scans `services/` for common security issues.
  3.  **Testing**:
      - Installs `pytest`.
      - Runs unit tests (if any exist in `tests/` or `services/`).

### Project Root

- No changes to source code.
- Dependencies for CI will be installed on-the-fly in the runner or strictly from a requirements file if present.

## Verification Plan

### Automated Verification

- **Commit & Push**: Pushing this workflow file to the `feature/setup-ci-pipeline` branch should trigger the action on GitHub.
- **Check Status**: We cannot verify the _execution_ locally, but we can verify the _syntax_ and _local execution_ of the commands.

### Manual Verification Steps

1.  Run `pip install black flake8 bandit pytest` locally.
2.  Run `black --check services/` -> Should report formatting status.
3.  Run `flake8 services/` -> Should report linting errors.
4.  Run `bandit -r services/` -> Should report security findings.
5.  Run `pytest tests/` -> Should run available tests.
