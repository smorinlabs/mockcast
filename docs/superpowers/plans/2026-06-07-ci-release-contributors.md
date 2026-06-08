# Release + Contributors Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Actions so merging Conventional-Commit work to `main` auto-opens a release PR, tagging it publishes to TestPyPI→PyPI via OIDC, and `CONTRIBUTORS.md` stays current — with commitlint gating commit format.

**Architecture:** Conventional split (`release-please.yml` for the release PR + tag; `publish.yml` for build+publish on `v*` tags) + `commitlint.yml` gate + `update-contributors.yml`. doxa-research's workflow structure wired to py-launch-blueprint's secret names (already on the repo) and contributors setup. Pure OIDC publishing — no stored PyPI tokens.

**Tech Stack:** GitHub Actions, `googleapis/release-please-action@v5`, `actions/create-github-app-token@v3`, `astral-sh/setup-uv@v6`, `uv build`/`uv publish --trusted-publishing`, `wagoid/commitlint-github-action@v6`, `smorinlabs/contributors-please-action@v1.0.6`. Local validation: `actionlint`, `jq`, `node --check`, `uv run python` (pyyaml).

**Spec:** `docs/superpowers/specs/2026-06-07-ci-release-contributors-design.md`

**Repo state:** `main` @ `0.1.0`; existing `.github/workflows/ci.yml`; App secrets (`RELEASE_PLEASE_APP_ID`, `RELEASE_PLEASE_PRIVATE_KEY`, `CONTRIBUTORS_PLEASE_APP_ID`, `CONTRIBUTORS_PLEASE_PRIVATE_KEY`) already set.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `release-please-config.json` | release-please package config (python, mockcast) |
| `.release-please-manifest.json` | last-released version tracker |
| `.github/workflows/release-please.yml` | release PR + tag + uv.lock sync |
| `.github/workflows/publish.yml` | build → TestPyPI → PyPI (OIDC) on `v*` |
| `.github/workflows/commitlint.yml` | Conventional Commits gate on PRs |
| `commitlint.config.mjs` | self-contained commitlint rules |
| `.github/workflows/update-contributors.yml` | contributors PR on push to main |
| `.contributors.yml` | contributors classification/identity/ignore |
| `CONTRIBUTORS.md` | seeded file with marker block |
| `CHANGELOG.md` | seeded; release-please appends |

**Bootstrap note:** All work happens on branch `ci-automation` and lands via one PR. `commitlint.yml` and `ci.yml` run on that PR (GitHub runs `pull_request` workflows from the PR head). `release-please.yml` / `update-contributors.yml` (push-to-main) and `publish.yml` (tags) only act after merge — exercised in Tasks 8–10.

**Task type legend:** 🤖 = agent-suitable (file creation + local validation). 🧑 = operator (GitHub/PyPI web or live repo actions, env approvals, tag pushes).

---

## Task 1 🤖: release-please config + manifest

**Files:**
- Create branch `ci-automation`
- Create: `release-please-config.json`
- Create: `.release-please-manifest.json`

- [ ] **Step 1: Create the working branch**

```bash
cd /Users/stevemorin/c/mockcast
git checkout -b ci-automation
```

- [ ] **Step 2: Write `release-please-config.json`**

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

- [ ] **Step 3: Write `.release-please-manifest.json`**

```json
{ ".": "0.1.0" }
```

- [ ] **Step 4: Validate both JSON files parse**

Run:
```bash
jq . release-please-config.json >/dev/null && jq . .release-please-manifest.json >/dev/null && echo OK
```
Expected: `OK` (non-zero exit + parse error if malformed).

- [ ] **Step 5: Commit**

```bash
git add release-please-config.json .release-please-manifest.json
git commit -m "ci: add release-please config and manifest"
```

---

## Task 2 🤖: release-please workflow

**Files:**
- Create: `.github/workflows/release-please.yml`

- [ ] **Step 1: Write `.github/workflows/release-please.yml`**

