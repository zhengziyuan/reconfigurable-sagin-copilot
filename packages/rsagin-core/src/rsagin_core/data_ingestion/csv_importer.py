from __future__ import annotations

import csv
import io
import json
from typing import Any


SUPPORTED_KINDS = {"nodes", "candidate_sites", "demand", "region", "measurement"}


def preview_import(kind: str, content: str, *, filename: str = "upload") -> dict[str, Any]:
    kind = kind if kind in SUPPORTED_KINDS else "measurement"
    parsed = _parse_content(content, filename)
    rows = parsed["rows"]
    quality = validate_rows(kind, rows)
    return {
        "kind": kind,
        "filename": filename,
        "format": parsed["format"],
        "row_count": len(rows),
        "columns": parsed["columns"],
        "preview_rows": rows[:12],
        "quality": quality,
        "normalized": normalize_rows(kind, rows),
    }


def normalize_rows(kind: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if kind in {"nodes", "candidate_sites"}:
            normalized.append(
                {
                    "id": str(row.get("id") or row.get("name") or f"imported_{kind}_{index + 1:03d}"),
                    "type": str(row.get("type") or row.get("node_type") or "ground_station"),
                    "position": {
                        "lat": _float(row.get("lat") or row.get("latitude")),
                        "lon": _float(row.get("lon") or row.get("lng") or row.get("longitude")),
                        "alt_m": _float(row.get("alt_m") or row.get("height_m") or row.get("altitude"), 0.0),
                    },
                    "cost": _float(row.get("cost"), 0.0),
                    "enabled": _bool(row.get("enabled"), True),
                    "source": "import",
                }
            )
        elif kind == "demand":
            normalized.append(
                {
                    "cell_id": str(row.get("cell_id") or f"demand_{index + 1:03d}"),
                    "lat": _float(row.get("lat") or row.get("latitude")),
                    "lon": _float(row.get("lon") or row.get("longitude")),
                    "demand_weight": _float(row.get("demand_weight") or row.get("weight"), 1.0),
                }
            )
        else:
            normalized.append(row)
    return normalized


def validate_rows(kind: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        errors.append("文件为空或无法解析。")
    required = ["lat", "lon"] if kind in {"nodes", "candidate_sites", "demand"} else []
    for column in required:
        if not any(column in row or ("latitude" if column == "lat" else "longitude") in row for row in rows):
            errors.append(f"缺少必要列：{column}")
    for index, row in enumerate(rows[:200], start=1):
        lat = _float(row.get("lat") or row.get("latitude"), None)
        lon = _float(row.get("lon") or row.get("longitude"), None)
        if kind in {"nodes", "candidate_sites", "demand"} and (lat is None or lon is None):
            errors.append(f"第 {index} 行缺少经纬度。")
        elif lat is not None and not (-90 <= lat <= 90):
            errors.append(f"第 {index} 行纬度越界。")
        elif lon is not None and not (-180 <= lon <= 180):
            errors.append(f"第 {index} 行经度越界。")
    if len(rows) > 10000:
        warnings.append("行数较大，建议后台异步导入并生成数据质量报告。")
    if kind == "measurement" and rows and not any("time" in row or "timestamp" in row for row in rows):
        warnings.append("测量数据未检测到时间列，无法做时序校准。")
    return {
        "valid": not errors,
        "errors": errors[:20],
        "warnings": warnings,
        "score": max(0.0, round(1.0 - 0.08 * len(errors) - 0.03 * len(warnings), 3)),
    }


def _parse_content(content: str, filename: str) -> dict[str, Any]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    stripped = content.strip()
    if suffix in {"json", "geojson"} or stripped.startswith("{") or stripped.startswith("["):
        payload = json.loads(stripped or "[]")
        rows = _json_rows(payload)
        return {"format": "json" if suffix != "geojson" else "geojson", "rows": rows, "columns": _columns(rows)}
    dialect = csv.Sniffer().sniff(stripped[:2048], delimiters=",;\t") if stripped else csv.excel
    reader = csv.DictReader(io.StringIO(stripped), dialect=dialect)
    rows = [dict(row) for row in reader]
    return {"format": "csv", "rows": rows, "columns": reader.fieldnames or []}


def _json_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if payload.get("type") == "FeatureCollection":
            rows = []
            for feature in payload.get("features", []):
                properties = feature.get("properties", {}) if isinstance(feature, dict) else {}
                geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
                coords = geometry.get("coordinates", [])
                if geometry.get("type") == "Point" and len(coords) >= 2:
                    rows.append({**properties, "lon": coords[0], "lat": coords[1]})
            return rows
        for key in ["rows", "items", "features", "nodes"]:
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "y", "enabled"}
