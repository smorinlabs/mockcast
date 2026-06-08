# Design: Release + Contributors Automation for mockcast

**Date:** 2026-06-07
**Status:** Approved design (precursor to an implementation plan)
**Repo:** smorinlabs/mockcast (public)

## Summary

Add GitHub Actions automation for **releases** (release-please → versioned PR →
tag → build → publish to TestPyPI then PyPI via OIDC) and **contributors**
(`contributors-please` auto-maintains `CONTRIBUTORS.md`), plus a **commitlint**
gate that makes release-please's Conventional-Commits flow reliable. The design
is a **hybrid** of two reference repos:

- **`~/c/doxa-research`** — clean split workflow *structure* (`release-please.yml`
  + `publish.yml`, TestPyPI→PyPI chain, deny-by-default permissions, tag-on-main
  + version-match guards, self-contained commitlint).
- **`~/c/py-launch-blueprint`** — *secret naming* (the names already set on this
  repo) and the *contributors* setup (`smorinlabs/contributors-please-action`,
  `.contributors.yml`).

## Goals

- Merging Conventional-Commit work to `main` automatically opens/maintains a
  release PR; merging it tags a release and publishes to PyPI — no manual tag.
- Every publish is OIDC Trusted Publishing (no API tokens stored), TestPyPI
  first then PyPI.
- `CONTRIBUTORS.md` stays current automatically via PRs.
- Conventional Commits enforced on PRs.

## Non-Goals

- Changing the existing `ci.yml` (format/lint/typecheck/test) — it stays as is.
- Publishing the historical `0.1.0` (see Open Decision 1).
- A dependabot/commitlint human-vs-bot split (no dependabot configured yet).

## Preconditions (state today)

