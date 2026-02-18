"""Unit tests for create command interactive mode."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

import cli as cli_module
from create import InteractiveCreateConfig


def _stub_create_pipeline(monkeypatch) -> dict[str, object]:
    calls: dict[str, object] = {}

    def fake_ensure_package_manager_available(package_manager: str) -> None:
        calls["package_manager"] = package_manager

    def fake_prepare_destination(
        destination: Path,
        orm_type: str,
        design: str,
        package_manager: str,
    ) -> Path:
        calls["prepare_destination"] = {
            "destination": destination,
            "orm": orm_type,
            "design": design,
            "package_manager": package_manager,
        }
        return destination

    def fake_copy_template(
        destination: Path,
        orm_type: str,
        design: str,
        name: str,
        package_manager: str,
    ) -> None:
        calls["copy_template"] = {
            "destination": destination,
            "orm": orm_type,
            "design": design,
            "name": name,
            "package_manager": package_manager,
        }

    def fake_apply_package_manager(
        destination: Path, package_manager: str
    ) -> None:
        calls["apply_package_manager"] = {
            "destination": destination,
            "package_manager": package_manager,
        }

    monkeypatch.setattr(
        cli_module,
        "ensure_package_manager_available",
        fake_ensure_package_manager_available,
    )
    monkeypatch.setattr(
        cli_module,
        "prepare_destination",
        fake_prepare_destination,
    )
    monkeypatch.setattr(
        cli_module,
        "get_generated_items",
        lambda _orm, _design, _pkg: set(),
    )
    monkeypatch.setattr(
        cli_module,
        "copy_template",
        fake_copy_template,
    )
    monkeypatch.setattr(
        cli_module,
        "apply_package_manager",
        fake_apply_package_manager,
    )
    return calls


def test_create_interactive_uses_selected_values(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    calls = _stub_create_pipeline(monkeypatch)
    interactive_destination = tmp_path / "interactive-project"

    monkeypatch.setattr(
        cli_module, "_interactive_terminal_available", lambda: True
    )
    monkeypatch.setattr(
        cli_module,
        "run_create_interactive",
        lambda _defaults: InteractiveCreateConfig(
            name="interactive-app",
            destination=str(interactive_destination),
            orm="tortoise",
            design="mvc",
            package_manager="poetry",
        ),
    )

    result = runner.invoke(cli_module.cli, ["create", "-i"])

    assert result.exit_code == 0, result.output
    assert calls["package_manager"] == "poetry"
    assert calls["prepare_destination"] == {
        "destination": interactive_destination,
        "orm": "tortoise",
        "design": "mvc",
        "package_manager": "poetry",
    }
    assert calls["copy_template"] == {
        "destination": interactive_destination,
        "orm": "tortoise",
        "design": "mvc",
        "name": "interactive-app",
        "package_manager": "poetry",
    }


def test_create_interactive_prefills_from_cli_inputs(
    monkeypatch, tmp_path
) -> None:
    runner = CliRunner()
    calls = _stub_create_pipeline(monkeypatch)
    captured_defaults: dict[str, InteractiveCreateConfig] = {}
    destination = tmp_path / "seed-project"

    monkeypatch.setattr(
        cli_module, "_interactive_terminal_available", lambda: True
    )

    def fake_run_create_interactive(
        defaults: InteractiveCreateConfig,
    ) -> InteractiveCreateConfig:
        captured_defaults["defaults"] = defaults
        return defaults

    monkeypatch.setattr(
        cli_module, "run_create_interactive", fake_run_create_interactive
    )

    result = runner.invoke(
        cli_module.cli,
        [
            "create",
            "-i",
            "--orm",
            "tortoise",
            "--design",
            "mvc",
            "--package-manager",
            "poetry",
            "seed-name",
            str(destination),
        ],
    )

    assert result.exit_code == 0, result.output
    defaults = captured_defaults["defaults"]
    assert defaults.name == "seed-name"
    assert defaults.destination == str(destination)
    assert defaults.orm == "tortoise"
    assert defaults.design == "mvc"
    assert defaults.package_manager == "poetry"
    assert calls["prepare_destination"] == {
        "destination": destination,
        "orm": "tortoise",
        "design": "mvc",
        "package_manager": "poetry",
    }


def test_create_interactive_cancelled(monkeypatch) -> None:
    runner = CliRunner()
    was_called = {"prepare_destination": False}

    monkeypatch.setattr(
        cli_module, "_interactive_terminal_available", lambda: True
    )
    monkeypatch.setattr(cli_module, "run_create_interactive", lambda _: None)

    def fake_prepare_destination(
        _destination: Path, _orm: str, _design: str, _package_manager: str
    ) -> Path:
        was_called["prepare_destination"] = True
        return Path(".")

    monkeypatch.setattr(
        cli_module, "prepare_destination", fake_prepare_destination
    )

    result = runner.invoke(cli_module.cli, ["create", "-i"])

    assert result.exit_code != 0
    assert "Create command cancelled." in result.output
    assert not was_called["prepare_destination"]


def test_create_without_name_non_interactive_fails() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["create"])
    assert result.exit_code != 0
    assert "Missing argument 'NAME'." in result.output


def test_create_help_contains_interactive_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["create", "--help"])
    assert result.exit_code == 0
    assert "-i, --interactive" in result.output


def test_create_interactive_requires_tty(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        cli_module, "_interactive_terminal_available", lambda: False
    )
    monkeypatch.setattr(
        cli_module,
        "run_create_interactive",
        lambda _: (_ for _ in ()).throw(RuntimeError("should not run")),
    )

    result = runner.invoke(cli_module.cli, ["create", "-i"])

    assert result.exit_code != 0
    assert "Interactive mode requires a TTY terminal." in result.output
