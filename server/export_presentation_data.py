from __future__ import annotations

import argparse
import ast
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "server" / "newsletter.sqlite3"
DEFAULT_OUTPUT = PROJECT_ROOT / "exports" / "presentation-data.json"
DATABASE_TABLES = (
    "newsletter_categories",
    "newsletter_category_sources",
    "newsletter_subscriptions",
    "newsletter_delivery_attempts",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export presentation-safe project data as JSON.",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--skip-supabase",
        action="store_true",
        help="Do not request the Supabase todos snapshot.",
    )
    return parser.parse_args()


def evaluate_static_expression(node: ast.AST, environment: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return environment[node.id]
    if isinstance(node, ast.List):
        values: list[Any] = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                values.extend(evaluate_static_expression(element.value, environment))
            else:
                values.append(evaluate_static_expression(element, environment))
        return values
    if isinstance(node, ast.Tuple):
        return tuple(evaluate_static_expression(element, environment) for element in node.elts)
    if isinstance(node, ast.Dict):
        return {
            evaluate_static_expression(key, environment): evaluate_static_expression(value, environment)
            for key, value in zip(node.keys, node.values, strict=True)
        }
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "CatalogEntry":
        fields = ("source_label", "feed_url", "homepage", "keywords", "reason")
        values = {
            field: evaluate_static_expression(argument, environment)
            for field, argument in zip(fields, node.args)
        }
        values.update(
            {
                keyword.arg: evaluate_static_expression(keyword.value, environment)
                for keyword in node.keywords
                if keyword.arg
            }
        )
        if set(values) != set(fields):
            raise ValueError(f"Unexpected CatalogEntry fields: {sorted(values)}")
        return {field: values[field] for field in fields}
    raise ValueError(f"Unsupported static expression: {ast.dump(node, include_attributes=False)}")


def read_python_constants(path: Path, names: set[str]) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    environment: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name):
            continue
        name = targets[0].id
        value_node = node.value
        if value_node is None:
            continue
        if name in names or name in {"KOREAN_GENERAL_FEEDS", "KOREAN_TECH_FEEDS"}:
            environment[name] = evaluate_static_expression(value_node, environment)
    missing = names.difference(environment)
    if missing:
        raise ValueError(f"Static constants not found in {path}: {sorted(missing)}")
    return {name: environment[name] for name in names}