- ✅ App secrets already set on the repo (via the repo-secrets skill):
  `RELEASE_PLEASE_APP_ID`, `RELEASE_PLEASE_PRIVATE_KEY`,
  `CONTRIBUTORS_PLEASE_APP_ID`, `CONTRIBUTORS_PLEASE_PRIVATE_KEY` — all as
  **secrets** (matches py-launch-blueprint's reference style; the workflows read
  `secrets.RELEASE_PLEASE_APP_ID` etc., **not** doxa's `vars.` form).
- ⏳ **You:** point the PyPI **and** TestPyPI Trusted Publishers at workflow
  filename **`publish.yml`**, environment names **`testpypi`** and **`pypi`**.
- ⏳ Create GitHub Environments `testpypi` and `pypi` in the repo (recommend a
  required-reviewer rule on `pypi`).
- Existing `ci.yml` pins `actions/checkout@v4` + `astral-sh/setup-uv@v6`; new
  workflows reuse those versions for consistency.

## Architecture (file-by-file)

Each workflow is single-purpose; they hand off only via the git tag.

```
push to main ─▶ release-please.yml ─┬─ release-please job ─▶ Release PR ─(merge)─▶ tag v* + GitHub Release
                                    └─ sync-uv-lock job (after release_created)
tag v* ─▶ publish.yml ─▶ build ─▶ publish-testpypi (env testpypi) ─▶ publish-pypi (env pypi)
PR ─▶ commitlint.yml (gate)
push to main ─▶ update-contributors.yml ─▶ PR updating CONTRIBUTORS.md
```

### 1. `.github/workflows/release-please.yml`

- `on: push: branches: [main]`; `permissions: {}`; `concurrency: release-please-${{ github.ref }}`, `cancel-in-progress: false`.
- **Job `release-please`** (`permissions: contents: read`): mint App token via
  `actions/create-github-app-token@v3` from `secrets.RELEASE_PLEASE_APP_ID` +
  `secrets.RELEASE_PLEASE_PRIVATE_KEY`; run `googleapis/release-please-action@v5`
  with `config-file` + `manifest-file` and `token: ${{ steps.app-token.outputs.token }}`.
  Outputs `release_created`, `tag_name`. (App token — not `GITHUB_TOKEN` — so the
  tag retriggers `publish.yml`.)
- **Job `sync-uv-lock`** (`needs: release-please`, `if: release_created == 'true'`):
  mint a fresh App token, `actions/checkout@v4` (ref `main`, App token),
  `astral-sh/setup-uv@v6`, `uv lock`, then commit `chore(release): sync uv.lock
  for $TAG_NAME` only if `uv.lock` changed (committer = `${app-slug}[bot]`).

### 2. `.github/workflows/publish.yml`

- `on: push: tags: ["v*"]`; `permissions: {}`; `concurrency: publish-${{ github.ref }}`, `cancel-in-progress: false`.
- **Job `build`** (`contents: read`): `actions/checkout@v4` (`fetch-depth: 0`) →
  **verify tag reachable from `origin/main`** (`git merge-base --is-ancestor`) →
  **verify tag == `pyproject` version** (`python3 -c "import tomllib…"`, stdlib on
  3.12) → `uv build` → `actions/upload-artifact@v4` (`name: dist`, `if-no-files-found: error`).
- **Job `publish-testpypi`** (`needs: build`, `environment: testpypi`,
  `permissions: id-token: write`): `setup-uv@v6`, `download-artifact@v4`,
  `uv publish --trusted-publishing always --publish-url https://test.pypi.org/legacy/ --check-url https://test.pypi.org/simple/`.
- **Job `publish-pypi`** (`needs: publish-testpypi`, `environment: pypi`,
  `permissions: id-token: write`): `setup-uv@v6`, `download-artifact@v4`,
  `uv publish --trusted-publishing always --check-url https://pypi.org/simple/`.
- No stored tokens; OIDC only.

### 3. `release-please-config.json`

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "pull-request-title-pattern": "chore(release): release ${version}",
  "packages": {
    ".": {
      "package-name": "mockcast",
      "include-v-in-tag": true,
      "include-component-in-tag": false,
      "bump-minor-pre-major": true,
      "bump-patch-for-minor-pre-major": false,
      "changelog-path": "CHANGELOG.md",
      "extra-files": [
        { "type": "toml", "path": "pyproject.toml", "jsonpath": "$.project.version" }
      ]
    }
  },
  "changelog-sections": [
    { "type": "feat", "section": "Features" },
    { "type": "fix", "section": "Bug Fixes" },
    { "type": "perf", "section": "Performance" },
    { "type": "refactor", "section": "Refactoring" },
    { "type": "docs", "section": "Documentation" },
    { "type": "ci", "section": "CI/CD" },
    { "type": "test", "section": "Testing" },
    { "type": "chore", "section": "Miscellaneous", "hidden": true }
  ]
}
```

- `release-type: python` bumps `[project] version` in `pyproject.toml`; the
  `extra-files` toml jsonpath is belt-and-suspenders for the same field.
- `bump-minor-pre-major: true` → pre-1.0 breaking changes bump the minor, not
  major; `feat` → minor, `fix` → patch.
- `chore` hidden so the `sync-uv-lock` commit never spawns a new release PR.

### 4. `.release-please-manifest.json`

```json
{ ".": "0.1.0" }
```

- A `v0.1.0` tag already exists, so release-please (manifest mode) parses commits
  *after* that tag — no `bootstrap-sha` needed. (Add `bootstrap-sha` to the config
  only if release-please can't locate the prior tag during the first run.)

### 5. `.github/workflows/commitlint.yml` + `commitlint.config.mjs`

- `commitlint.yml`: `on: pull_request: branches: [main]`;
  `permissions: contents: read, pull-requests: read`;
  `concurrency: commitlint-${{ github.event.pull_request.number }}`,
  `cancel-in-progress: true`; `actions/checkout@v4` (`fetch-depth: 0`) →
  `wagoid/commitlint-github-action@v6` (`configFile: commitlint.config.mjs`).
- `commitlint.config.mjs`: **self-contained** (no `extends`, no `node_modules`),
  enforcing lowercase non-empty type from the Conventional set, non-empty subject,
  no trailing period, 100-char header, blank lines before body/footer.

### 6. `.github/workflows/update-contributors.yml` + `.contributors.yml` + `CONTRIBUTORS.md`

- `update-contributors.yml`: `on: push: branches: [main]` with
  `paths-ignore: [CONTRIBUTORS.md, .contributors.jsonl]` (+ `workflow_dispatch`);
  `permissions: contents: write, pull-requests: write, issues: write`;
  `actions/checkout@v4` (`fetch-depth: 0`) →
  `smorinlabs/contributors-please-action@v1.0.6` with `app-id` +
  `private-key` from the `CONTRIBUTORS_PLEASE_*` secrets, `output-file:
  CONTRIBUTORS.md`, `state-file: .contributors.jsonl`, `config-file:
  .contributors.yml`, `mode: pull-request`.
- `.contributors.yml`: `classifier: path`, in-place markers, `min_contributions: 1`,
  `ignore` list (`Copilot`, `claude`, `github-actions[bot]`, `dependabot[bot]`,
  and the **actual** release-please + contributors-please bot slugs — to be
  confirmed from the installed App names), classification (docs:
  `docs/**`/`*.md`/`.github/**`; quality: `tests/**`; default code; combination
  `project`), `identity_map` for `smorin` → `steve.morin@gmail.com`.
- `CONTRIBUTORS.md`: seeded with a header + the
  `<!-- contributors-please:start -->` / `…:end -->` marker pair the action fills.

### 7. `CHANGELOG.md`

- Created/managed by release-please (Keep-a-Changelog format). Optionally seed an
  empty header; release-please will populate on first release.

## Action-version normalization

doxa's report listed `upload-artifact@v7`/`download-artifact@v8`, which are not
real public majors (the artifact actions are at **v4**). This design uses the
real current majors and the versions already in mockcast's `ci.yml`:
`actions/checkout@v4`, `astral-sh/setup-uv@v6`, `actions/upload-artifact@v4`,
`actions/download-artifact@v4`, `actions/create-github-app-token@v3`,
`googleapis/release-please-action@v5`, `wagoid/commitlint-github-action@v6`,
`smorinlabs/contributors-please-action@v1.0.6`. The plan must verify each pin
resolves before relying on it.

## One-time setup checklist (operator)

1. ✅ App secrets set (done).
2. Create GitHub Environments `testpypi` and `pypi` (required reviewer on `pypi`
   recommended).
3. Point PyPI + TestPyPI Trusted Publishers at `publish.yml` / envs
   `testpypi` / `pypi`.
4. Confirm the installed GitHub Apps' bot slugs and add them to `.contributors.yml`
   `ignore`.

## Open decisions (record + recommendation; resolved in the plan)

1. **First-release reconciliation.** `v0.1.0` tag + GitHub Release exist, but PyPI
   has only the `0.0.0.dev0` placeholder, so with the manifest at `0.1.0` the next
   release-please PR cuts `0.1.1`/`0.2.0` and `0.1.0` never auto-publishes.
   **Recommendation:** publish `0.1.0` once manually (`uv build` + `uv publish`
   via the new trusted publisher, or a one-off re-push of the `v0.1.0` tag after
   `publish.yml` lands) so PyPI has a real `0.1.0`; then let automation own
   everything from the next bump.
2. **contributors-please PAT.** py-launch also passes an optional
   `CONTRIBUTORS_PLEASE_PAT`; this repo has only the App pair. **Recommendation:**
   ship App-pair-only and verify the action accepts it; add a PAT only if it
   requires one.

## Testing / acceptance

- `release-please.yml`, `publish.yml`, `commitlint.yml`, `update-contributors.yml`
  pass `actionlint`.
- A `feat:`/`fix:` commit merged to `main` opens a release PR with a correct
  version bump + changelog; merging it tags `v*`.
- The tag triggers `publish.yml`; `build` guards pass; TestPyPI then PyPI publish
  succeed via OIDC (verified by a real release, e.g. the reconciled `0.1.0` or the
  first `0.1.1`).
- A non-conventional PR commit fails `commitlint`.
- `update-contributors` opens a PR adding contributors to `CONTRIBUTORS.md`; a
  re-run is a no-op (loop-safe via `paths-ignore`).
- Existing `ci.yml` and the 26 tests remain green.

## Out-of-scope follow-ups

- dependabot + a human/bot commitlint split.
- TestPyPI environment protection rules.
- A `RELEASE.md` runbook documenting the App + trusted-publisher setup.
