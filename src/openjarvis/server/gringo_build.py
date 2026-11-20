"""Gringo-Werkstatt: Gringo AI lässt Claude neue Funktionen bauen.

Ablauf (immer mit Bestätigung durch den Nutzer):

1. ``POST /v1/gringo/build``            – Auftrag annehmen. Claude arbeitet in einer
   separaten Kopie (git worktree) und darf dort nur Dateien lesen/schreiben.
2. ``POST /v1/gringo/build/{id}/apply``  – Nutzer sagt OK: Änderungen werden in den
   Hauptstand übernommen, zu GitHub hochgeladen und Gringo AI startet neu.
3. ``POST /v1/gringo/build/{id}/discard`` – Nutzer sagt Nein: Kopie wird verworfen.

Benötigt einen Anthropic-API-Schlüssel (Cloud Models → Anthropic).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from openjarvis.core.paths import get_config_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/gringo/build", tags=["gringo-build"])

# Exit code that tells scripts/gringo-start.command to restart the backend.
RESTART_EXIT_CODE = 42
_BUILD_TIMEOUT_S = 1200
_LOCK = threading.Lock()

_SYSTEM_PROMPT = """\
Du arbeitest am Projekt "Gringo AI", einem persönlichen, lokal laufenden
KI-Assistenten (ein Fork von OpenJarvis). Backend: Python in src/openjarvis,
Oberfläche: React/TypeScript in frontend/src. Der Besitzer ist kein
Programmierer und spricht Deutsch.

Regeln:
- Setze genau den Auftrag um, mit möglichst kleinen, sauberen Änderungen.
- Bestehende Funktionen dürfen nicht kaputtgehen. Lies relevante Dateien,
  bevor du sie änderst.
- Führe KEINE git-Befehle aus (kein commit, push, merge) – das erledigt
  Gringo AI nach der Freigabe durch den Nutzer.
- Lege keine Geheimnisse/API-Schlüssel in Dateien ab.
- Antworte am Ende mit einer kurzen Zusammenfassung auf Deutsch in
  einfachen Worten (3–6 Sätze): Was wurde gebaut, wie benutzt man es,
  gibt es etwas zu beachten. Keine Code-Blöcke in der Zusammenfassung.