def extract_api_endpoints(path: Path) -> list[dict[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    endpoints: list[dict[str, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "app"
                and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                continue
            path_value = str(decorator.args[0].value)
            if path_value.startswith("/api/") or path_value == "/demo/article":
                endpoints.append(
                    {
                        "method": decorator.func.attr.upper(),
                        "path": path_value,
                        "handler": node.name,
                    }
                )
    return sorted(endpoints, key=lambda endpoint: (endpoint["path"], endpoint["method"]))


def load_dependencies() -> dict[str, Any]:
    client_package = json.loads((PROJECT_ROOT / "client" / "package.json").read_text(encoding="utf-8"))
    requirements = [
        line.strip()
        for line in (PROJECT_ROOT / "server" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return {
        "frontend": client_package.get("dependencies", {}),
        "backend": requirements,
    }


def connect_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_rows(connection: sqlite3.Connection, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def load_database_snapshot(database_path: Path, default_category_ids: set[str]) -> dict[str, Any]:
    with connect_read_only(database_path) as connection:
        tables = existing_tables(connection)
        table_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] if table in tables else 0
            for table in DATABASE_TABLES
        }

        categories = (
            fetch_rows(
                connection,
                """
                SELECT id, label, search_hint, created_at
                FROM newsletter_categories
                ORDER BY created_at, label
                """,
            )
            if "newsletter_categories" in tables
            else []
        )
        sources = (
            fetch_rows(
                connection,
                """
                SELECT category_id, source_label, feed_url, reason, created_at
                FROM newsletter_category_sources
                ORDER BY category_id, created_at, source_label
                """,
            )
            if "newsletter_category_sources" in tables
            else []
        )
        source_groups: dict[str, list[dict[str, Any]]] = {}
        for source in sources:
            category_id = source.pop("category_id")
            source_groups.setdefault(category_id, []).append(source)

        subscription_groups = (
            fetch_rows(
                connection,
                """
                SELECT category_id, cadence, status, COUNT(*) AS count,
                       MIN(created_at) AS first_created_at,
                       MAX(created_at) AS last_created_at,
                       SUM(CASE WHEN last_sent_at <> '' THEN 1 ELSE 0 END) AS sent_subscribers
                FROM newsletter_subscriptions
                GROUP BY category_id, cadence, status
                ORDER BY category_id, cadence, status
                """,
            )
            if "newsletter_subscriptions" in tables
            else []
        )
        delivery_groups = (
            fetch_rows(
                connection,
                """
                SELECT category_id, delivery_window, status, COUNT(*) AS count
                FROM newsletter_delivery_attempts
                GROUP BY category_id, delivery_window, status
                ORDER BY delivery_window, category_id, status
                """,
            )
            if "newsletter_delivery_attempts" in tables
            else []
        )

    subscription_by_category: dict[str, int] = Counter()
    for group in subscription_groups:
        subscription_by_category[group["category_id"]] += int(group["count"])

    category_records = []
    for category in categories:
        category_id = category["id"]
        category_records.append(
            {
                **category,
                "category_type": "default" if category_id in default_category_ids else "custom",
                "source_count": len(source_groups.get(category_id, [])),
                "subscription_count": subscription_by_category.get(category_id, 0),
                "sources": source_groups.get(category_id, []),
            }
        )

    status_counts = Counter()
    cadence_counts = Counter()
    sent_subscribers = 0
    for group in subscription_groups:
        status_counts[group["status"]] += int(group["count"])
        cadence_counts[group["cadence"]] += int(group["count"])
        sent_subscribers += int(group["sent_subscribers"] or 0)

    delivery_status_counts = Counter()
    for group in delivery_groups:
        delivery_status_counts[group["status"]] += int(group["count"])

    return {
        "database_file": relative_display_path(database_path),
        "privacy_mode": "aggregated_no_email_no_token_no_internal_id",
        "table_counts": table_counts,
        "category_count": len(category_records),
        "default_category_count": sum(record["category_type"] == "default" for record in category_records),
        "custom_category_count": sum(record["category_type"] == "custom" for record in category_records),
        "categories": category_records,
        "subscription_metrics": {
            "total": table_counts["newsletter_subscriptions"],
            "active": status_counts.get("active", 0),
            "sent_subscribers": sent_subscribers,
            "by_status": dict(sorted(status_counts.items())),
            "by_cadence": dict(sorted(cadence_counts.items())),
            "by_category": subscription_groups,
        },
        "delivery_metrics": {
            "total": table_counts["newsletter_delivery_attempts"],
            "by_status": dict(sorted(delivery_status_counts.items())),
            "by_category_window": delivery_groups,
        },
    }


def relative_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    environment: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        environment[key.strip()] = value.strip().strip("'\"")
    return environment


def load_supabase_snapshot(skip: bool) -> dict[str, Any]:
    base = {
        "purpose": "초기 연결 검증용 공개 todos 조회",
        "table": "public.todos",
        "selected_fields": ["id", "name"],
    }
    if skip:
        return {**base, "snapshot": {"status": "skipped", "row_count": 0, "rows": []}}

    environment = read_env_file(PROJECT_ROOT / "client" / ".env")
    project_url = environment.get("VITE_SUPABASE_URL", "").rstrip("/")
    publishable_key = environment.get("VITE_SUPABASE_PUBLISHABLE_KEY", "")
    if not project_url or not publishable_key:
        return {
            **base,
            "snapshot": {
                "status": "not_configured",
                "row_count": 0,
                "rows": [],
            },
        }

    query = urlencode({"select": "id,name", "order": "id.asc"})
    request = Request(
        f"{project_url}/rest/v1/todos?{query}",
        headers={
            "apikey": publishable_key,
            "Authorization": f"Bearer {publishable_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = parse_http_error(error)
        return {
            **base,
            "snapshot": {
                "status": "unavailable",
                "http_status": error.code,
                "error_code": details.get("code", ""),
                "message": details.get("message", "Supabase request failed"),
                "row_count": 0,
                "rows": [],
            },
        }
    except (URLError, TimeoutError) as error:
        return {
            **base,
            "snapshot": {
                "status": "unavailable",
                "message": str(getattr(error, "reason", error)),
                "row_count": 0,
                "rows": [],
            },
        }

    safe_rows = [
        {"id": row.get("id"), "name": row.get("name")}
        for row in rows
        if isinstance(row, dict)
    ]
    return {
        **base,
        "snapshot": {
            "status": "available",
            "row_count": len(safe_rows),
            "rows": safe_rows,
        },
    }


def parse_http_error(error: HTTPError) -> dict[str, Any]:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_payload(database_path: Path, skip_supabase: bool) -> dict[str, Any]:
    main_constants = read_python_constants(
        PROJECT_ROOT / "server" / "main.py",
        {"RSS_FEEDS", "DEEPL_TARGET_LANGUAGES"},
    )
    discovery_constants = read_python_constants(
        PROJECT_ROOT / "server" / "newsletter_discovery.py",
        {"CATALOG"},
    )
    rss_feeds: dict[str, dict[str, Any]] = main_constants["RSS_FEEDS"]
    catalog = list(discovery_constants["CATALOG"])
    endpoints = extract_api_endpoints(PROJECT_ROOT / "server" / "main.py")
    database = load_database_snapshot(database_path, set(rss_feeds))
    supabase = load_supabase_snapshot(skip_supabase)

    rss_categories = [
        {
            "id": category_id,
            "label": configuration["label"],
            "keywords": configuration.get("keywords", []),
            "keyword_count": len(configuration.get("keywords", [])),
            "feeds": configuration["feeds"],
            "feed_count": len(configuration["feeds"]),
        }
        for category_id, configuration in rss_feeds.items()
    ]
    unique_feed_urls = sorted(
        {
            feed_url
            for configuration in rss_feeds.values()
            for feed_url in configuration["feeds"]
        }
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": {
            "name": "읽을게",
            "package_name": "ilgeulge-reader",
            "version": "0.1.0",
            "summary": "URL 본문 추출, 접근성 리더뷰, RSS 큐레이션, AI 요약·관찰 노트, 뉴스레터를 결합한 뉴스 읽기 서비스",
            "architecture": {
                "frontend": "React + Vite",
                "backend": "FastAPI",
                "primary_storage": "SQLite",
                "external_storage_prototype": "Supabase public.todos 조회",
                "external_services": ["Claude Messages API", "DeepL API", "RSS/Atom", "SMTP"],
                "browser_capabilities": ["localStorage", "Web Speech API"],
            },
            "dependencies": load_dependencies(),
        },
        "presentation_highlights": {
            "api_endpoint_count": len(endpoints),
            "default_rss_category_count": len(rss_categories),
            "unique_default_feed_count": len(unique_feed_urls),
            "feed_discovery_catalog_count": len(catalog),
            "stored_category_count": database["category_count"],
            "custom_category_count": database["custom_category_count"],
            "active_subscription_count": database["subscription_metrics"]["active"],
            "delivery_attempt_count": database["delivery_metrics"]["total"],
            "supabase_todos_status": supabase["snapshot"]["status"],
        },
        "api": {
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        },
        "rss": {
            "default_category_count": len(rss_categories),
            "unique_default_feed_count": len(unique_feed_urls),
            "unique_default_feed_urls": unique_feed_urls,
            "default_categories": rss_categories,
            "discovery_catalog_count": len(catalog),
            "discovery_catalog": catalog,
        },
        "local_database": database,
        "supabase": supabase,
        "client_defaults": {
            "reader_settings_storage_key": "reader-settings",
            "reader_settings": {
                "fontSize": 18,
                "lineHeight": 1.75,
                "paragraphSpacing": 1.4,
                "contentWidth": 720,
                "theme": "light",
            },
            "translation_targets": [
                {"label": "한국어", "value": "Korean"},
                {"label": "영어", "value": "English"},
                {"label": "일본어", "value": "Japanese"},
                {"label": "중국어(간체)", "value": "Simplified Chinese"},
            ],
            "deepl_target_codes": main_constants["DEEPL_TARGET_LANGUAGES"],
            "sample_urls": [
                {"label": "데모 기사", "url": "/demo/article"},
                {
                    "label": "MDN 접근성 문서",
                    "url": "https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Accessibility/What_is_accessibility",
                },
                {"label": "FastAPI 문서", "url": "https://fastapi.tiangolo.com/ko/"},
                {
                    "label": "Django 릴리스 글",
                    "url": "https://www.djangoproject.com/weblog/2025/dec/03/django-60-released/",
                },
            ],
        },
        "privacy": {
            "excluded": [
                "newsletter_subscriptions.email",
                "newsletter_subscriptions.unsubscribe_token",
                "newsletter_subscriptions.id",
                "newsletter_delivery_attempts.subscription_id",
                "newsletter_delivery_attempts.error",
                "all environment variable values and API keys",
            ],
            "included": [
                "category and source metadata",
                "aggregated subscription and delivery counts",
                "public Supabase todos fields only when available",
            ],
        },
        "source_files": [
            "README.md",
            "client/src/main.jsx",
            "client/package.json",
            "server/main.py",
            "server/newsletter_discovery.py",
            "server/newsletter.sqlite3",
            "server/requirements.txt",
        ],
    }


def main() -> int:
    arguments = parse_arguments()
    if not arguments.database.exists():
        print(f"Database not found: {arguments.database}", file=sys.stderr)
        return 2

    payload = build_payload(arguments.database, arguments.skip_supabase)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported presentation data to {relative_display_path(arguments.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
