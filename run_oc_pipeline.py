"""Command line driver for the Organizational Coupling pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import requests

import pandas as pd

from organizationalCoupling import (
    GithubConfig,
    MissingGithubTokenError,
    compute_oc_value,
    furtherCrawlCommits,
    getCommitTablebyProject,
    makeHeatmapdatasetBetweenDate,
    map_files_to_services,
)


def _parse_repo(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("Encountered empty repository URL entry")
    if url.endswith(".git"):
        url = url[: -len(".git")]
    if "github.com/" not in url:
        raise ValueError(f"Unsupported repository URL: {url}")
    return url.split("github.com/")[-1]


def load_repo_list(path: Path) -> List[str]:
    df = pd.read_csv(path)
    if "github_url" not in df.columns:
        raise ValueError("`github_url` column not found in repo list")
    return [_parse_repo(url) for url in df["github_url"].dropna().tolist()]


def run_pipeline(args: argparse.Namespace) -> None:
    repo_list = load_repo_list(Path(args.repo_list))
    cfg = GithubConfig.from_env()

    print("Checking GitHub API connectivity ...")
    try:
        login, remaining, limit = cfg.verify_connection()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        reason = exc.response.reason if exc.response is not None else str(exc)
        body = exc.response.text if exc.response is not None else ""
        snippet = " ".join(body.split())[:500]
        raise RuntimeError(
            f"GitHub API connection failed: HTTP {status} {reason}. Response snippet: {snippet}"
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"GitHub API connection failed: {exc}") from exc
    else:
        print(
            "GitHub API connection established.",
            f"Authenticated as '{login}' with {remaining}/{limit} core requests remaining.",
        )

    output_dir = Path(args.output_dir)
    commits_dir = output_dir / "commits"
    commits_full_dir = output_dir / "commits_full"
    commits_service_dir = output_dir / "commits_with_services"
    heatmap_dir = output_dir / "heatmaps"

    commits_dir.mkdir(parents=True, exist_ok=True)
    commits_full_dir.mkdir(parents=True, exist_ok=True)
    commits_service_dir.mkdir(parents=True, exist_ok=True)
    heatmap_dir.mkdir(parents=True, exist_ok=True)

    oc_results = []

    for repo in repo_list:
        print(f"Processing repository: {repo}")
        repo_safe = repo.replace("/", "_")

        commit_csv = commits_dir / f"{repo_safe}_commits.csv"
        commit_full_csv = commits_full_dir / f"{repo_safe}_commits_full.csv"
        commit_service_csv = commits_service_dir / f"{repo_safe}_commits_with_services.csv"
        heatmap_csv = heatmap_dir / f"{repo_safe}_heatmap_{args.start_date}_to_{args.end_date}.csv"

        print("  Fetching commit list ...")
        try:
            getCommitTablebyProject(
                repo,
                commit_csv,
                config=cfg,
                start_date=args.start_date,
                end_date=args.end_date,
            )
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            reason = exc.response.reason if exc.response is not None else str(exc)
            body = exc.response.text if exc.response is not None else ""
            snippet = " ".join(body.split())[:500]
            raise RuntimeError(
                f"Failed to fetch commit list for {repo}: HTTP {status} {reason}. Response snippet: {snippet}"
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch commit list for {repo}: {exc}") from exc
        commit_df = pd.read_csv(commit_csv)

        print("  Fetching commit details ...")
        furtherCrawlCommits(commit_df, repo, commit_full_csv, config=cfg)
        commit_full_df = pd.read_csv(commit_full_csv)

        print("  Mapping files to services ...")
        map_files_to_services(commit_full_df, args.service_mapping, commit_service_csv)
        commit_service_df = pd.read_csv(commit_service_csv)

        print("  Building heatmap ...")
        makeHeatmapdatasetBetweenDate(repo, commit_service_df, args.start_date, args.end_date, heatmap_csv)

        print("  Computing OC value ...")
        oc_value = compute_oc_value(heatmap_csv)
        oc_results.append({
            "project": repo,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "oc_value": oc_value,
            "heatmap": str(heatmap_csv),
        })
        print(f"  OC value: {oc_value:.4f}")

    summary_path = output_dir / "oc_summary.csv"
    pd.DataFrame(oc_results).to_csv(summary_path, index=False)
    print(f"Results written to {summary_path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Organizational Coupling pipeline")
    parser.add_argument("--repo-list", required=True, help="CSV listing repositories to crawl")
    parser.add_argument("--service-mapping", required=True, help="CSV mapping file path prefixes to services")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory where intermediate and final outputs will be stored",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        run_pipeline(args)
    except MissingGithubTokenError as exc:
        print(f"Error: {exc}")
        return 2
    except Exception as exc:  # pragma: no cover - defensive logging for CLI usage
        print(f"Pipeline failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
