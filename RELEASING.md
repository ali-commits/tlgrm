# Releasing tlgrm

tlgrm bundles a **fallback** Telegram `api_id`/`api_hash` so it works out of the box
when a user hasn't set their own `TG_API_ID`/`TG_API_HASH`. The fallback is **injected
at build time** — it never lives in the source tree or git history. The committed
`src/tlgrm/config.py` always has an empty placeholder (`_q = ""`).

## How it works

- `release.sh` reads `TG_API_ID` / `TG_API_HASH` from the environment, turns them into
  the obfuscated blob the runtime decoder expects, writes it into `config.py`, builds the
  wheel + sdist, then reverts `config.py`. The blob is never printed.
- The GitHub Actions workflow `.github/workflows/release.yml` runs this automatically when
  you **publish a GitHub Release**, pulling the credentials from repo secrets, then
  publishes to PyPI.

## One-time setup

### 1. Add the credentials as repository secrets

```bash
gh secret set TG_API_ID --body 31193026
gh secret set TG_API_HASH            # prompts; paste your api_hash
```

These live encrypted in GitHub's secret store, are masked in logs, and are unavailable to
fork pull requests.

### 2. Choose how to authenticate to PyPI (pick one)

**Option A — Trusted Publishing (recommended, no token to manage):**
On <https://pypi.org>, open the project (or "pending publisher" for a new project) →
**Publishing** → add a GitHub trusted publisher:
- Repository: `ali-commits/tlgrm`
- Workflow filename: `release.yml`
- Environment: `pypi`

Nothing else to store — the workflow authenticates via OIDC.

**Option B — API token:**
Create a PyPI API token (scoped to the project) and store it:

```bash
gh secret set PYPI_API_TOKEN         # prompts; paste the pypi-… token
```

The workflow auto-detects this: if `PYPI_API_TOKEN` is set it uses the token; otherwise it
falls back to Trusted Publishing.

## Versioning

The version is derived automatically from the **git tag** by `hatch-vcs` — there is no
version number to edit in the source. The tag you choose for the release *is* the version:
`v0.2.0` → `0.2.0`. (`src/tlgrm/__init__.py` reads it back from the installed package
metadata at runtime.)

## Cutting a release

Pick the next version yourself and create the GitHub Release with that tag — that's the
only manual step, and it triggers the workflow:

```bash
gh release create v0.2.0 --generate-notes
```

The workflow reads the version from the tag, injects the credentials, builds, and publishes
to PyPI (PyPI rejects re-uploading an existing version, so always use a new tag). Watch it:

```bash
gh run watch
```

## Building locally (optional)

To produce an injected build on your own machine (e.g. to inspect the wheel):

```bash
TG_API_ID=31193026 TG_API_HASH=your_hash bash release.sh
# wheel + sdist land in dist/; config.py is reverted automatically
twine upload dist/*        # if publishing manually
```

## Security notes

- The bundled credential is **obfuscation, not encryption** — it defeats automated
  scrapers and GitHub secret scanning, but anyone who `pip download`s the wheel can recover
  it. It is the *application* identity (it cannot access any user's account).
- The secret stays in GitHub's secret vault; it is never committed and never echoed to logs.
- If you ever suspect the bundled `api_id` is being abused, rotate it at
  <https://my.telegram.org> and cut a new release.
