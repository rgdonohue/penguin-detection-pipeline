# DORA 2025 Integration Notes

Objective: translate the latest DORA guidance into concrete habits for the penguins pipeline so our AI-assisted workflow stays fast **and** stable.

## Key Themes to Anchor On
- **AI accelerates both signal and noise.** Velocity gains only stick if we harden safety nets (tests, provenance, rollbacks). [Google Cloud][1]
- **Seven AI capabilities** act as a checklist for healthy collaboration across humans and agents: policy, data hygiene, access, version control, small batches, user focus, platform strength. [Google Cloud][2]
- **Systems thinking beats tool chasing.** Track the entire value stream from PR → `make golden` → QC report → client readout, then shorten the slowest hops. [Google Cloud][1]
- **DORA metrics remain our compass.** Deployment frequency, lead time, change failure rate, and time to restore prove whether changes help. [Dora][3]

## Collaboration & Workflow Improvements
- **Adopt structured work intake.** Every task (including AI prompts) references the user scenario and definition of done; capture it in PR descriptions and `PLAN.md`.
- **Enforce small batches.** Target PRs that touch a single stage (`scripts/`, `pipelines/`, or `tests/`) and must pass `make golden` + pytest before review.
- **Codify the AI policy.** Extend `CLAUDE.md` / `AGENTS.md` with the shared guardrails (no parameter drift outside `RUNBOOK.md`, provenance notes required, restricted access to `data/legacy_ro/`).
- **Pair reviews across agents and humans.** Require one human approval plus one AI code review when changes originate from an agent; record outcome in PR checklist.

## Technical Practices for Stability
- **Guardrail tests.** Keep `tests/test_golden_aoi.py` as the smoke suite; add assertions for any new artifact (e.g., timing JSON, QC plots). Aim for <5 min local runtime.
- **Runtime transparency.** Preserve the lightweight telemetry already emitted (`timings.json`, `provenance_lidar.json`); publish hashes and counts to `manifests/qc_report.md` after each milestone run.
- **Rollback readiness.** Script `make rollback::<stage>` targets that restore the most recent blessed artifacts from `data/processed/` and document the process in `RUNBOOK.md`.
- **Consistent environments.** Use `requirements.txt` with venv, layer a devcontainer (optional), and add CI that runs lint + `make golden`.

## AI Enablement Actions
- **Centralize context.** Periodically index `PRD.md`, `RUNBOOK.md`, `manifests/`, and QC outputs for retrieval so agents receive accurate parameters.
- **Document decision provenance.** When agents recommend parameter shifts, append a short rationale plus validation evidence to `manifests/qc_report.md` or new ADRs in `notes/`.
- **Human-in-the-loop checkpoints.** For high-impact stages (LiDAR, Thermal), require manual validation of plots/GeoJSON before promoting outputs to `data/processed/`.

## Measuring DORA Metrics
- **Deployment frequency & lead time.** Treat every successful `make golden` run merged to main as a “deployment.” Track start/finish timestamps via PR template fields.
- **Change failure rate.** Log incidents (failed runs, hotfixes) in `manifests/incidents.md` with cause and remediation.
- **Time to restore service.** Capture the interval between incident detection and the next successful `make golden`; automate via a lightweight script that reads incident entries.
- **Reporting cadence.** Add a monthly `notes/delivery-metrics-YYYY-MM.md` summary plotting the Four Keys trends and linking to supporting manifests.

## Immediate Next Steps
- Draft the shared AI policy addendum and merge it into `CLAUDE.md` / `AGENTS.md`.  
- Add PR template checkboxes for: small batch scope, `make golden` result, incident log update, and human validation of QC assets.  
- Create `manifests/incidents.md` and seed it with historical context (if any).  
- Automate capture of `timings.json` and `test_run.json` stats into a `manifests/delivery_metrics.csv`.  
- Schedule a fortnightly 15-minute retro focused on DORA metrics and queued improvements.

[1]: https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report "Announcing the 2025 DORA Report | Google Cloud Blog"
[2]: https://cloud.google.com/blog/products/ai-machine-learning/introducing-doras-inaugural-ai-capabilities-model?utm_source=chatgpt.com "Introducing DORA's inaugural AI Capabilities Model"
[3]: https://dora.dev/guides/dora-metrics-four-keys/?utm_source=chatgpt.com "DORA's software delivery metrics: the four keys"
