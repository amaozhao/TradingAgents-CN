import re
from pathlib import Path


RAW_BODY_PATTERN = re.compile(
    r"\b(payload|request|settings|config_data)\s*:\s*"
    r"(dict|Dict\[str,\s*Any\]|Dict\[str,Any\])"
)


def test_routers_do_not_use_raw_dict_request_bodies():
    routers_dir = Path(__file__).resolve().parents[1] / "app" / "routers"
    offenders = []

    for router_path in routers_dir.glob("*.py"):
        text = router_path.read_text(encoding="utf-8")
        for match in RAW_BODY_PATTERN.finditer(text):
            line_no = text[:match.start()].count("\n") + 1
            offenders.append(f"{router_path.name}:{line_no}")

    assert offenders == []