```yaml
name: release-please

on:
  push:
    branches: [main]

permissions: {}

concurrency:
  group: release-please-${{ github.ref }}
  cancel-in-progress: false

jobs:
  release-please:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    outputs:
      release_created: ${{ steps.release.outputs.release_created }}
      tag_name: ${{ steps.release.outputs.tag_name }}
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          app-id: ${{ secrets.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_PRIVATE_KEY }}

      - uses: googleapis/release-please-action@v5
        id: release
        with:
          token: ${{ steps.app-token.outputs.token }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json

  sync-uv-lock:
    needs: release-please
    if: needs.release-please.outputs.release_created == 'true'
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/create-github-app-token@v3
        id: app-token
        with:
          app-id: ${{ secrets.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_PRIVATE_KEY }}

      - uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}
          ref: main

      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Regenerate uv.lock from pyproject
        run: uv lock

      - name: Commit uv.lock if changed
        env:
          TAG_NAME: ${{ needs.release-please.outputs.tag_name }}
          APP_SLUG: ${{ steps.app-token.outputs.app-slug }}
        run: |
          if git diff --quiet uv.lock; then
            echo "uv.lock already in sync; nothing to commit."
            exit 0
          fi
          git config user.email "${APP_SLUG}[bot]@users.noreply.github.com"
          git config user.name "${APP_SLUG}[bot]"
          git add uv.lock
          git commit -m "chore(release): sync uv.lock for ${TAG_NAME}"
          git push origin main
```

- [ ] **Step 2: Lint the workflow**

Run: `actionlint .github/workflows/release-please.yml`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-please.yml
git commit -m "ci: add release-please workflow"
```

---

## Task 3 🤖: PyPI publish workflow

**Files:**
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Write `.github/workflows/publish.yml`**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

permissions: {}

concurrency:
  group: publish-${{ github.ref }}
  cancel-in-progress: false

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true

      - name: Verify tag is reachable from main
        run: |
          git fetch origin main
          if ! git merge-base --is-ancestor "${GITHUB_SHA}" origin/main; then
            echo "::error::Tag ${GITHUB_REF_NAME} (${GITHUB_SHA}) is not on main."
            exit 1
          fi
          echo "Tag ${GITHUB_REF_NAME} is on main."

      - name: Verify tag matches pyproject version
        run: |
          TAG_VERSION="${GITHUB_REF_NAME#v}"
          PKG_VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
          if [ "${TAG_VERSION}" != "${PKG_VERSION}" ]; then
            echo "::error::tag ${TAG_VERSION} != pyproject ${PKG_VERSION}"
            exit 1
          fi
          echo "Tag matches pyproject version (${TAG_VERSION})."

      - name: Build sdist + wheel
        run: uv build

      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
          if-no-files-found: error

  publish-testpypi:
    name: Publish to TestPyPI
    needs: build
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write
    steps:
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: false
          ignore-empty-workdir: true

      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish to TestPyPI
        run: >-
          uv publish --trusted-publishing always
          --publish-url https://test.pypi.org/legacy/
          --check-url https://test.pypi.org/simple/

  publish-pypi:
    name: Publish to PyPI
    needs: publish-testpypi
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: false
          ignore-empty-workdir: true

      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish to PyPI
        run: uv publish --trusted-publishing always --check-url https://pypi.org/simple/
```

- [ ] **Step 2: Lint the workflow**

Run: `actionlint .github/workflows/publish.yml`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: add PyPI publish workflow (OIDC, TestPyPI then PyPI)"
```

---

## Task 4 🤖: commitlint gate

**Files:**
- Create: `.github/workflows/commitlint.yml`
- Create: `commitlint.config.mjs`

- [ ] **Step 1: Write `commitlint.config.mjs`**

```javascript
// Self-contained Conventional Commits config (no `extends`, no node_modules).
export default {
  rules: {
    'type-empty': [2, 'never'],
    'type-case': [2, 'always', 'lower-case'],
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'perf', 'refactor', 'docs', 'test', 'ci', 'chore', 'build', 'style', 'revert'],
    ],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'header-max-length': [2, 'always', 100],
    'body-leading-blank': [2, 'always'],
    'footer-leading-blank': [2, 'always'],
  },
};
```

- [ ] **Step 2: Write `.github/workflows/commitlint.yml`**

```yaml
name: commitlint

