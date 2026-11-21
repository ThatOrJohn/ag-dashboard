# 0002: Public repo, served by GitHub Pages and deployed from CI

- **Status:** Accepted
- **Date:** 2026-11-21

## Context
The site is static: a scheduled workflow ingests public data, builds JSON and an Astro site, and tests it.
It needs a host that takes a build artifact from that workflow, costs nothing, and serves a 404 page.

## Decision
The repo is public, and the `deploy` job in `.github/workflows/update.yml` publishes `web/dist` to GitHub
Pages with `actions/upload-pages-artifact` and `actions/deploy-pages`, from `main` only. Pages' source is
"GitHub Actions" (Settings → Pages). The site builds under the repo path, `/ag-dashboard/`; `SITE_URL` and
`SITE_BASE` override `site` and `base` for a custom domain.

## Why
Pages is free for public repos and needs no extra account or token: the workflow's own token deploys.
Only CI has the API keys and the `data` branch, so building in the workflow (not a Pages branch build) is
the only way to produce the site.

## Consequences
- Secrets are only the two data API keys. Pull requests from forks get no secrets and never reach the
  steps that use them; they build and test only.
- GitHub disables scheduled workflows in a public repo after 60 days without repo activity. The deploy job
  re-enables the workflow through the API on every run, which resets that clock.
- Canonical URLs and share images use `site` + `base`, so changing the host is a config change.
