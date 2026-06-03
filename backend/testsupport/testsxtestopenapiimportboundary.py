import json
import subprocess
import sys
from pathlib import Path


def test_openapi_generation_does_not_initialize_runtime_config_storage():
    backend_dir = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error::UserWarning",
            "-c",
            (
                "import json\n"
                "from app.appmain import app\n"
                "schema = app.openapi()\n"
                "print(json.dumps({"
                "'openapi': schema.get('openapi'), "
                "'path_count': len(schema.get('paths', {})), "
                "'schema_count': len(schema.get('components', {}).get('schemas', {}))"
                "}, sort_keys=True))\n"
            ),
        ],
        cwd=backend_dir,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "MongoDB数据库未初始化" not in result.stdout + result.stderr
    assert "command find requires authentication" not in result.stdout + result.stderr

    summary = json.loads(result.stdout.strip())
    assert summary["openapi"] == "3.1.0"
    assert summary["path_count"] > 0
    assert summary["schema_count"] > 0