on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: read

concurrency:
  group: commitlint-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  commitlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: wagoid/commitlint-github-action@v6
        with:
          configFile: commitlint.config.mjs
```

- [ ] **Step 3: Validate config syntax + workflow lint**

Run:
```bash
node --check commitlint.config.mjs && actionlint .github/workflows/commitlint.yml && echo OK
```
Expected: `OK` (node reports syntax errors if any; actionlint silent on success).

- [ ] **Step 4: Commit**

```bash
git add commitlint.config.mjs .github/workflows/commitlint.yml
git commit -m "ci: add commitlint Conventional Commits gate"
```

---

## Task 5 🤖: contributors automation

**Files:**
- Create: `.github/workflows/update-contributors.yml`
- Create: `.contributors.yml`
- Create: `CONTRIBUTORS.md`

- [ ] **Step 1: Write `.github/workflows/update-contributors.yml`**

```yaml
name: Update Contributors

on:
  push:
    branches: [main]
    paths-ignore:
      - CONTRIBUTORS.md
      - .contributors.jsonl
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  contributors-please:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Update contributors
        uses: smorinlabs/contributors-please-action@v1.0.6
        with:
          app-id: ${{ secrets.CONTRIBUTORS_PLEASE_APP_ID }}
          private-key: ${{ secrets.CONTRIBUTORS_PLEASE_PRIVATE_KEY }}
          output-file: CONTRIBUTORS.md
          state-file: .contributors.jsonl
          config-file: .contributors.yml
          mode: pull-request
```

- [ ] **Step 2: Write `.contributors.yml`**

```yaml
classifier: path
output_file: CONTRIBUTORS.md
state_file: .contributors.jsonl
in_place: true
in_place_marker_start: "<!-- contributors-please:start -->"
in_place_marker_end: "<!-- contributors-please:end -->"
entry_template: "- [{{name}}]({{profile}}) - {{title}} ({{commits}} commits)"
columns_per_row: 1
sort: contributions
min_contributions: 1
ignore:
  - Copilot
  - claude
  - github-actions[bot]
  - dependabot[bot]
  - release-please-smorinlabs[bot]
  - contributors-please[bot]

classification:
  categories:
    - id: docs
      label: Documentation Contributor
      paths:
        - "docs/**"
        - "*.md"
        - ".github/**"
    - id: quality
      label: Quality Contributor
      paths:
        - "tests/**"
  default:
    id: code
    label: Code Contributor
  combinations:
    - id: project
      label: Project Contributor
      when: [docs, quality, code]
  multi_category_resolution: priority

identity_map:
  - login: smorin
    emails:
      - steve.morin@gmail.com
```

- [ ] **Step 3: Write `CONTRIBUTORS.md`**

```markdown
# Contributors

Thanks to everyone who has contributed to mockcast!

<!-- contributors-please:start -->
<!-- contributors-please:end -->
```

- [ ] **Step 4: Validate workflow lint + YAML parse**

Run:
```bash
actionlint .github/workflows/update-contributors.yml \
  && uv run python -c "import yaml; yaml.safe_load(open('.contributors.yml'))" \
  && echo OK
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/update-contributors.yml .contributors.yml CONTRIBUTORS.md
git commit -m "ci: add contributors-please automation"
```

---

## Task 6 🤖: seed CHANGELOG

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project are documented here. This file is maintained
by [release-please](https://github.com/googleapis/release-please) from
Conventional Commits.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: seed CHANGELOG for release-please"
```

---

## Task 7 🧑: One-time GitHub + PyPI setup

**Files:** none (repo/registry configuration). Some steps also amend `.contributors.yml`.

- [ ] **Step 1: Create the `testpypi` and `pypi` GitHub Environments**

