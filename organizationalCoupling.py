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
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

    def verify_connection(self) -> Tuple[str, int, int]:
        """Return information about the authenticated GitHub session.

        The method performs lightweight API calls to make sure the
        provided token is valid and that we can reach the GitHub REST
        API.  It returns the authenticated login along with the current
        core rate-limit information so callers can log helpful status
        messages before attempting the expensive crawling steps.
        """

        session = _create_session(self)
        user_response = _github_request(
            session,
            "https://api.github.com/user",
            params=None,
            max_retries=self.max_retries,
            sleep_seconds=self.sleep_seconds,
        )
        login = user_response.json().get("login", "<unknown>")

        rate_response = _github_request(
            session,
            "https://api.github.com/rate_limit",
            params=None,
            max_retries=self.max_retries,
            sleep_seconds=self.sleep_seconds,
        )
        core_limits = rate_response.json().get("resources", {}).get("core", {})
        remaining = int(core_limits.get("remaining", 0))
        limit = int(core_limits.get("limit", 0))
        return login, remaining, limit

    @classmethod
    def from_env(cls) -> "GithubConfig":
        token = os.getenv("MY_PAT")
        if not token:
            raise MissingGithubTokenError(
                "A GitHub personal access token must be provided via the "
                "MY_PAT environment variable."
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


def _format_github_date(date_str: str, *, is_end: bool) -> str:
    """Convert a ``YYYY-MM-DD`` string into an ISO-8601 timestamp in UTC."""

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if is_end:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def getCommitTablebyProject(
    projectfullname: str,
    updateissuetablename: str | Path,
    *,
    config: Optional[GithubConfig] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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
        configuration is built from the ``MY_PAT`` environment
        variable.
    start_date:
        Optional lower bound (inclusive) on commit author dates in
        ``YYYY-MM-DD`` format.
    end_date:
        Optional upper bound (inclusive) on commit author dates in
        ``YYYY-MM-DD`` format.
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
        if start_date:
            params["since"] = _format_github_date(start_date, is_end=False)
        if end_date:
            params["until"] = _format_github_date(end_date, is_end=True)
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


def _coerce_optional_str(value: Any) -> Optional[str]:
    """Return ``value`` as a string when possible.

    The service mapping CSVs occasionally contain numeric columns which Pandas
    will load as ``float`` objects.  The pipeline expects textual values for the
    project, service name, and path prefix columns, so we coerce them to
    strings while gracefully handling missing data.  Returning ``None`` allows
    callers to decide how to treat absent values.
    """

    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return str(value)


def _load_service_mapping(path: str | Path) -> Dict[str, List[Tuple[str, str]]]:
    df = pd.read_csv(path)
    mapping: Dict[str, List[Tuple[str, str]]] = {}
    for row in df.itertuples(index=False):
        project = _coerce_optional_str(getattr(row, "project"))
        service_name = _coerce_optional_str(getattr(row, "service_name"))
        if project is None or service_name is None:
            # Skip rows missing the required identifiers.
            continue
        path_prefix = _coerce_optional_str(getattr(row, "path_prefix", "")) or ""
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


def _extract_author_identifier(value: Any) -> Optional[str]:
    email = _coerce_optional_str(value)
    if not email:
        return None
    if "@" in email:
        return email.split("@", 1)[0]
    return email


def _prepare_coupling_dataframe(
    commit_df: pd.DataFrame,
    *,
    project: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    df = commit_df.copy()
    df["author_date"] = pd.to_datetime(df["author_date"], errors="coerce", utc=True)
    df = df.loc[
        (df["project"] == project)
        & df["service"].notna()
        & (df["author_date"] >= start)
        & (df["author_date"] <= end)
    ]

    df = df.copy()
    df["author"] = df["author_email"].apply(_extract_author_identifier)
    df = df.loc[df["author"].notna()]

    additions = pd.to_numeric(df.get("additions"), errors="coerce").fillna(0.0)
    deletions = pd.to_numeric(df.get("deletions"), errors="coerce").fillna(0.0)
    df["sum"] = additions + deletions

    grouped = (
        df.groupby(["author_date", "commit_sha", "author", "service"], dropna=False)["sum"]
        .sum()
        .reset_index()
    )
    return grouped.sort_values(["author", "author_date", "commit_sha"])


def _compute_service_coupling(grouped: pd.DataFrame, service_a: str, service_b: str) -> float:
    if service_a == service_b:
        return 0.0

    relevant = grouped[grouped["service"].isin({service_a, service_b})]
    if relevant.empty:
        return 0.0

    authors_a = set(relevant.loc[relevant["service"] == service_a, "author"])
    authors_b = set(relevant.loc[relevant["service"] == service_b, "author"])
    shared_authors = authors_a & authors_b
    if not shared_authors:
        return 0.0

    coupling_total = 0.0
    for author in shared_authors:
        author_rows = relevant.loc[relevant["author"] == author]
        author_rows = author_rows.sort_values(["author_date", "commit_sha"])
        sequence = author_rows["service"].tolist()
        if len(sequence) <= 1:
            continue

        switch_count = sum(1 for i in range(len(sequence) - 1) if sequence[i] != sequence[i + 1])
        if switch_count == 0:
            continue

        weight_denominator = (len(sequence) - 1) * 2
        if weight_denominator <= 0:
            continue
        weight = switch_count / weight_denominator

        contrib_a = author_rows.loc[author_rows["service"] == service_a, "sum"].sum()
        contrib_b = author_rows.loc[author_rows["service"] == service_b, "sum"].sum()
        if contrib_a <= 0 or contrib_b <= 0:
            continue

        coupling_total += (2 * contrib_a * contrib_b / (contrib_a + contrib_b)) * weight

    return float(coupling_total)


def makeHeatmapdatasetBetweenDate(
    project: str,
    commit_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    output_path: str | Path,
) -> Path:
    start = pd.to_datetime(start_date, utc=True)
    end = pd.to_datetime(end_date, utc=True)
    grouped = _prepare_coupling_dataframe(
        commit_df, project=project, start=start, end=end
    )

    services = sorted(grouped["service"].unique())
    heatmap = pd.DataFrame(0.0, index=services, columns=services, dtype=float)

    for i, service_a in enumerate(services):
        for j, service_b in enumerate(services[i:], start=i):
            coupling = _compute_service_coupling(grouped, service_a, service_b)
            heatmap.loc[service_a, service_b] = coupling
            heatmap.loc[service_b, service_a] = coupling

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
