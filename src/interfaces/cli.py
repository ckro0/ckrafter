"""
Interfaz de linea de comandos (CLI) para el equipo multi-agente.

Para agregar otra interfaz (web, API, etc.) crea un nuevo archivo en este
mismo directorio, por ejemplo:
  - src/interfaces/web.py   -> Streamlit / Gradio
  - src/interfaces/api.py   -> FastAPI con endpoints REST
  - src/interfaces/tui.py   -> Textual (terminal UI interactiva)

Cada interfaz solo necesita llamar a:
    from src.crews.dev_crew import run as run_pipeline
    run_pipeline(requirement, output_language, session)
"""

import argparse
import os
import re
import sys
import time

from dotenv import load_dotenv
from openai import RateLimitError
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

BANNER = """
+----------------------------------------------------------------+
|                         AGENTE S                               |
|          Tu equipo de desarrollo, listo para ayudar            |
+----------------------------------------------------------------+
|  Planifica  |  Diseña  |  Comprueba  |  Prepara  |  Explica   |
+----------------------------------------------------------------+
"""

STEP_NAMES = {
    "pm":          "Project Manager",
    "backend":     "Backend Developer",
    "frontend":    "Frontend Developer",
    "qa":          "QA Engineer",
    "security":    "Security Auditor",
    "devops":      "DevOps Engineer",
    "tech_writer": "Tech Writer",
}

PROVIDER_CONFIGS = {
    "groq": {
        "OPENAI_BASE_URL": "https://api.groq.com/openai/v1",
        "OPENAI_MODEL": "openai/gpt-oss-120b",
        "LOW_COST_MODEL": "openai/gpt-oss-120b",
    },
    "openai": {
        "OPENAI_BASE_URL": "",
        "OPENAI_MODEL": "gpt-4o-mini",
        "LOW_COST_MODEL": "gpt-4o-mini",
    },
    "ollama": {
        "OPENAI_BASE_URL": "http://localhost:11434/v1",
        "OPENAI_MODEL": "llama3.2",
        "LOW_COST_MODEL": "llama3.2",
    },
}


def _show_error(exc: Exception) -> None:
    """Muestra un error de forma amigable; detecta rate limit y muestra el tiempo de espera."""
    if isinstance(exc, RateLimitError):
        msg = str(exc)
        wait_match = re.search(r"try again in ([^.\"]+)", msg, re.IGNORECASE)
        wait_str = wait_match.group(1).strip() if wait_match else "un momento"
        console.print(Panel(
            f"[bold red]Limite de tokens diarios alcanzado.[/bold red]\n\n"
            f"Groq (plan gratuito) permite 100 000 tokens/dia.\n"
            f"Tiempo de espera: [bold yellow]{wait_str}[/bold yellow]\n\n"
            f"Puedes volver a intentarlo cuando se restablezca el limite.",
            title="Rate Limit - Groq",
            border_style="red",
        ))
    else:
        console.print(f"[red]Error: {exc}[/red]")


def configure_provider(provider: str | None, low_cost: bool = False) -> str:
    provider = (provider or os.getenv("OPENAI_PROVIDER", "groq")).lower()
    if provider not in PROVIDER_CONFIGS:
        console.print(
            Panel(
                f"[bold red]Proveedor desconocido:[/bold red] {provider}\n\n"
                f"Proveedores disponibles: {', '.join(PROVIDER_CONFIGS)}",
                title="Configuracion de proveedor",
                border_style="red",
            )
        )
        sys.exit(1)

    config = PROVIDER_CONFIGS[provider]
    os.environ["OPENAI_PROVIDER"] = provider
    os.environ["OPENAI_BASE_URL"] = config["OPENAI_BASE_URL"]
    model = config["LOW_COST_MODEL"] if low_cost else config["OPENAI_MODEL"]
    os.environ["OPENAI_MODEL"] = model
    os.environ["LOW_COST_MODE"] = "1" if low_cost else "0"
    return provider


def check_env() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        console.print(
            Panel(
                "[bold red]OPENAI_API_KEY no configurada.[/bold red]\n\n"
                "Edita el archivo [cyan].env[/cyan] y agrega tu API key.",
                title="Configuracion requerida",
                border_style="red",
            )
        )
        sys.exit(1)


