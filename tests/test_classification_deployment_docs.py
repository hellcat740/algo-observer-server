import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ClassificationDeploymentDocsTest(unittest.TestCase):
    def test_env_example_has_both_provider_templates_without_real_keys(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        for expected in (
            "CLASSIFICATION_PROVIDER=deepseek",
            "QWEN_API_KEY=replace-with-qwen-secret",
            "QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1",
            "QWEN_MODEL=qwen3.7-flash",
        ):
            self.assertIn(expected, text)
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9]", text))

    def test_alibaba_cloud_operations_are_documented(self):
        deploy = (ROOT / "DEPLOY.md").read_text(encoding="utf-8")
        for expected in (
            "/opt/algo-observer-server/.env",
            "api/app/classification_config.py",
            "docker compose up -d --force-recreate web",
            "POST /api/space/classification-check",
            "01:17",
            "100",
        ):
            self.assertIn(expected, deploy)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("CLASSIFICATION_PROVIDER", readme)
        self.assertIn("QWEN_API_KEY", readme)


if __name__ == "__main__":
    unittest.main()
