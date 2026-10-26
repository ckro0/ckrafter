import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from repair_finder.server import SearchError, normalize_result, search_ifixit


class SearchResultTests(unittest.TestCase):
    def test_normalizes_ifixit_guide(self):
        result = normalize_result(
            {
                "dataType": "guide",
                "title": "Battery replacement",
                "summary": "Replace the battery.",
                "url": "https://www.ifixit.com/Guide/Battery/1",
                "langid": "en",
                "difficulty": "Moderate",
                "modified_date": 1700000000,
                "image": {
                    "thumbnail": "https://guide-images.cdn.ifixit.com/example.thumbnail"
                },
            }
        )

        self.assertEqual(result["title"], "Battery replacement")
        self.assertEqual(result["kind"], "guide")
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["modified"], 1700000000)
        self.assertIsNotNone(result["image"])

    def test_rejects_non_ifixit_links(self):
        result = normalize_result(
            {"title": "Unexpected link", "url": "https://example.com/resource"}
        )
        self.assertIsNone(result)

    def test_search_normalizes_provider_response(self):
        payload = {
            "results": [
                {
                    "dataType": "guide",
                    "title": "Screen replacement",
                    "url": "https://www.ifixit.com/Guide/Screen/1",
                },
                {"title": "Invalid link", "url": "https://example.com/"},
            ]
        }
        response = BytesIO(json.dumps(payload).encode())
        response.__enter__ = lambda: response
        response.__exit__ = lambda *args: None

        with patch("repair_finder.server.urlopen", return_value=response):
            results = search_ifixit("iPhone 13")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Screen replacement")

    def test_search_reports_connection_errors(self):
        with patch("repair_finder.server.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(SearchError):
                search_ifixit("iPhone 13")


if __name__ == "__main__":
    unittest.main()