def display_start(requirement: str, output_language: str, provider: str) -> None:
    console.print(
        Panel(
            f"[bold green]Tu idea:[/bold green]\n{requirement}\n\n"
            f"[bold green]Idioma de los documentos:[/bold green] {output_language}\n"
            f"[dim]Servicio de IA: {provider}[/dim]",
            title="¡Vamos a construirlo!",
            border_style="green",
        )
    )


def display_complete(output_dir: str) -> None:
    console.print(
        Panel(
            "[bold green]Tu paquete de proyecto está listo.[/bold green]\n\n"
            "Preparamos siete documentos con el plan, ejemplos, revisiones y una guia para continuar.\n\n"
            f"Los encontrarás en: [cyan]{output_dir}/[/cyan]\n\n"
            "Empieza por [cyan]01_plan_tecnico.md[/cyan] para ver el resumen de tu idea.",
            title="¡Buen trabajo!",
            border_style="green",
        )
    )


# ── Flowchart ────────────────────────────────────────────────────────────────

_STATUS_COLOR = {
    "completed": "green",
    "failed":    "red",
    "running":   "yellow",
    "pending":   "dim",
}

_STATUS_LABEL = {
    "completed": "DONE",
    "failed":    "FAIL",
    "running":   "...",
    "pending":   "---",
}


def _badge(status: str) -> str:
    color = _STATUS_COLOR.get(status, "white")
    label = _STATUS_LABEL.get(status, "?")
    return f"[{color}][{label}][/{color}]"


_PIPELINE_STEPS = (
    ("pm", "Plan del proyecto", "Ordena la idea y define el camino"),
    ("backend", "Construccion", "Prepara la logica y los datos"),
    ("frontend", "Interfaz", "Disena las pantallas"),
    ("qa", "Pruebas", "Comprueba que todo encaje"),
    ("security", "Seguridad", "Busca puntos que necesiten atencion"),
    ("devops", "Preparacion", "Deja listo el proyecto para arrancar"),
    ("tech_writer", "Guia de uso", "Explica como seguir adelante"),
)


_GLOBE_FRAMES = (
    (
        "          .-=========-.",
        "       .-'   .----.    '-.",
        "     .'    .'######'.      '.",
        "    /     /##########\\       \\",
        "   |     |############|       |",
        "   |     |##########..|       |",
        "    \\     \\##########/       /",
        "     '.    '.######.'      .'",
        "       '-.   '----'    .-'",
        "          '-.======.-'",
    ),
    (
        "          .-=========-.",
        "       .-'   .----.    '-.",
        "     .'    .-'####'-.     '.",
        "    /     /##########\\      \\",
        "   |     |############|      |",
        "   |     |##########..|      |",
        "    \\     \\##########/      /",
        "     '.    '-.####.-'     .'",
        "       '-.   '----'    .-'",
        "          '-.======.-'",
    ),
    (
        "          .-=========-.",
        "       .-'    .----.   '-.",
        "     .'     .'#######'.    '.",
        "    /      /###########\\     \\",
        "   |      |#############|     |",
        "   |      |#############|     |",
        "    \\      \\###########/     /",
        "     '.     '.#######.'    .'",
        "       '-.   '----'   .-'",
        "          '-.======.-'",
    ),
    (
        "          .-=========-.",
        "       .-'    .----.   '-.",
        "     .'    .-'######'-.   '.",
        "    /     /############\\    \\",
        "   |     |##############|    |",
        "   |     |..############|    |",
        "    \\     \\############/    /",
        "     '.    '-.######.-'   .'",
        "       '-.    '----'   .-'",
        "          '-.======.-'",
    ),
    (
        "          .-=========-.",
        "       .-'   .----.    '-.",
        "     .'    .'######'.      '.",
        "    /     /##########\\       \\",
        "   |     |############|       |",
        "   |     |##########..|       |",
        "    \\     \\##########/       /",
        "     '.    '.######.'      .'",
        "       '-.   '----'    .-'",
        "          '-.======.-'",
    ),
)


class _RotatingGlobe:
    def __init__(self, started_at: float) -> None:
        self.started_at = started_at

    def __rich_console__(self, console, options):
        frame_index = int((time.monotonic() - self.started_at) * 3) % len(_GLOBE_FRAMES)
        yield Text("\n".join(_GLOBE_FRAMES[frame_index]), style="bold cyan")


