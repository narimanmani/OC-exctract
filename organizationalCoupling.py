"""Utilities for crawling GitHub repositories and computing Organizational Coupling (OC).

This module implements the helper functions referenced in the
project documentation.  It intentionally keeps the public API very
close to the names used in the historical notebook/worksheet so that
existing instructions remain valid, while providing a much more robust
implementation behind the scenes.
"""
from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


class MissingGithubTokenError(RuntimeError):
    """Raised when the required GitHub token is not configured."""


@dataclass
class GithubConfig:
    token: str
    sleep_seconds: float = 1.0
    max_retries: int = 5

    @classmethod
    def from_env(cls) -> "GithubConfig":
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise MissingGithubTokenError(
                "A GitHub personal access token must be provided via the "
                "GITHUB_TOKEN environment variable."
            )
        return cls(token=token)


def _create_session(config: GithubConfig) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Authorization": f"token {config.token}", "Accept": "application/vnd.github+json"})
    return session


def _github_request(
    session: requests.Session,
    url: str,
    *,
    params: Optional[Dict[str, int]] = None,
    max_retries: int,
    sleep_seconds: float,
) -> requests.Response:
    backoff = sleep_seconds
    for attempt in range(max_retries):
        response = session.get(url, params=params, timeout=60)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            reset_at = response.headers.get("X-RateLimit-Reset")
            if reset_at is not None:
                sleep_for = max(int(reset_at) - int(time.time()), 0) + 1
            else:
                sleep_for = max(backoff, 1.0)
            time.sleep(sleep_for)
            backoff *= 2
            continue
        if response.status_code >= 500:
            time.sleep(backoff)
            backoff *= 2
            continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


