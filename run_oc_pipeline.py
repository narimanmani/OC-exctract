"""Command line driver for the Organizational Coupling pipeline."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

import pandas as pd

from organizationalCoupling import (
    GithubConfig,
    MissingGithubTokenError,
    compute_oc_from_heatmap,
    compute_oc_value,
    furtherCrawlCommits,
    getCommitTablebyProject,
    makeHeatmapdatasetBetweenDate,
    map_files_to_services,
    normalize_service_mapping,
)


UNMAPPED_SERVICE = "__unmapped__"


def _normalize_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if value is None or pd.isna(value):
        return None
    return str(value)


def _developer_identifier(row: pd.Series) -> str | None:
    for field in ("author_email", "author_login", "author_name"):
        resolved = _normalize_optional_str(row.get(field))
        if resolved:
            return resolved
    return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown-service"


def _derive_service_name(prefix: str) -> str:
    parts = [part for part in prefix.strip("/").split("/") if part]
    return parts[-1] if parts else "unscoped-service"


def write_service_mapping_used(service_mapping_path: str | Path, output_path: str | Path) -> Path:
    mapping_df = normalize_service_mapping(service_mapping_path)
    records: List[Dict[str, str]] = []
    for row in mapping_df.itertuples(index=False):
        prefix = _normalize_optional_str(getattr(row, "path_prefix", "")) or ""
        service_name = _normalize_optional_str(getattr(row, "service_name")) or _derive_service_name(prefix)
        service_id = _normalize_optional_str(getattr(row, "service_id", None)) or _slugify(service_name)
        records.append(
            {
                "service_id": service_id,
                "service_name": service_name,
                "root_path_prefix": prefix,
            }
        )

    service_mapping_used_df = pd.DataFrame(records).drop_duplicates()
    service_mapping_used_df["_prefix_len"] = service_mapping_used_df["root_path_prefix"].map(len)
    service_mapping_used_df = service_mapping_used_df.sort_values(
        ["_prefix_len", "root_path_prefix", "service_name", "service_id"],
        ascending=[False, True, True, True],
    ).drop(columns=["_prefix_len"])

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    service_mapping_used_df.to_csv(out_path, index=False)
    return out_path


def compute_weekly_sociotechnical_metrics(
    commit_service_df: pd.DataFrame,
    *,
    project: str,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
) -> Dict[str, float]:
    df = commit_service_df.copy()
    df["author_date"] = pd.to_datetime(df["author_date"], errors="coerce", utc=True)
    df = df.loc[df["project"] == project]
    df = df.loc[df["author_date"].between(week_start, week_end, inclusive="both")]

    if df.empty:
        return {
            "active_devs": 0,
            "cross_service_devs": 0,
            "avg_services_per_dev": 0.0,
            "switch_count_total": 0,
        }

    commit_identity = (
        df.sort_values(["commit_sha", "author_date"])
        .drop_duplicates(subset=["commit_sha"], keep="first")
        .copy()
    )
    commit_identity["developer"] = commit_identity.apply(_developer_identifier, axis=1)
    active_devs = int(commit_identity["developer"].dropna().nunique())

    mapped_rows = df.loc[
        df["service"].notna()
        & (df["service"] != UNMAPPED_SERVICE)
        & df["filename"].notna()
    ].copy()
    if mapped_rows.empty:
        return {
            "active_devs": active_devs,
            "cross_service_devs": 0,
            "avg_services_per_dev": 0.0,
            "switch_count_total": 0,
        }

    mapped_rows["developer"] = mapped_rows.apply(_developer_identifier, axis=1)
    mapped_rows = mapped_rows.loc[mapped_rows["developer"].notna()]

    services_per_dev = mapped_rows.groupby("developer")["service"].nunique()
    cross_service_devs = int((services_per_dev >= 2).sum())
    avg_services_per_dev = float(round(services_per_dev.mean(), 3)) if not services_per_dev.empty else 0.0

    commit_service_counts = (
        mapped_rows.groupby(["developer", "commit_sha", "author_date", "service"])
        .size()
        .rename("file_count")
        .reset_index()
    )
    dominant_services = (
        commit_service_counts.sort_values(
            ["developer", "commit_sha", "author_date", "file_count", "service"],
            ascending=[True, True, True, False, True],
        )
        .drop_duplicates(subset=["developer", "commit_sha"], keep="first")
        .sort_values(["developer", "author_date", "commit_sha"])
    )

    switch_count_total = 0
    for _, developer_commits in dominant_services.groupby("developer"):
        sequence = developer_commits["service"].tolist()
        switch_count_total += sum(
            1
            for idx in range(1, len(sequence))
            if sequence[idx] != sequence[idx - 1]
        )

    return {
        "active_devs": active_devs,
        "cross_service_devs": cross_service_devs,
        "avg_services_per_dev": avg_services_per_dev,
        "switch_count_total": int(switch_count_total),
    }


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

    weekly_results = []
    commit_results = []
    overall_results = []

    for repo in repo_list:
        print(f"Processing repository: {repo}")
        repo_safe = repo.replace("/", "_")

        commit_csv = commits_dir / f"{repo_safe}_commits.csv"
        commit_full_csv = commits_full_dir / f"{repo_safe}_commits_full.csv"
        commit_service_csv = commits_service_dir / f"{repo_safe}_commits_with_services.csv"

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

        print("  Computing weekly OC values ...")
        overall_start = pd.to_datetime(args.start_date, utc=True)
        overall_end = pd.to_datetime(args.end_date, utc=True)
        week_start = overall_start
        while week_start <= overall_end:
            week_end = min(week_start + pd.Timedelta(days=6), overall_end)
            week_start_str = week_start.strftime("%Y-%m-%d")
            week_end_str = week_end.strftime("%Y-%m-%d")
            heatmap_csv = heatmap_dir / f"{repo_safe}_heatmap_{week_start_str}_to_{week_end_str}.csv"

            makeHeatmapdatasetBetweenDate(repo, commit_service_df, week_start_str, week_end_str, heatmap_csv)
            oc_value = compute_oc_value(heatmap_csv)
            metrics = compute_weekly_sociotechnical_metrics(
                commit_service_df,
                project=repo,
                week_start=week_start,
                week_end=week_end,
            )
            weekly_results.append(
                {
                    "project": repo,
                    "week_start": week_start_str,
                    "week_end": week_end_str,
                    "oc_value": oc_value,
                    "heatmap": str(heatmap_csv),
                    "active_devs": metrics["active_devs"],
                    "cross_service_devs": metrics["cross_service_devs"],
                    "avg_services_per_dev": metrics["avg_services_per_dev"],
                    "switch_count_total": metrics["switch_count_total"],
                }
            )
            print(
                f"    {week_start_str} to {week_end_str}: OC value {oc_value:.4f}, "
                f"active_devs={metrics['active_devs']}, "
                f"cross_service_devs={metrics['cross_service_devs']}, "
                f"avg_services_per_dev={metrics['avg_services_per_dev']:.3f}, "
                f"switch_count_total={metrics['switch_count_total']}"
            )

            week_start = week_end + pd.Timedelta(days=1)

        print("  Computing per-commit OC values ...")
        repo_commits = commit_service_df.copy()
        repo_commits["author_date"] = pd.to_datetime(
            repo_commits["author_date"], errors="coerce", utc=True
        )
        repo_commits = repo_commits.loc[repo_commits["project"] == repo]

        start = overall_start
        end = overall_end

        repo_commits = repo_commits.loc[
            repo_commits["author_date"].between(start, end, inclusive="both")
            | repo_commits["author_date"].isna()
        ]

        for commit_sha, group in repo_commits.groupby("commit_sha"):
            commit_services = sorted(
                {
                    service
                    for service in group["service"].dropna()
                    if isinstance(service, str) and service.strip() and service != UNMAPPED_SERVICE
                }
            )
            if commit_services:
                heatmap = pd.DataFrame(
                    0, index=commit_services, columns=commit_services, dtype=int
                )
                for service in commit_services:
                    heatmap.loc[service, service] += 1
                for idx, service_a in enumerate(commit_services):
                    for service_b in commit_services[idx + 1 :]:
                        heatmap.loc[service_a, service_b] += 1
                        heatmap.loc[service_b, service_a] += 1
                oc_value = compute_oc_from_heatmap(heatmap)
            else:
                heatmap = pd.DataFrame()
                oc_value = 0.0

            commit_date = group["author_date"].dropna()
            commit_date_str = (
                commit_date.iloc[0].strftime("%Y-%m-%dT%H:%M:%SZ")
                if not commit_date.empty
                else ""
            )

            heatmap_csv = heatmap_dir / f"{repo_safe}_commit_{commit_sha}.csv"
            heatmap.to_csv(heatmap_csv)

            commit_results.append(
                {
                    "project": repo,
                    "commit_sha": commit_sha,
                    "author_date": commit_date_str,
                    "oc_value": oc_value,
                    "heatmap": str(heatmap_csv),
                }
            )
            print(f"    commit {commit_sha}: OC value {oc_value:.4f}")

        print("  Computing overall OC value ...")
        overall_heatmap_csv = heatmap_dir / f"{repo_safe}_heatmap_{args.start_date}_to_{args.end_date}.csv"
        makeHeatmapdatasetBetweenDate(
            repo,
            commit_service_df,
            args.start_date,
            args.end_date,
            overall_heatmap_csv,
        )
        overall_oc_value = compute_oc_value(overall_heatmap_csv)
        overall_results.append(
            {
                "project": repo,
                "start_date": args.start_date,
                "end_date": args.end_date,
                "oc_value": overall_oc_value,
                "heatmap": str(overall_heatmap_csv),
            }
        )
        print(
            "    Overall interval",
            f"{args.start_date} to {args.end_date}: OC value {overall_oc_value:.4f}",
        )

    summary_path = output_dir / "oc_weekly_summary.csv"
    summary_df = pd.DataFrame(
        weekly_results,
        columns=[
            "project",
            "week_start",
            "week_end",
            "oc_value",
            "heatmap",
            "active_devs",
            "cross_service_devs",
            "avg_services_per_dev",
            "switch_count_total",
        ],
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["week_start", "project"], ascending=[True, True])
    summary_df.to_csv(summary_path, index=False)

    mapping_used_path = output_dir / "service_mapping_used.csv"
    write_service_mapping_used(args.service_mapping, mapping_used_path)
    print(f"Service mapping snapshot written to {mapping_used_path}")

    metadata_path = output_dir / "run_metadata.json"
    metadata = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "repo_list_path": args.repo_list,
        "service_mapping_path": args.service_mapping,
        "git_sha": _normalize_optional_str(os.getenv("GITHUB_SHA")) or "unknown",
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Run metadata written to {metadata_path}")

    if summary_path.exists():
        print(
            "Weekly results written to",
            f"{summary_path} ({len(summary_df)} rows)",
        )
        if summary_df.empty:
            print(
                "No weekly OC values were generated. "
                "Check the repository list and date range."
            )
        else:
            preview = summary_df.head(10).copy()
            preview["oc_value"] = preview["oc_value"].map(lambda v: f"{v:.4f}")
            print("Weekly summary preview (first 10 rows):")
            print(preview.to_string(index=False))
            if len(summary_df) > len(preview):
                print(
                    "...",
                    f"({len(summary_df) - len(preview)} additional rows not shown)",
                )
    else:
        print(
            "Warning: Expected weekly summary file was not created at",
            summary_path,
        )

    if commit_results:
        commit_summary_path = output_dir / "oc_commit_summary.csv"
        commit_summary_df = pd.DataFrame(
            commit_results,
            columns=["project", "commit_sha", "author_date", "oc_value", "heatmap"],
        )
        commit_summary_df.to_csv(commit_summary_path, index=False)

        print(
            "Per-commit results written to",
            f"{commit_summary_path} ({len(commit_summary_df)} rows)",
        )
        preview = commit_summary_df.head(10).copy()
        preview["oc_value"] = preview["oc_value"].map(lambda v: f"{v:.4f}")
        print("Per-commit summary preview (first 10 rows):")
        print(preview.to_string(index=False))
        if len(commit_summary_df) > len(preview):
            print(
                "...",
                f"({len(commit_summary_df) - len(preview)} additional rows not shown)",
            )
    else:
        print("No per-commit OC values were generated within the selected range.")

    if overall_results:
        overall_summary_path = output_dir / "oc_summary.csv"
        overall_summary_df = pd.DataFrame(
            overall_results,
            columns=["project", "start_date", "end_date", "oc_value", "heatmap"],
        )
        overall_summary_df.to_csv(overall_summary_path, index=False)

        print(
            "Overall OC results written to",
            f"{overall_summary_path} ({len(overall_summary_df)} rows)",
        )
        preview = overall_summary_df.head(10).copy()
        preview["oc_value"] = preview["oc_value"].map(lambda v: f"{v:.4f}")
        print("Overall summary preview (first 10 rows):")
        print(preview.to_string(index=False))
        if len(overall_summary_df) > len(preview):
            print(
                "...",
                f"({len(overall_summary_df) - len(preview)} additional rows not shown)",
            )
    else:
        print("No overall OC values were generated.")


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
