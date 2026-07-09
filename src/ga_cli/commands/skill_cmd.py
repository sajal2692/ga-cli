from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import click

from ga_cli import __version__, output
from ga_cli.commands import global_options
from ga_cli.errors import CliError, handle_errors


def _bundled_dir() -> Path:
    package_dir = Path(__file__).resolve().parent.parent
    bundled = package_dir / "_skill"
    if bundled.is_dir():
        return bundled
    repo_skill = package_dir.parent.parent / "skills" / "ga-cli"
    if repo_skill.is_dir():
        return repo_skill
    raise CliError("Bundled skill not found in this installation.")


def _files(root: Path) -> list[Path]:
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    )


def _same(source: Path, target: Path) -> bool:
    source_files = _files(source)
    if source_files != _files(target):
        return False
    return all(
        filecmp.cmp(source / path, target / path, shallow=False) for path in source_files
    )


@click.group("skill")
@global_options
def skill_group() -> None:
    """Manage the bundled Claude Code skill."""


@skill_group.command("install")
@click.option("--project", is_flag=True,
              help="Install into ./.claude/skills instead of ~/.claude/skills.")
@click.option("--force", is_flag=True, help="Overwrite an existing install.")
@global_options
@click.pass_context
@handle_errors
def skill_install(ctx: click.Context, project: bool, force: bool) -> None:
    """Install the skill for Claude Code."""
    source = _bundled_dir()
    base = Path.cwd() / ".claude" / "skills" if project else Path.home() / ".claude" / "skills"
    target = base / "ga-cli"
    if target.exists() and not force:
        if _same(source, target):
            output.emit({"ok": True, "status": "up-to-date"})
            return
        raise click.UsageError(
            f"Existing skill at {target} differs from the bundled version. "
            "Re-run with --force to overwrite."
        )
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".*"))
    output.emit(
        {
            "ok": True,
            "installed": str(target),
            "files": len(_files(target)),
            "version": __version__,
        }
    )


@skill_group.command("show")
@global_options
@handle_errors
def skill_show() -> None:
    """Print the bundled SKILL.md."""
    click.echo((_bundled_dir() / "SKILL.md").read_text(), nl=False)


@skill_group.command("path")
@global_options
@handle_errors
def skill_path() -> None:
    """Print the absolute path of the bundled skill directory."""
    click.echo(str(_bundled_dir()))