def getCommitTablebyProject(
    projectfullname: str,
    updateissuetablename: str | Path,
    *,
    config: Optional[GithubConfig] = None,
) -> Path:
    """Fetch the list of commits for a project.

    Parameters
    ----------
    projectfullname:
        The repository in ``org/name`` format.
    updateissuetablename:
        Location of the CSV file that will be written.
    config:
        Optional :class:`GithubConfig` instance.  When omitted the
        configuration is built from the ``GITHUB_TOKEN`` environment
        variable.
    """

    cfg = config or GithubConfig.from_env()
    session = _create_session(cfg)
    output_path = Path(updateissuetablename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    commit_features = ["project_id", "commit_sha", "author_email", "author_date"]
    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(commit_features)

        params = {"per_page": 100, "page": 1}
        project_url = f"https://api.github.com/repos/{projectfullname}"
        project_info = _github_request(
            session, project_url, max_retries=cfg.max_retries, sleep_seconds=cfg.sleep_seconds
        ).json()
        project_id = project_info["id"]

        while True:
            response = _github_request(
                session,
                f"{project_url}/commits",
                params=params,
                max_retries=cfg.max_retries,
                sleep_seconds=cfg.sleep_seconds,
            )
            items = response.json()
            if not items:
                break
            for item in items:
                commit_sha = item["sha"]
                author = item.get("commit", {}).get("author", {})
                writer.writerow(
                    [
                        project_id,
                        commit_sha,
                        author.get("email"),
                        author.get("date"),
                    ]
                )
            params["page"] += 1
            time.sleep(cfg.sleep_seconds)

    return output_path


def furtherCrawlCommits(
    commitsdf: pd.DataFrame,
    projectfullname: str,
    newupdateissuetablename: str | Path,
    *,
    config: Optional[GithubConfig] = None,
) -> Path:
    """Fetch file-level data for every commit returned by :func:`getCommitTablebyProject`."""

    cfg = config or GithubConfig.from_env()
    session = _create_session(cfg)
    output_path = Path(newupdateissuetablename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    commit_features = [
        "project",
        "commit_sha",
        "author_email",
        "author_date",
        "file_sha",
        "filename",
        "status",
        "additions",
        "deletions",
        "patch",
        "previous_filename",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(commit_features)

        for row in commitsdf.itertuples(index=False):
            sha = getattr(row, "commit_sha")
            commit_url = f"https://api.github.com/repos/{projectfullname}/commits/{sha}"
            response = _github_request(
                session, commit_url, max_retries=cfg.max_retries, sleep_seconds=cfg.sleep_seconds
            )
            commit_info = response.json()
            author = commit_info.get("commit", {}).get("author", {})
            files = commit_info.get("files", [])
            if not files:
                writer.writerow(
                    [
                        projectfullname,
                        sha,
                        author.get("email"),
                        author.get("date"),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ]
                )
            else:
                for file_info in files:
                    writer.writerow(
                        [
                            projectfullname,
                            sha,
                            author.get("email"),
                            author.get("date"),
                            file_info.get("sha"),
                            file_info.get("filename"),
                            file_info.get("status"),
                            file_info.get("additions"),
                            file_info.get("deletions"),
                            file_info.get("patch"),
                            file_info.get("previous_filename"),
                        ]
                    )
            time.sleep(cfg.sleep_seconds)

    return output_path


def _load_service_mapping(path: str | Path) -> Dict[str, List[Tuple[str, str]]]:
    df = pd.read_csv(path)
    mapping: Dict[str, List[Tuple[str, str]]] = {}
    for row in df.itertuples(index=False):
        project = getattr(row, "project")
        service_name = getattr(row, "service_name")
        path_prefix = getattr(row, "path_prefix", "") or ""
        mapping.setdefault(project, []).append((path_prefix, service_name))
    # Sort prefixes so that longer (more specific) prefixes are matched first.
    for project, entries in mapping.items():
        entries.sort(key=lambda entry: len(entry[0]), reverse=True)
    return mapping


def _assign_service(filename: str, mapping: List[Tuple[str, str]]) -> Optional[str]:
    for prefix, service in mapping:
        if prefix and filename.startswith(prefix):
            return service
    # Fallback to the first entry with an empty prefix (default bucket)
    for prefix, service in mapping:
        if not prefix:
            return service
    return None


def map_files_to_services(
    commit_details: pd.DataFrame,
    service_mapping_path: str | Path,
    output_path: str | Path,
) -> Path:
    mapping = _load_service_mapping(service_mapping_path)
    commit_details = commit_details.copy()
    services: List[Optional[str]] = []
    for row in commit_details.itertuples(index=False):
        project = getattr(row, "project")
        filename = getattr(row, "filename", None)
        if filename is None or (isinstance(filename, float) and pd.isna(filename)):
            services.append(None)
            continue
        if project not in mapping:
            services.append(None)
            continue
        services.append(_assign_service(str(filename), mapping[project]))
    commit_details["service"] = services
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    commit_details.to_csv(output, index=False)
    return output


def makeHeatmapdatasetBetweenDate(
    project: str,
    commit_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    output_path: str | Path,
) -> Path:
    df = commit_df.copy()
    df["author_date"] = pd.to_datetime(df["author_date"], errors="coerce", utc=True)
    start = pd.to_datetime(start_date, utc=True)
    end = pd.to_datetime(end_date, utc=True)
    mask = (
        (df["project"] == project)
        & (df["author_date"] >= start)
        & (df["author_date"] <= end)
        & df["service"].notna()
    )
    df = df.loc[mask, ["commit_sha", "service"]]

    services = sorted(df["service"].unique())
    heatmap = pd.DataFrame(0, index=services, columns=services, dtype=int)

    for commit_sha, group in df.groupby("commit_sha"):
        service_set = sorted(set(group["service"]))
        if not service_set:
            continue
        for service in service_set:
            heatmap.loc[service, service] += 1
        for i, service_a in enumerate(service_set):
            for service_b in service_set[i + 1 :]:
                heatmap.loc[service_a, service_b] += 1
                heatmap.loc[service_b, service_a] += 1

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    heatmap.to_csv(output)
    return output


def compute_oc_from_heatmap(heatmap: pd.DataFrame) -> float:
    if heatmap.empty:
        return 0.0
    if heatmap.shape[0] <= 1:
        return 0.0
    mask = np.triu(np.ones(heatmap.shape, dtype=bool), k=1)
    upper_triangle = heatmap.where(mask)
    total = upper_triangle.sum().sum()
    n = heatmap.shape[0]
    return float(total) / (n * (n - 1) / 2)


def compute_oc_value(heatmap_path: str | Path) -> float:
    try:
        heatmap = pd.read_csv(heatmap_path, index_col=0)
    except pd.errors.EmptyDataError:
        return 0.0
    return compute_oc_from_heatmap(heatmap)


__all__ = [
    "GithubConfig",
    "MissingGithubTokenError",
    "compute_oc_from_heatmap",
    "compute_oc_value",
    "furtherCrawlCommits",
    "getCommitTablebyProject",
    "makeHeatmapdatasetBetweenDate",
    "map_files_to_services",
]
