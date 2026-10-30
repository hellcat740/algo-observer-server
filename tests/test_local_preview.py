import json
from pathlib import Path


def test_npm_dev_starts_the_existing_fastapi_application():
    package = json.loads((Path(__file__).resolve().parent.parent / "package.json").read_text(encoding="utf-8"))
    script = package["scripts"]["dev"]
    assert ".venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir api" in script
    assert "--host" not in script
    assert "--port" not in script
