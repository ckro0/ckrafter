import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.crews.dev_crew import _analyze_project, _ask_project, _scan_light


class ExternalProjectTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_analysis_reads_readme_and_manifests_and_waits_for_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary, "booking-app")
            folder.mkdir()
            (folder / "README.md").write_text(
                "Hotel booking app for creating and managing reservations.",
                encoding="utf-8",
            )
            (folder / "pyproject.toml").write_text(
                '[project]\nname = "booking-app"\ndescription = "Manage hotel reservations"\n',
                encoding="utf-8",
            )
            (folder / ".env").write_text(
                "API_KEY=must-not-be-read-or-sent", encoding="utf-8"
            )
            tree, context = _scan_light(folder)
            self.assertIn("README.md", context)
            self.assertIn("pyproject.toml", context)
            self.assertNotIn("must-not-be-read-or-sent", context)
            self.assertNotIn(".env", tree)

            agents = (object(),) * 8
            session = {
                "id": "20261026_112200",
                "requirement": "Proyecto existente: booking-app",
                "output_dir": temporary,
            }
            with (
                patch("src.crews.dev_crew.get_agents", return_value=agents),
                patch("src.crews.dev_crew.Runner.run", new=AsyncMock(
                    return_value=SimpleNamespace(final_output="Ya leí el proyecto. ¿Qué hacemos?")
                )) as run_agent,
                patch("src.crews.dev_crew.close_agents", new=AsyncMock()) as close_agents,
                patch("src.crews.dev_crew._save_output") as save_output,
                patch("src.crews.dev_crew.save_session"),
            ):
                analyzed, analysis = await _analyze_project(
                    str(folder), "espanol", session=session
                )

        self.assertIs(analyzed, session)
        self.assertEqual(analysis, "Ya leí el proyecto. ¿Qué hacemos?")
        prompt = run_agent.await_args.kwargs["input"]
        self.assertIn("README y manifiestos disponibles", prompt)
        self.assertIn("No ejecutes cambios", prompt)
        self.assertIn("preguntando que quiere hacer", prompt)
        self.assertEqual(run_agent.await_args.args[0], agents[7])
        close_agents.assert_awaited_once_with(agents)
        self.assertEqual(save_output.call_args.args[1], "00_project_analysis.md")

    async def test_project_answers_include_prior_conversation_and_close_agents(self):
        session = {
            "language": "espanol",
            "external_folder": "C:\\project",
            "requirement": "Proyecto existente",
            "conversation": [
                {"role": "user", "content": "Explícame primero el estado."},
                {"role": "assistant", "content": "Es un prototipo."},
            ],
        }
        agents = (object(),) * 8
        with (
            patch("src.crews.dev_crew._load_output", return_value="README: app de reservas"),
            patch("src.crews.dev_crew.get_agents", return_value=agents),
            patch("src.crews.dev_crew.Runner.run", new=AsyncMock(
                return_value=SimpleNamespace(final_output="Respuesta")
            )) as run_agent,
            patch("src.crews.dev_crew.close_agents", new=AsyncMock()) as close_agents,
        ):
            answer = await _ask_project(session, "¿Qué debería corregir primero?")

        self.assertEqual(answer, "Respuesta")
        prompt = run_agent.await_args.kwargs["input"]
        self.assertIn("Explícame primero el estado.", prompt)
        self.assertIn("Es un prototipo.", prompt)
        self.assertIn("¿Qué debería corregir primero?", prompt)
        close_agents.assert_awaited_once_with(agents)
