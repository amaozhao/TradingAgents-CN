import json
import re
from pathlib import Path

from app.core.migrate import HOT_COLLECTIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DOCS = REPO_ROOT / "docs" / "migration"


def test_migration_docs_do_not_reference_missing_repo_files():
    missing: list[str] = []
    pattern = re.compile(r"`((?:backend|docs|config)/[^`]+)`")

    for doc_path in MIGRATION_DOCS.glob("*.md"):
        for match in pattern.finditer(doc_path.read_text(encoding="utf-8")):
            raw_reference = match.group(1)
            reference = raw_reference.split("#", 1)[0]
            if "*" in reference:
                exists = bool(list(REPO_ROOT.glob(reference)))
            else:
                exists = (REPO_ROOT / reference).exists()
            if not exists:
                missing.append(f"{doc_path.relative_to(REPO_ROOT)} -> {raw_reference}")

    assert missing == []


def test_completion_audit_covers_every_task_plan_item():
    task_plan = (MIGRATION_DOCS / "postgres_migration_task_plan.md").read_text(
        encoding="utf-8"
    )
    completion_audit = (MIGRATION_DOCS / "postgres_completion_audit.md").read_text(
        encoding="utf-8"
    )

    planned_tasks = _sort_task_ids(
        set(re.findall(r"^## (T\d+)\.", task_plan, flags=re.MULTILINE))
    )
    audited_tasks = _sort_task_ids(
        set(re.findall(r"^### (T\d+)\.", completion_audit, flags=re.MULTILINE))
    )

    assert planned_tasks
    assert audited_tasks
    assert audited_tasks == planned_tasks


def test_inventory_named_write_collections_have_migration_decisions():
    inventory = _load_inventory()
    docs_text = "\n".join(
        path.read_text(encoding="utf-8") for path in MIGRATION_DOCS.glob("*.md")
    )
    named_collections = {
        item["collection"]
        for item in inventory["postgres_writes"]
        if item.get("collection")
    }
    documented_collections = set(re.findall(r"`([A-Za-z0-9_]+)`", docs_text))
    covered_collections = set(HOT_COLLECTIONS) | documented_collections

    assert "collection" not in named_collections
    assert sorted(named_collections - covered_collections) == []


def test_unresolved_dynamic_postgres_writes_have_manual_audit_rows():
    inventory = _load_inventory()
    long_tail_doc = (MIGRATION_DOCS / "postgres_long_tail_coverage.md").read_text(
        encoding="utf-8"
    )
    unresolved_writes = [
        item for item in inventory["postgres_writes"] if not item.get("collection")
    ]

    missing = []
    for item in unresolved_writes:
        reference = f"`{item['path']}` | {item['line']} | `{item['operation']}`"
        if reference not in long_tail_doc:
            missing.append(reference)

    assert missing == []


def test_operator_script_postgres_writes_have_manual_audit_rows():
    inventory = _load_inventory()
    long_tail_doc = (MIGRATION_DOCS / "postgres_long_tail_coverage.md").read_text(
        encoding="utf-8"
    )
    script_writes = [
        item
        for item in inventory["postgres_writes"]
        if item["path"].startswith("app/scripts/")
    ]

    missing = []
    for item in script_writes:
        reference = f"`{item['path']}` | {item['line']} | `{item['operation']}`"
        if reference not in long_tail_doc:
            missing.append(reference)

    assert missing == []


def test_cutover_runbook_keeps_api_smoke_as_post_read_acceptance():
    runbook = (MIGRATION_DOCS / "postgres_cutover_runbook.md").read_text(
        encoding="utf-8"
    )
    stop_conditions = _section(runbook, "## Stop Conditions")
    post_read = _section(runbook, "## Post-Read Acceptance Conditions")

    assert (
        "Do not move from `dual_write` to `postgres_read_postgres_fallback`"
        in stop_conditions
    )
    assert "API smoke is missing" not in stop_conditions
    assert "API smoke is missing or `all_passed=false`" in post_read
    assert "after entering `postgres_read_postgres_fallback`" in runbook


def test_worker_dual_write_coverage_matches_inventory():
    inventory = _load_inventory()
    coverage_doc = (MIGRATION_DOCS / "worker_dual_write_coverage.md").read_text(
        encoding="utf-8"
    )
    documented_rows = _parse_worker_coverage_rows(coverage_doc)
    worker_write_files = set(inventory["worker_postgres_write_files"])
    inventory_rows = {
        (
            item["path"],
            item["line"],
            item.get("collection"),
            item["operation"],
        )
        for item in inventory["postgres_writes"]
        if item["path"] in worker_write_files
    }

    assert sorted(inventory_rows - documented_rows) == []


def _sort_task_ids(task_ids: set[str]) -> list[str]:
    return sorted(task_ids, key=lambda task_id: int(task_id.removeprefix("T")))


def _load_inventory() -> dict:
    return json.loads(
        (MIGRATION_DOCS / "postgres_inventory.json").read_text(encoding="utf-8")
    )


def _section(markdown: str, heading: str) -> str:
    start = markdown.index(heading)
    next_heading = markdown.find("\n## ", start + len(heading))
    if next_heading == -1:
        return markdown[start:]
    return markdown[start:next_heading]


def _parse_worker_coverage_rows(markdown: str) -> set[tuple[str, int, str, str]]:
    rows: set[tuple[str, int, str, str]] = set()
    for line in markdown.splitlines():
        if not line.startswith("| `app/"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        status = cells[5].lower()
        if status != "covered":
            continue
        rows.add(
            (
                cells[0].strip("`"),
                int(cells[1]),
                cells[2].strip("`"),
                cells[3].strip("`"),
            )
        )
    return rows