class _AsciiSpinner:
    def __rich_console__(self, console, options):
        frame = "|/-\\"[int(time.monotonic() * 8) % 4]
        yield Text(f"{frame} En marcha", style="yellow")


def _pipeline_board(session: dict, started_at: float) -> Panel:
    steps = session["steps"]
    completed = sum(status == "completed" for status in steps.values())
    table = Table(box=None, expand=True, padding=(0, 1), show_header=False)
    table.add_column("Flujo del equipo", style="bold", width=26, no_wrap=True)
    table.add_column("En que ayuda", width=43)
    table.add_column("Estado", justify="right", width=15, no_wrap=True)

    for key, name, description in _PIPELINE_STEPS:
        status = steps.get(key, "pending")
        if status == "completed":
            indicator = Text("LISTO", style="bold green")
        elif status == "failed":
            indicator = Text("REVISAR", style="bold red")
        elif status == "running":
            indicator = _AsciiSpinner()
        else:
            indicator = Text("En espera", style="dim")

        if key == "backend":
            name = "+-- " + name
        elif key == "frontend":
            name = "\\-- " + name
            description += " (a la vez que Construccion)"
        elif key != "pm":
            name = "|   " + name
        table.add_row(name, description, indicator)

    elapsed = int(time.monotonic() - started_at)
    minutes, seconds = divmod(elapsed, 60)
    content = Group(
        Align.center(
            Text.from_markup(
                "[bold]UNA IDEA, TODO UN EQUIPO[/bold]\n"
                "[dim]Estamos convirtiendo tu idea en un proyecto, paso a paso.[/dim]"
            )
        ),
        Align.center(_RotatingGlobe(started_at)),
        Align.center(
            Text.from_markup(
                f"[bold cyan]{completed} de {len(_PIPELINE_STEPS)} pasos listos[/bold cyan]"
                f"   [dim]Tiempo: {minutes:02d}:{seconds:02d}[/dim]"
            )
        ),
        Text(""),
        table,
        Text(""),
        Align.center(
            Text.from_markup(
                "[dim]Puedes dejar esta ventana abierta; el avance se guarda automaticamente.[/dim]"
            )
        ),
    )
    return Panel(
        content,
        title="[bold cyan] AGENTE S [/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 3),
    )


def show_flowchart(session: dict) -> None:
    """Muestra un diagrama de flujo ASCII del estado actual del proyecto."""
    steps = session["steps"]
    created = session.get("created_at", "")[:16].replace("T", " ")

    console.print()
    console.print(Panel(
        f"[bold]Proyecto:[/bold] {session['requirement']}\n"
        f"[bold]Sesion:[/bold]   {session['id']}  ({created})\n"
        f"[bold]Idioma:[/bold]   {session['language']}",
        title="Diagrama de flujo del proyecto",
        border_style="cyan",
    ))

    pm  = _badge(steps["pm"])
    be  = _badge(steps["backend"])
    fe  = _badge(steps["frontend"])
    qa  = _badge(steps["qa"])
    sec = _badge(steps["security"])
    dv  = _badge(steps["devops"])
    tw  = _badge(steps["tech_writer"])

    diagram = (
        "\n"
        f"         +---------------------------+\n"
        f"         |    Project Manager        |  {pm}\n"
        f"         +------------+--------------+\n"
        f"                      |\n"
        f"            +---------+---------+\n"
        f"            |                   |\n"
        f"   +--------+-------+  +--------+-------+\n"
        f"   | Backend Dev    |  | Frontend Dev   |\n"
        f"   |   {be}          |  |   {fe}          |\n"
        f"   +--------+-------+  +--------+-------+\n"
        f"            |                   |\n"
        f"            +---------+---------+\n"
        f"                      |\n"
        f"         +------------+--------------+\n"
        f"         |    QA Engineer            |  {qa}\n"
        f"         +------------+--------------+\n"
        f"                      |\n"
        f"         +------------+--------------+\n"
        f"         |    Security Auditor       |  {sec}\n"
        f"         +------------+--------------+\n"
        f"                      |\n"
        f"         +------------+--------------+\n"
        f"         |    DevOps Engineer        |  {dv}\n"
        f"         +------------+--------------+\n"
        f"                      |\n"
        f"         +------------+--------------+\n"
        f"         |    Tech Writer            |  {tw}\n"
        f"         +---------------------------+\n"
    )
    console.print(diagram)

    # Status table
    table = Table(title="Estado detallado", box=box.SIMPLE_HEAVY, show_header=True)
    table.add_column("Agente", style="bold")
    table.add_column("Estado", justify="center")

    status_label = {
        "completed": "[green]Completado[/green]",
        "failed":    "[red]Fallido[/red]",
        "running":   "[yellow]En progreso[/yellow]",
        "pending":   "[dim]Pendiente[/dim]",
    }
    for key, name in STEP_NAMES.items():
        s = steps.get(key, "pending")
        table.add_row(name, status_label.get(s, s))

    console.print(table)

    done = sum(1 for s in steps.values() if s == "completed")
    total = len(steps)
    console.print(f"  [bold]Progreso: {done}/{total} pasos completados[/bold]")

    if session.get("error"):
        console.print(f"\n  [red]Ultimo error:[/red] {session['error']}")
    console.print()


