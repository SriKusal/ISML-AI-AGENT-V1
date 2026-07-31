import unittest

from fastapi.testclient import TestClient

from main import app


class DeepSeekRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_deepseek_generate_returns_error_when_key_missing(self) -> None:
        response = self.client.post(
            "/api/v1/deepseek/generate",
            json={"prompt": "Hello from tests"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("DEEPSEEK_API_KEY", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