```bash
cd /Users/stevemorin/c/mockcast
gh api --method PUT repos/smorinlabs/mockcast/environments/testpypi >/dev/null && echo "testpypi env created"
gh api --method PUT repos/smorinlabs/mockcast/environments/pypi >/dev/null && echo "pypi env created"
```
Expected: both print "created". Verify: `gh api repos/smorinlabs/mockcast/environments --jq '.environments[].name'` lists `testpypi` and `pypi`.

- [ ] **Step 2 (recommended): Require a reviewer before publishing to `pypi`**

In the GitHub UI: Settings → Environments → `pypi` → enable **Required reviewers** (add yourself). This makes `publish-pypi` pause for manual approval. (Optional but recommended for a public package.)

- [ ] **Step 3: Point Trusted Publishers at `publish.yml`**

On **PyPI** (pypi.org → project `mockcast` → Settings → Publishing) add/confirm a GitHub Actions trusted publisher:
- Repository: `smorinlabs/mockcast`
- Workflow filename: `publish.yml`
- Environment: `pypi`

On **TestPyPI** (test.pypi.org), same with Environment: `testpypi`.

(Per the agreed decision the trusted publishers point at `publish.yml`, not `release.yml`.)

- [ ] **Step 4: Confirm the actual bot login slugs and fix `.contributors.yml` ignore**

```bash
gh api repos/smorinlabs/mockcast/installations --jq '.installations[].app_slug' 2>/dev/null || \
  gh api orgs/smorinlabs/installations --jq '.installations[].app_slug'
```
Compare the printed app slugs to the `ignore:` entries `release-please-smorinlabs[bot]` and `contributors-please[bot]` in `.contributors.yml`. If a slug differs, edit `.contributors.yml` so each bot is `<actual-slug>[bot]`, then:
```bash
git add .contributors.yml
git commit -m "ci: pin contributor bot ignore slugs"
```
(If the slugs already match, skip the commit.)

---

## Task 8 🧑: Open PR, verify gates, merge

- [ ] **Step 1: Push the branch and open the PR**

```bash
git push -u origin ci-automation
gh pr create --title "ci: release-please + publish + contributors automation" \
  --body "Adds release-please, OIDC PyPI publish, commitlint, and contributors automation. See docs/superpowers/specs/2026-06-07-ci-release-contributors-design.md." \
  --base main
```

- [ ] **Step 2: Verify PR checks pass**

```bash
gh pr checks --watch
```
Expected: `commitlint` passes (all branch commits use Conventional types) and the existing `CI` (`ci.yml`) passes. If `commitlint` fails, fix the offending commit message (`git rebase -i` / amend) and force-push.

- [ ] **Step 3: Merge the PR**

```bash
gh pr merge --squash --delete-branch
```
Note: a squash merge produces ONE commit on `main` — its title must be a valid Conventional Commit (use e.g. `ci: add release-please, publish, commitlint, contributors automation`). After merge, `release-please.yml` and `update-contributors.yml` run on `main`.

- [ ] **Step 4: Verify post-merge workflows ran**

```bash
git checkout main && git pull
gh run list --branch main --limit 5
```
Expected: `release-please` ran. Because every merged commit is `ci:`/`docs:`/`chore:` (hidden / non-releasing types), release-please opens **no** release PR yet — confirmed by `gh pr list` showing no `chore(release):` PR. `update-contributors` may open a PR adding you to `CONTRIBUTORS.md`.

---

## Task 9 🧑: Reconcile and publish `0.1.0` (Open Decision 1)

This both fixes "PyPI only has the `0.0.0.dev0` placeholder" and live-tests `publish.yml`.

- [ ] **Step 1: Re-point the `v0.1.0` tag at current `main` and push it**

