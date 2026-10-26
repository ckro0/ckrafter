import unittest

from src.interfaces.cli import BANNER, _pipeline_board


class CliBrandingTests(unittest.TestCase):
    def test_banner_uses_current_project_name(self):
        self.assertIn("CKRAFTER", BANNER)
        self.assertNotIn("AGENTE S", BANNER)

    def test_progress_board_uses_current_project_name(self):
        session = {
            "steps": {
                "pm": "pending",
                "backend": "pending",
                "frontend": "pending",
                "qa": "pending",
                "security": "pending",
                "devops": "pending",
                "tech_writer": "pending",
            },
        }

        self.assertIn("CKRAFTER", str(_pipeline_board(session, 0).title))
