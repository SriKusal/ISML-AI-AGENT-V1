import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


class DeepSeekRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_deepseek_generate_returns_error_when_key_missing(self) -> None:
        """When DEEPSEEK_API_KEY is absent the service raises ValueError → 500."""
        with patch("app.services.deepseek_service.DeepSeekService.generate_text",
                   side_effect=ValueError("DEEPSEEK_API_KEY is not configured")):
            response = self.client.post(
                "/api/v1/deepseek/generate",
                json={"prompt": "Hello from tests"},
            )
        self.assertEqual(response.status_code, 500)
        body = response.json()
        # Response may use either {"detail": ...} or {"error": {"message": ...}} envelope
        error_text = (
            body.get("detail", "")
            or body.get("error", {}).get("message", "")
        )
        self.assertIn("DEEPSEEK_API_KEY", error_text)


if __name__ == "__main__":
    unittest.main()
