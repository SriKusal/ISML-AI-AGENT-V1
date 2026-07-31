import unittest

from app.services.gemini_service import GeminiService


class GeminiServiceTests(unittest.TestCase):
    def test_build_url_normalizes_model_name(self) -> None:
        service = GeminiService(api_key="test-key")
        url = service._build_url("gemini 3.1 flash")
        self.assertIn("/models/gemini-3.1-flash:generateContent", url)


if __name__ == "__main__":
    unittest.main()
