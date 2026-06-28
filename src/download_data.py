"""Create source inventory and download or stage raw source files.

Examples:
    python src/download_data.py --inventory-only
    python src/download_data.py --source us_drought_monitor_ohio_county_52w
    python src/download_data.py --source epa_echo_sdwis --include-large
"""

from __future__ import annotations

import argparse
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from utils import REPO_ROOT, ensure_directories, list_to_pipe, load_yaml, read_csv_if_exists, write_csv

SOURCE_INVENTORY_FIELDS = [
    "source_name",
    "agency",
    "dataset_description",
    "grain",
    "geographic_level",
    "refresh_frequency",
    "key_fields",
    "known_limitations",
    "local_raw_path",
    "processed_output_path",
    "ingestion_method",
    "size_class",
    "landing_page_url",
    "documentation_url",
]

MANIFEST_FIELDS = [
    "source_name",
    "retrieval_date_utc",
    "status",
    "file_size_bytes",
    "local_path",
    "source_url",
    "notes",
]


def mdy(value: date) -> str:
    """Return M/D/YYYY date text expected by the U.S. Drought Monitor API."""
    return f"{value.month}/{value.day}/{value.year}"


def load_sources_config() -> dict:
    return load_yaml(REPO_ROOT / "config" / "sources.yaml")


