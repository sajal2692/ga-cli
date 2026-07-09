from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ga_cli import __version__


def test_skill_install_show_path_lifecycle(invoke: Any, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home)}

    result = invoke("skill", "install", env=env)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    target = Path(data["installed"])
    assert data == {
        "ok": True,
        "installed": str(home / ".claude" / "skills" / "ga-cli"),
        "files": 2,
        "version": __version__,
    }
    assert (target / "SKILL.md").is_file()
    assert (target / "references" / "commands.md").is_file()

    result = invoke("skill", "install", env=env)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"ok": True, "status": "up-to-date"}

    (target / "SKILL.md").write_text("modified\n")
    result = invoke("skill", "install", env=env)
    assert result.exit_code == 2
    assert "--force" in result.stderr
    assert result.stdout == ""

    result = invoke("skill", "install", "--force", env=env)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["files"] == 2
    assert "modified" not in (target / "SKILL.md").read_text()


def test_skill_install_project(
    invoke: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    result = invoke("skill", "install", "--project", env={"HOME": str(tmp_path / "h")})
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["installed"] == str(project / ".claude" / "skills" / "ga-cli")
    assert (project / ".claude" / "skills" / "ga-cli" / "SKILL.md").is_file()


def test_skill_show(invoke: Any) -> None:
    result = invoke("skill", "show")
    assert result.exit_code == 0
    assert result.stdout.startswith("---\nname: ga-cli\n")


def test_skill_path(invoke: Any) -> None:
    result = invoke("skill", "path")
    assert result.exit_code == 0
    path = Path(result.stdout.strip())
    assert (path / "SKILL.md").is_file()