```bash
cd /Users/stevemorin/c/mockcast
git checkout main && git pull
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0
git tag -a v0.1.0 -m "mockcast v0.1.0"
git push origin v0.1.0
```
(The tag must sit on a `main` commit and `pyproject` is `0.1.0`, satisfying `publish.yml`'s two guard steps.)

- [ ] **Step 2: Watch the publish run; approve the `pypi` environment if prompted**

```bash
gh run list --workflow publish.yml --limit 1
gh run watch "$(gh run list --workflow publish.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```
If you enabled the required reviewer (Task 7 Step 2), approve the `pypi` deployment in the GitHub UI (Actions → the run → Review deployments) so `publish-pypi` proceeds.

- [ ] **Step 3: Verify `0.1.0` is live on both indexes**

```bash
curl -s https://test.pypi.org/pypi/mockcast/json | jq -r '.info.version'
curl -s https://pypi.org/pypi/mockcast/json     | jq -r '.releases | keys[]'
```
Expected: TestPyPI shows `0.1.0`; PyPI `releases` keys include `0.1.0` (alongside the `0.0.0.dev0` placeholder).

---

## Task 10 🧑: End-to-end acceptance (full release loop)

Proves the automation works for a real change going forward.

- [ ] **Step 1: Land a releasing commit via PR**

```bash
git checkout -b chore/verify-release
# make a small user-visible change, e.g. a README badge tweak or a docs line
git commit -am "fix: tidy README wording"   # 'fix' → triggers a patch release
git push -u origin chore/verify-release
gh pr create --fill --base main
gh pr checks --watch        # commitlint + ci must pass
gh pr merge --squash --delete-branch   # squash title must stay Conventional, e.g. "fix: tidy README wording"
```

- [ ] **Step 2: Verify release-please opens a release PR**

```bash
git checkout main && git pull
gh pr list --search "chore(release):"
```
Expected: a `chore(release): release 0.1.1` PR exists, with `pyproject.toml` bumped to `0.1.1`, `CHANGELOG.md` updated, and (after the `sync-uv-lock` job) `uv.lock` synced.

- [ ] **Step 3: Merge the release PR → tag → publish**

```bash
gh pr merge <release-pr-number> --squash
```
Expected: release-please pushes tag `v0.1.1` and creates a GitHub Release; `publish.yml` fires on the tag and publishes `0.1.1` to TestPyPI then PyPI (approve `pypi` env if gated). Verify:
```bash
curl -s https://pypi.org/pypi/mockcast/json | jq -r '.releases | keys[]'
```
Expected: includes `0.1.1`.

- [ ] **Step 4: Verify contributors automation**

```bash
gh pr list --search "contributors"
```
Expected: an `update-contributors` PR exists (or merged) populating the marker block in `CONTRIBUTORS.md` with the `smorin` entry. Merging it does not loop (guarded by `paths-ignore`).

---

## Acceptance criteria (from spec)

- All four new workflows pass `actionlint`; JSON parses; `commitlint.config.mjs` passes `node --check`.
- A non-Conventional PR commit fails `commitlint`; Conventional commits pass.
- A `feat:`/`fix:` merged to `main` produces a release PR with correct bump + changelog; merging it tags `v*` and publishes to TestPyPI then PyPI via OIDC (no stored tokens).
- `0.1.0` is reconciled onto PyPI (Task 9).
- `update-contributors` opens a loop-safe PR maintaining `CONTRIBUTORS.md`.
- Existing `ci.yml` and the 26 tests stay green throughout.

## Notes / risks

- **Action version pins** (`@v4`/`@v5`/`@v6`/`@v3`/`@v1.0.6`) were normalized to real current majors; `actionlint` in Tasks 2–5 catches typos, but a pin that 404s only surfaces at run time — if a step errors with "action not found," check the tag exists.
- **Squash-merge titles must be Conventional** — release-please reads the commit that lands on `main`. A non-conventional squash title silently produces no release.
- **contributors-please PAT** (Open Decision 2): this plan uses App-pair auth only. If `smorinlabs/contributors-please-action@v1.0.6` errors requiring a `pat`, add a `CONTRIBUTORS_PLEASE_PAT` secret and the `pat:` input.
