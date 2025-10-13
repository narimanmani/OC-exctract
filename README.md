# Organizational Coupling Extraction

This repository contains a reproducible pipeline for crawling GitHub repositories and computing Organizational Coupling (OC) metrics. The current configuration focuses on the [`spinnaker/spinnaker`](https://github.com/spinnaker/spinnaker) project and follows the workflow described in the user instructions.

## Prerequisites

1. **Python** 3.9 or newer.
2. A GitHub personal access token (PAT) with `repo` scope stored in the `MY_PAT` environment variable. The pipeline will refuse to run without it.

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

## Repository Inputs

* `OldData/filtered_lang_perc.csv` – list of repositories to process.
* `EsoccExt/service_mapping.csv` – mapping between repository file path prefixes and service names.

## Running the Pipeline Locally

```bash
export MY_PAT=ghp_your_token_here
python run_oc_pipeline.py \
  --repo-list OldData/filtered_lang_perc.csv \
  --service-mapping EsoccExt/service_mapping.csv \
  --start-date 2023-01-01 \
  --end-date 2023-06-30 \
  --output-dir artifacts
```

The script produces:

* Raw commit listings in `artifacts/commits/`.
* File-level commit data in `artifacts/commits_full/`.
* Commit/service mappings in `artifacts/commits_with_services/`.
* Heatmap CSVs in `artifacts/heatmaps/`.
* `artifacts/oc_summary.csv` with the overall OC value for each repository (matching the legacy notebook formula).
* `artifacts/oc_weekly_summary.csv` with weekly OC values computed from the same heatmaps.
* `artifacts/oc_commit_summary.csv` with per-commit OC values for additional granularity.

## GitHub Actions Workflow

The workflow defined in `.github/workflows/run-oc-pipeline.yml` can be triggered manually (`workflow_dispatch`). It requires a repository secret named `MY_PAT` containing the PAT described above. The workflow uploads the generated OC artifacts for inspection.

To run it:

1. Add the secret `MY_PAT` in the repository settings. You can either store it as a regular repository secret or attach it to a GitHub environment (the workflow defaults to an environment named `OC`).
2. Trigger the **Run OC Pipeline** workflow from the *Actions* tab. If you are using a differently named environment, supply it via the `environment_name` input when starting the workflow.

## Notes

* The GitHub API is rate limited. The crawler automatically retries when it encounters rate limit responses and sleeps for a short duration between requests.
* The provided service mapping covers the major Spinnaker services. Update `EsoccExt/service_mapping.csv` to refine the mapping for your analysis.