"""


class BuildRequest(BaseModel):
    task: str


def _repo_root() -> Path:
    import openjarvis

    root = Path(openjarvis.__file__).resolve().parents[2]
    if not (root / ".git").exists():
        raise HTTPException(
            status_code=500,
            detail="Gringo-AI-Projektordner (git) nicht gefunden.",
        )
    return root


def _git(args: List[str], cwd: Path, check: bool = True, timeout: int = 120) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {args[0]} fehlgeschlagen")
    return proc.stdout.strip()


def _anthropic_key() -> str:
    from openjarvis.server.cloud_router import _load_keys

    return _load_keys().get("ANTHROPIC_API_KEY", "")


def _builds(request: Request) -> Dict[str, Dict[str, Any]]:
    builds = getattr(request.app.state, "gringo_builds", None)
    if builds is None:
        builds = {}
        request.app.state.gringo_builds = builds
    return builds


def _cleanup(repo: Path, worktree: str, branch: str) -> None:
    _git(["worktree", "remove", "--force", worktree], repo, check=False)
    shutil.rmtree(worktree, ignore_errors=True)
    _git(["worktree", "prune"], repo, check=False)
    _git(["branch", "-D", branch], repo, check=False)


def _run_build(engine: Any, task: str, api_key: str) -> Dict[str, Any]:
    from openjarvis.agents.claude_code import ClaudeCodeAgent

    repo = _repo_root()
    base = _git(["rev-parse", "HEAD"], repo)
    build_id = uuid.uuid4().hex[:8]
    branch = f"werkstatt-{build_id}"
    worktree = str(get_config_dir() / "gringo-werkstatt" / build_id)
    Path(worktree).parent.mkdir(parents=True, exist_ok=True)
    _git(["worktree", "add", "-b", branch, worktree, base], repo)

    try:
        agent = ClaudeCodeAgent(
            engine,
            "claude",
            api_key=api_key,
            workspace=worktree,
            allowed_tools=["Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "LS"],
            system_prompt=_SYSTEM_PROMPT,
            timeout=_BUILD_TIMEOUT_S,
        )
        result = agent.run(task)
        summary = (getattr(result, "content", "") or "").strip()
        if (getattr(result, "metadata", None) or {}).get("error"):
            raise RuntimeError(summary or "Claude konnte den Auftrag nicht ausführen.")

        _git(["add", "-A"], Path(worktree))
        changed = _git(["status", "--porcelain"], Path(worktree))
        if not changed:
            _cleanup(repo, worktree, branch)
            return {
                "id": build_id,
                "status": "no_changes",
                "summary": summary or "Claude hat keine Änderungen vorgenommen.",
                "files": [],
            }

        _git(
            [
                "-c", "user.name=Gringo AI Werkstatt",
                "-c", "user.email=gringo-ai@users.noreply.github.com",
                "commit", "-q", "-m", f"Gringo-Werkstatt: {task[:72]}\n\n{summary[:2000]}",
            ],
            Path(worktree),
        )
        files = _git(["diff", "--stat", "--stat-width=100", base, "HEAD"], Path(worktree)).splitlines()
        return {
            "id": build_id,
            "status": "ready",
            "summary": summary,
            "files": files,
            "_branch": branch,
            "_worktree": worktree,
            "_base": base,
        }
    except Exception:
        _cleanup(repo, worktree, branch)
        raise


@router.post("")
async def start_build(body: BuildRequest, request: Request):
    task = body.task.strip()
    if not task:
        raise HTTPException(status_code=400, detail="Kein Auftrag angegeben.")
    api_key = _anthropic_key()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "Kein Anthropic-API-Schlüssel hinterlegt. Bitte unter ⌘K → "
                "„Cloud Models“ → Anthropic eintragen."
            ),
        )
    if shutil.which("node") is None:
        raise HTTPException(status_code=500, detail="Node.js fehlt (brew install node).")
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Es läuft schon ein Bauauftrag.")
    try:
        engine = getattr(request.app.state, "engine", None)
        data = await asyncio.to_thread(_run_build, engine, task, api_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Gringo build failed")
        raise HTTPException(status_code=500, detail=f"Bauauftrag fehlgeschlagen: {exc}") from exc
    finally:
        _LOCK.release()

    if data["status"] == "ready":
        _builds(request)[data["id"]] = data
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _schedule_restart() -> bool:
    if os.environ.get("GRINGO_SUPERVISED") != "1":
        return False

    def _exit_later() -> None:
        time.sleep(1.5)
        os._exit(RESTART_EXIT_CODE)

    threading.Thread(target=_exit_later, daemon=True).start()
    return True


@router.post("/{build_id}/apply")
async def apply_build(build_id: str, request: Request):
    build = _builds(request).pop(build_id, None)
    if build is None:
        raise HTTPException(status_code=404, detail="Bauauftrag nicht gefunden.")
    repo = _repo_root()

    def _apply() -> Dict[str, Any]:
        if _git(["status", "--porcelain", "--untracked-files=no"], repo):
            raise RuntimeError(
                "Im Gringo-AI-Ordner gibt es ungespeicherte Änderungen – "
                "Übernahme abgebrochen."
            )
        _git(["merge", "--ff-only", build["_branch"]], repo)
        _cleanup(repo, build["_worktree"], build["_branch"])
        pushed = subprocess.run(
            ["git", "push", "-q"], cwd=str(repo), capture_output=True, text=True, timeout=120
        ).returncode == 0
        return {"pushed": pushed}

    try:
        result = await asyncio.to_thread(_apply)
    except Exception as exc:
        _builds(request)[build_id] = build  # allow retry / discard
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    restarting = _schedule_restart()
    return {"status": "applied", "pushed": result["pushed"], "restarting": restarting}


@router.post("/{build_id}/discard")
async def discard_build(build_id: str, request: Request):
    build = _builds(request).pop(build_id, None)
    if build is None:
        raise HTTPException(status_code=404, detail="Bauauftrag nicht gefunden.")
    await asyncio.to_thread(_cleanup, _repo_root(), build["_worktree"], build["_branch"])
    return {"status": "discarded"}


@router.get("/status")
async def build_status():
    return {
        "anthropic_key": bool(_anthropic_key()),
        "node": shutil.which("node") is not None,
        "busy": _LOCK.locked(),
    }