# ── Session selection ────────────────────────────────────────────────────────

def _select_session(prompt_text: str) -> "dict | None":
    from src.sessions.manager import list_sessions

    sessions = list_sessions()
    if not sessions:
        console.print("\n[yellow]No hay sesiones guardadas aun.[/yellow]")
        return None

    table = Table(title="Sesiones guardadas", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan")
    table.add_column("Requerimiento")
    table.add_column("Progreso", justify="center")
    table.add_column("Estado", justify="center")

    for i, s in enumerate(sessions, 1):
        done  = sum(1 for v in s["steps"].values() if v == "completed")
        total = len(s["steps"])
        any_failed = any(v == "failed" for v in s["steps"].values())
        if done == total:
            estado = "[green]Completo[/green]"
        elif any_failed:
            estado = "[red]Fallido[/red]"
        else:
            estado = "[yellow]Incompleto[/yellow]"
        req_short = s["requirement"][:50] + ("..." if len(s["requirement"]) > 50 else "")
        table.add_row(str(i), s["id"], req_short, f"{done}/{total}", estado)

    console.print(table)
    choice = IntPrompt.ask(f"\n{prompt_text} (0 para cancelar)", default=0)
    if choice == 0 or choice > len(sessions):
        return None
    return sessions[choice - 1]


# ── Run helpers ──────────────────────────────────────────────────────────────

def _run_pipeline_safe(session: dict) -> None:
    """Ejecuta el pipeline y maneja errores mostrando como reanudar."""
    from src.crews.dev_crew import run as run_pipeline
    try:
        started_at = time.monotonic()
        with Live(
            _pipeline_board(session, started_at),
            console=console,
            refresh_per_second=4,
            screen=True,
            transient=True,
        ) as live:
            run_pipeline(
                session["requirement"],
                session["language"],
                session,
                progress_callback=lambda _step, _status: live.update(
                    _pipeline_board(session, started_at)
                ),
            )
        done = sum(1 for s in session["steps"].values() if s == "completed")
        if done == len(session["steps"]):
            display_complete(session["output_dir"])
        else:
            console.print(
                f"\n[yellow]Pipeline detenido. Sesion guardada: "
                f"[bold]{session['id']}[/bold][/yellow]"
            )
    except Exception as exc:
        _show_error(exc)
        console.print(
            f"\n[yellow]Sesion guardada. Usa 'Continuar sesion' para reanudar: "
            f"[bold]{session['id']}[/bold][/yellow]"
        )


def run_new(requirement: str, output_language: str) -> None:
    from src.sessions.manager import create_session, save_session

    os.environ["OUTPUT_LANGUAGE"] = output_language
    session = create_session(requirement, output_language)
    save_session(session)
    provider = os.getenv("OPENAI_PROVIDER", "groq")
    display_start(requirement, output_language, provider)
    _run_pipeline_safe(session)


def run_continue(session: dict) -> None:
    os.environ["OUTPUT_LANGUAGE"] = session["language"]
    os.environ["OPENAI_PROVIDER"] = session.get("provider", os.getenv("OPENAI_PROVIDER", "groq"))
    os.environ["OPENAI_MODEL"] = session.get("model", os.getenv("OPENAI_MODEL", "gpt-4o"))
    os.environ["OPENAI_BASE_URL"] = session.get("openai_base_url", os.getenv("OPENAI_BASE_URL", "")) or ""
    os.environ["LOW_COST_MODE"] = "1" if session.get("low_cost", False) else "0"

    console.print(f"\n[bold cyan]Reanudando sesion: {session['id']}[/bold cyan]")
    provider = os.getenv("OPENAI_PROVIDER", "groq")
    display_start(session["requirement"], session["language"], provider)
    _run_pipeline_safe(session)


def open_project() -> None:
    """Pide la ruta de un proyecto externo, lo escanea, lo analiza y entra en modo consulta."""
    from pathlib import Path
    from src.crews.dev_crew import analyze_external_project, ask_about_project

    console.print()
    folder_raw = Prompt.ask(
        "[bold yellow]Ruta de la carpeta raiz del proyecto[/bold yellow]\n"
        "  (ejemplo: C:\\Users\\yo\\mi-proyecto)"
    )
    folder_path = folder_raw.strip().strip('"').strip("'")

    if not Path(folder_path).is_dir():
        console.print(f"[red]La carpeta no existe o no es accesible: {folder_path}[/red]")
        return

    lang = os.getenv("OUTPUT_LANGUAGE", "espanol")

    console.print(Panel(
        f"Leyendo archivos de:\n[cyan]{folder_path}[/cyan]\n\n"
        "Esto puede tomar unos segundos...",
        title="Abriendo proyecto externo",
        border_style="cyan",
    ))

    try:
        session, analysis = analyze_external_project(folder_path, lang)
    except Exception as exc:
        _show_error(exc)
        return

    console.print()
    console.print(Panel(
        analysis[:900] + ("...\n\n[dim](analisis completo en 00_project_analysis.md)[/dim]"
                          if len(analysis) > 900 else ""),
        title="Analisis inicial del proyecto",
        border_style="green",
    ))

    # Modo consulta interactiva
    console.print(Panel(
        "Ahora puedes preguntarme cualquier cosa sobre este proyecto.\n"
        "Ejemplos: ¿como mejoro la seguridad? / ¿que falta para produccion?\n"
        "[dim]Deja en blanco, escribe 'menu' o un numero del menu (1-6) para volver.[/dim]",
        title="Modo consulta",
        border_style="cyan",
    ))

    _MENU_EXITS = {"", "menu", "salir", "exit", "volver", "1", "2", "3", "4", "5", "6", "7"}

    while True:
        question = Prompt.ask("\n[bold yellow]Pregunta[/bold yellow]")
        if question.strip().lower() in _MENU_EXITS:
            break
        try:
            answer = ask_about_project(session, question.strip())
            console.print(Panel(answer, title="Technical Lead", border_style="magenta"))
        except Exception as exc:
            _show_error(exc)


def lead_review(session: dict) -> None:
    """Ejecuta el Technical Lead para revisar todos los entregables y tomar el liderazgo."""
    from src.crews.dev_crew import run_lead

    done = sum(1 for s in session["steps"].values() if s == "completed")
    if done == 0:
        console.print("\n[yellow]Esta sesion no tiene entregables aun. Ejecuta el pipeline primero.[/yellow]")
        return

    console.print()
    console.print(Panel(
        f"[bold]Proyecto:[/bold] {session['requirement']}\n\n"
        f"El Technical Lead revisara los [bold]{done}[/bold] entregable(s) disponibles\n"
        f"y emitira directivas para el equipo.",
        title="Technical Lead - Tomando el liderazgo",
        border_style="magenta",
    ))

    try:
        review = run_lead(session)
        console.print()
        console.print(Panel(
            f"[bold magenta]Revision guardada en:[/bold magenta]\n"
            f"  [cyan]{session['output_dir']}/00_lead_review.md[/cyan]\n\n"
            f"[bold]Vista previa:[/bold]\n{review[:600]}{'...' if len(review) > 600 else ''}",
            title="Lead Review completada",
            border_style="magenta",
        ))
    except Exception as exc:
        _show_error(exc)


# ── Main menu ────────────────────────────────────────────────────────────────

def show_usage_guide() -> None:
    """Muestra una guia paso a paso para usar el proyecto con un ejemplo Hello World con efectos."""
    guide = (
        "[bold]Modo de uso: paso a paso[/bold]\n\n"
        "1. Asegurate de tener un entorno Python activo y las dependencias instaladas:\n"
        "   python -m pip install -r requirements.txt\n\n"
        "2. Configura tu .env con la API key y el proveedor, por ejemplo con Groq:\n"
        "   OPENAI_API_KEY=gsk_...\n"
        "   OPENAI_BASE_URL=https://api.groq.com/openai/v1\n"
        "   OPENAI_MODEL=openai/gpt-oss-120b\n"
        "   OPENAI_PROVIDER=groq\n\n"
        "3. Ejecuta este ejemplo con bajo costo usando Groq:\n"
        "   python main.py --req \"Hello World con efectos animados en una app web\" "
        "--provider groq --low-cost --lang espanol\n\n"
        "4. El proyecto creara una sesion y generara los entregables en la carpeta [cyan]output/[/cyan].\n"
        "   Revisa especialmente estos archivos:\n"
        "   - output/01_plan_tecnico.md\n"
        "   - output/02_backend_code.md\n"
        "   - output/03_frontend_code.md\n\n"
        "5. Si quieres repetir el ejemplo, selecciona \"Nuevo proyecto\" en el menu.\n"
        "   Copia este prompt exacto:\n\n"
        "   \"Crea un proyecto web simple que muestre un \"Hello World\" con efectos visuales, animaciones suaves, y un boton que cambia el color de fondo. Entregame el plan tecnico, backend, frontend y documentacion.\"\n\n"
        "6. Para reanudar una sesion existente, usa la opcion \"Continuar sesion guardada\".\n\n"
        "[bold]Consejo:[/bold] Si quieres gastar aun menos tokens, mantén el prompt claro y directo, y usa --low-cost."
    )
    console.print(Panel(guide, title="Guia de uso", border_style="blue", width=90))


def show_main_menu(output_language: str) -> None:
    while True:
        console.print()
        console.print(Panel(
            "[bold]1.[/bold]  Empezar un proyecto\n"
            "[bold]2.[/bold]  Continuar donde lo dejamos\n"
            "[bold]3.[/bold]  Ver el avance de un proyecto\n"
            "[bold]4.[/bold]  Consultar un proyecto existente\n"
            "[bold]5.[/bold]  Pedir una revisión final\n"
            "[bold]6.[/bold]  Cómo funciona\n"
            "[bold]7.[/bold]  Salir",
            title="¿Qué te gustaría hacer?",
            border_style="cyan",
            width=46,
        ))
        choice = Prompt.ask(
            "[bold yellow]Elige una opcion[/bold yellow]",
            choices=["1", "2", "3", "4", "5", "6", "7"],
            default="1",
        )

        if choice == "1":
            req = Prompt.ask("\n[bold yellow]Describe el proyecto a desarrollar[/bold yellow]")
            if req.strip():
                run_new(req.strip(), output_language)

        elif choice == "2":
            session = _select_session("Elige el numero de sesion a continuar")
            if session:
                run_continue(session)

        elif choice == "3":
            session = _select_session("Elige el numero de sesion para ver el diagrama")
            if session:
                show_flowchart(session)

        elif choice == "4":
            open_project()

        elif choice == "5":
            session = _select_session("Elige el numero de sesion para la revision del Lead")
            if session:
                lead_review(session)

        elif choice == "6":
            show_usage_guide()

        elif choice == "7":
            console.print("[dim]Hasta luego.[/dim]")
            break


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Equipo de desarrollo multi-agente IA")
    parser.add_argument(
        "--req", "--requirement", type=str, default=None, dest="req",
        help="Requerimiento del proyecto (omite para menu interactivo)",
    )
    parser.add_argument(
        "--lang", type=str, default=None,
        help="Idioma de salida: espanol | english",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="Proveedor de IA: groq | openai | ollama",
    )
    parser.add_argument(
        "--low-cost", action="store_true",
        help="Usar un modelo de IA de menor costo",
    )
    parser.add_argument(
        "--usage", action="store_true",
        help="Mostrar el modo de uso paso a paso y salir",
    )
    args = parser.parse_args()

    console.print(Text(BANNER, style="bold cyan"))
    if args.usage:
        show_usage_guide()
        return

    low_cost = args.low_cost or os.getenv("LOW_COST_MODE", "0") == "1"
    provider = configure_provider(args.provider, low_cost=low_cost)
    check_env()

    output_language = args.lang or os.getenv("OUTPUT_LANGUAGE", "espanol")

    if args.req:
        # Modo directo: sin menu
        run_new(args.req.strip(), output_language)
    else:
        # Modo interactivo: mostrar menu
        show_main_menu(output_language)