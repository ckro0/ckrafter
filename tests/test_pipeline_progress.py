import asyncio
from io import StringIO
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from rich.console import Console

from src.crews.dev_crew import _run_agent, _run_dev_pipeline_steps, _run_lead_review
from src.interfaces.cli import _GLOBE_FRAMES, _RotatingGlobe, _pipeline_board


class PipelineProgressTests(unittest.IsolatedAsyncioTestCase):
    def test_globe_animation_changes_frames(self):
        rendered_frames = []
        for timestamp in (0.0, 0.4):
            output = StringIO()
            with patch("src.interfaces.cli.time.monotonic", return_value=timestamp):
                Console(file=output, width=40, color_system=None).print(_RotatingGlobe(0))
            rendered_frames.append(output.getvalue())

        self.assertNotEqual(*rendered_frames)

    def test_animation_art_uses_ascii_characters(self):
        for frame in _GLOBE_FRAMES:
            self.assertTrue(all(character.isascii() for character in frame))

    def test_progress_panel_shows_agent_status(self):
        output = StringIO()
        session = {
            "steps": {
                "pm": "completed",
                "backend": "running",
                "frontend": "running",
                "qa": "pending",
                "security": "pending",
                "devops": "pending",
                "tech_writer": "pending",
            }
        }
        Console(file=output, width=100, legacy_windows=True).print(
            _pipeline_board(session, time.monotonic())
        )

        self.assertIn("Construccion", output.getvalue())
        self.assertIn("En marcha", output.getvalue())

    async def test_reports_agent_start_and_completion(self):
        session = {"steps": {"pm": "pending"}, "error": None}
        progress = []

        with (
            patch("src.crews.dev_crew.Runner.run", new=AsyncMock(
                return_value=SimpleNamespace(final_output="Plan listo")
            )),
            patch("src.crews.dev_crew.save_session"),
        ):
            result = await _run_agent(
                object(), "requerimiento", "Project Manager", session, "pm",
                lambda step, status: progress.append((step, status)),
            )

        self.assertEqual(result.final_output, "Plan listo")
        self.assertEqual(progress, [("pm", "running"), ("pm", "completed")])
        self.assertEqual(session["steps"]["pm"], "completed")

    async def test_reports_agent_failure(self):
        session = {"steps": {"qa": "pending"}, "error": None}
        progress = []

        with (
            patch("src.crews.dev_crew.Runner.run", new=AsyncMock(
                side_effect=RuntimeError("fallo de prueba")
            )),
            patch("src.crews.dev_crew.save_session"),
        ):
            with self.assertRaisesRegex(RuntimeError, "fallo de prueba"):
                await _run_agent(
                    object(), "requerimiento", "QA Engineer", session, "qa",
                    lambda step, status: progress.append((step, status)),
                )

        self.assertEqual(progress, [("qa", "running"), ("qa", "failed")])
        self.assertEqual(session["steps"]["qa"], "failed")

    async def test_successful_parallel_agent_does_not_clear_sibling_failure(self):
        session = {"steps": {"backend": "pending", "frontend": "pending"}, "error": None}

        async def run_agent(agent, input):
            if agent == "backend":
                raise RuntimeError("fallo de backend")
            return SimpleNamespace(final_output="Interfaz lista")

        with (
            patch("src.crews.dev_crew.Runner.run", new=AsyncMock(side_effect=run_agent)),
            patch("src.crews.dev_crew.save_session"),
        ):
            results = await asyncio.gather(
                _run_agent("backend", "requerimiento", "Backend", session, "backend"),
                _run_agent("frontend", "requerimiento", "Frontend", session, "frontend"),
                return_exceptions=True,
            )

        self.assertIsInstance(results[0], RuntimeError)
        self.assertEqual(session["steps"]["backend"], "failed")
        self.assertEqual(session["steps"]["frontend"], "completed")
        self.assertIn("fallo de backend", session["error"])

    async def test_resuming_pipeline_clears_the_previous_error(self):
        session = {
            "steps": {
                "pm": "completed",
                "backend": "completed",
                "frontend": "completed",
                "qa": "completed",
                "security": "completed",
                "devops": "completed",
                "tech_writer": "completed",
            },
            "error": "fallo anterior",
        }
        with (
            patch("src.crews.dev_crew._load_output", return_value="Entregable listo"),
            patch("src.crews.dev_crew.save_session") as save_session,
        ):
            await _run_dev_pipeline_steps(
                "requerimiento",
                "espanol",
                session,
                (None,) * 8,
            )

        self.assertIsNone(session["error"])
        save_session.assert_called_once_with(session)

    async def test_focused_review_adds_selected_context_to_lead_prompt(self):
        lead = object()
        session = {
            "id": "20261026_112200",
            "requirement": "Una app escrita en Java",
            "language": "espanol",
            "steps": {"pm": "completed"},
        }
        result = SimpleNamespace(final_output="Revision enfocada")

        with (
            patch("src.crews.dev_crew._load_output", return_value="Entregable del proyecto"),
            patch("src.crews.dev_crew.get_agents", return_value=(None,) * 7 + (lead,)),
            patch("src.crews.dev_crew.Runner.run", new=AsyncMock(return_value=result)) as run_agent,
            patch("src.crews.dev_crew._save_output"),
            patch("src.crews.dev_crew.close_agents", new=AsyncMock()),
        ):
            review = await _run_lead_review(session, "Prioriza compatibilidad con Java", quiet=True)

        self.assertEqual(review, "Revision enfocada")
        prompt = run_agent.await_args.kwargs["input"]
        self.assertIn("Prioriza compatibilidad con Java", prompt)
        self.assertIn("Una app escrita en Java", prompt)


if __name__ == "__main__":
    unittest.main()