def build_source_inventory(config: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in config.get("sources", []):
        rows.append(
            {
                "source_name": source.get("source_name", ""),
                "agency": source.get("agency", ""),
                "dataset_description": source.get("dataset_description", ""),
                "grain": source.get("grain", ""),
                "geographic_level": source.get("geographic_level", ""),
                "refresh_frequency": source.get("refresh_frequency", ""),
                "key_fields": list_to_pipe(source.get("key_fields", [])),
                "known_limitations": source.get("known_limitations", ""),
                "local_raw_path": source.get("local_raw_path", ""),
                "processed_output_path": source.get("processed_output_path", ""),
                "ingestion_method": source.get("ingestion_method", ""),
                "size_class": source.get("size_class", ""),
                "landing_page_url": source.get("landing_page_url", ""),
                "documentation_url": source.get("documentation_url", ""),
            }
        )
    return rows


def write_source_inventory(config: dict) -> Path:
    output_path = REPO_ROOT / config["project"]["source_inventory_output"]
    rows = build_source_inventory(config)
    write_csv(rows, output_path, SOURCE_INVENTORY_FIELDS)
    print(f"Wrote source inventory: {output_path} ({len(rows)} sources)")
    return output_path


def render_source_url(source: dict, lookback_days: int) -> str:
    url = source.get("direct_download_url") or ""
    if source.get("ingestion_method") != "parameterized_download":
        return url
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    return url.format(start_date_mdy=mdy(start_date), end_date_mdy=mdy(end_date))


def manifest_row(source: dict, status: str, source_url: str = "", notes: str = "") -> dict[str, str]:
    local_path = REPO_ROOT / source.get("local_raw_path", "")
    file_size = local_path.stat().st_size if local_path.exists() and local_path.is_file() else 0
    return {
        "source_name": source.get("source_name", ""),
        "retrieval_date_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "file_size_bytes": str(file_size),
        "local_path": str(local_path),
        "source_url": source_url,
        "notes": notes,
    }


def write_manifest(config: dict, rows: list[dict[str, str]], append: bool = True) -> Path:
    manifest_path = REPO_ROOT / config["project"]["manifest_output"]
    existing_rows = read_csv_if_exists(manifest_path) if append else []
    write_csv(existing_rows + rows, manifest_path, MANIFEST_FIELDS)
    print(f"Wrote data source manifest: {manifest_path} ({len(existing_rows) + len(rows)} rows)")
    return manifest_path


def snapshot_manifest(config: dict, lookback_days: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in config.get("sources", []):
        local_path = REPO_ROOT / source.get("local_raw_path", "")
        source_url = render_source_url(source, lookback_days)
        if local_path.exists():
            status = "available"
            notes = "Raw file is present locally."
        elif source.get("ingestion_method") == "manual":
            status = "manual_required"
            notes = "Manual staging required before this source can be loaded."
        else:
            status = "not_downloaded"
            notes = "Direct download source has not been downloaded yet."
        rows.append(manifest_row(source, status=status, source_url=source_url, notes=notes))
    return rows


def should_skip_large(source: dict, include_large: bool) -> bool:
    return source.get("size_class") == "large" and not include_large


def download_source(source: dict, force: bool, include_large: bool, lookback_days: int) -> dict[str, str]:
    source_name = source.get("source_name", "")
    method = source.get("ingestion_method", "")
    local_path = REPO_ROOT / source.get("local_raw_path", "")
    source_url = render_source_url(source, lookback_days)

    if method == "manual":
        status = "manual_available" if local_path.exists() else "manual_required"
        notes = (
            "Manual source found locally."
            if local_path.exists()
            else "Download from landing page and place at local_raw_path."
        )
        print(f"{source_name}: {status}")
        return manifest_row(source, status=status, source_url=source_url, notes=notes)

    if method not in {"direct_download", "parameterized_download"}:
        print(f"{source_name}: skipped_unknown_method")
        return manifest_row(
            source, status="skipped_unknown_method", source_url=source_url, notes=f"Unsupported method: {method}"
        )

    if should_skip_large(source, include_large):
        print(f"{source_name}: skipped_large")
        return manifest_row(
            source, status="skipped_large", source_url=source_url, notes="Use --include-large to download this source."
        )

    if not source_url:
        print(f"{source_name}: missing_url")
        return manifest_row(
            source, status="missing_url", source_url=source_url, notes="No direct_download_url configured."
        )

    if local_path.exists() and not force:
        print(f"{source_name}: exists")
        return manifest_row(
            source,
            status="exists",
            source_url=source_url,
            notes="Existing raw file preserved. Use --force to overwrite.",
        )

    local_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = local_path.with_suffix(local_path.suffix + ".download")
    print(f"{source_name}: downloading {source_url}")

    with requests.get(source_url, stream=True, timeout=120) as response:
        response.raise_for_status()
        response.raw.decode_content = True
        with temp_path.open("wb") as file:
            shutil.copyfileobj(response.raw, file)

    temp_path.replace(local_path)
    parsed = urlparse(source_url)
    notes = f"Downloaded from {parsed.netloc}."
    print(f"{source_name}: downloaded {local_path} ({local_path.stat().st_size} bytes)")
    return manifest_row(source, status="downloaded", source_url=source_url, notes=notes)


def select_sources(config: dict, selected_names: list[str] | None, all_sources: bool) -> list[dict]:
    sources = config.get("sources", [])
    if all_sources:
        return sources
    if not selected_names:
        return []
    by_name = {source["source_name"]: source for source in sources}
    missing = sorted(set(selected_names) - set(by_name))
    if missing:
        raise SystemExit(f"Unknown source(s): {', '.join(missing)}")
    return [by_name[name] for name in selected_names]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source inventory and download/stage raw public data.")
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Create folders, inventory, and manifest snapshot without downloading.",
    )
    parser.add_argument("--source", action="append", help="Source name to process. Can be provided more than once.")
    parser.add_argument(
        "--all", action="store_true", help="Process every configured source. Large files still require --include-large."
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing raw files.")
    parser.add_argument(
        "--include-large", action="store_true", help="Allow large configured downloads such as the national SDWA zip."
    )
    parser.add_argument(
        "--lookback-days", type=int, default=365, help="Lookback window for parameterized time-series sources."
    )
    parser.add_argument("--list-sources", action="store_true", help="Print configured source names and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_sources_config()
    ensure_directories(config.get("folders", []))
    write_source_inventory(config)

    if args.list_sources:
        for source in config.get("sources", []):
            print(f"{source['source_name']} ({source.get('ingestion_method')}, {source.get('size_class')})")
        return

    if args.inventory_only or (not args.source and not args.all):
        rows = snapshot_manifest(config, args.lookback_days)
        write_manifest(config, rows, append=False)
        return

    selected_sources = select_sources(config, args.source, args.all)
    manifest_rows = [
        download_source(source, force=args.force, include_large=args.include_large, lookback_days=args.lookback_days)
        for source in selected_sources
    ]
    write_manifest(config, manifest_rows, append=True)


if __name__ == "__main__":
    main()
