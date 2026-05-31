"""Unit tests for create command interactive mode."""

from __future__ import annotations

from pathlib import Path

import pytest
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
        uid: str,
        broker: str,
        nosql: tuple[str, ...],
    ) -> None:
        calls["copy_template"] = {
            "destination": destination,
            "orm": orm_type,
            "design": design,
            "name": name,
            "package_manager": package_manager,
            "uid": uid,
            "broker": broker,
            "nosql": nosql,
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


def test_create_interactive_uses_selected_values(
    monkeypatch, tmp_path
) -> None:
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
            uid="sparkid",
            broker="kafka",
            nosql=("mongodb", "neo4j"),
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
        "uid": "sparkid",
        "broker": "kafka",
        "nosql": ("mongodb", "neo4j"),
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
            "--uid",
            "sparkid",
            "--broker",
            "rabbitmq",
            "--nosql",
            "mongodb",
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
    assert defaults.uid == "sparkid"
    assert defaults.broker == "rabbitmq"
    assert defaults.nosql == ("mongodb",)
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


def test_create_accepts_explicit_no_broker_like_uid(
    monkeypatch, tmp_path
) -> None:
    runner = CliRunner()
    calls = _stub_create_pipeline(monkeypatch)
    destination = tmp_path / "no-broker-project"

    result = runner.invoke(
        cli_module.cli,
        ["create", "no-broker-app", "--broker", "none", str(destination)],
    )

    assert result.exit_code == 0, result.output
    assert calls["copy_template"]["broker"] == "none"  # type: ignore[index]


def test_create_accepts_explicit_no_nosql_like_uid(
    monkeypatch, tmp_path
) -> None:
    runner = CliRunner()
    calls = _stub_create_pipeline(monkeypatch)
    destination = tmp_path / "no-nosql-project"

    result = runner.invoke(
        cli_module.cli,
        ["create", "no-nosql-app", "--nosql", "none", str(destination)],
    )

    assert result.exit_code == 0, result.output
    assert calls["copy_template"]["nosql"] == ()  # type: ignore[index]


@pytest.mark.parametrize(
    "nosql_args",
    [
        ["--nosql", "mongodb,neo4j"],
        ["--nosql", "mongodb", "--nosql", "neo4j"],
        ["--nosql", "neo4j", "--nosql", "mongodb", "--nosql", "neo4j"],
    ],
)
def test_create_accepts_multiple_nosql_providers(
    monkeypatch, tmp_path, nosql_args
) -> None:
    runner = CliRunner()
    calls = _stub_create_pipeline(monkeypatch)
    destination = tmp_path / "multi-nosql-project"

    result = runner.invoke(
        cli_module.cli,
        ["create", "multi-nosql-app", *nosql_args, str(destination)],
    )

    assert result.exit_code == 0, result.output
    assert calls["copy_template"]["nosql"] == (  # type: ignore[index]
        "mongodb",
        "neo4j",
    )


@pytest.mark.parametrize(
    ("nosql_value", "message"),
    [
        ("none,mongodb", "'none' cannot be combined"),
        ("redis", "Unsupported NoSQL provider 'redis'"),
    ],
)
def test_create_rejects_invalid_nosql_selection(
    monkeypatch, nosql_value, message
) -> None:
    runner = CliRunner()
    _stub_create_pipeline(monkeypatch)

    result = runner.invoke(
        cli_module.cli,
        ["create", "invalid-nosql-app", "--nosql", nosql_value],
    )

    assert result.exit_code != 0
    assert message in result.output


def test_create_help_contains_interactive_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["create", "--help"])
    assert result.exit_code == 0
    assert "-i, --interactive" in result.output
    assert "-uid, --uid" in result.output
    assert "-broker, --broker" in result.output
    assert "-nosql, --nosql" in result.output


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


def test_create_rejects_uuidv7_on_python_older_than_313(monkeypatch) -> None:
    runner = CliRunner()
    _stub_create_pipeline(monkeypatch)

    monkeypatch.setattr(cli_module.sys, "version_info", (3, 12, 9))

    result = runner.invoke(
        cli_module.cli,
        ["create", "uid-app", "--uid", "uuidv7"],
    )

    assert result.exit_code != 0
    assert "uuidv7 requires Python 3.13 or newer" in result.output


@pytest.mark.skipif(
    not hasattr(
        __import__(
            "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
        ),
        "TEXTUAL_AVAILABLE",
    )
    or not __import__(
        "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
    ).TEXTUAL_AVAILABLE,
    reason="textual not installed",
)
class TestBannerWidget:
    """Tests for the ASCII banner widget."""

    def test_banner_contains_robyn_config_text(self):
        from create.utils._interactive import BannerWidget

        widget = BannerWidget()
        # The banner renderable should contain "Robyn" and "Config"
        text = str(widget.render())
        assert "Robyn" in text or "____" in text


class TestBulletField:
    """Tests for BulletField widget."""

    def test_bullet_field_reports_value(self):
        from create.utils._interactive import BulletField

        field = BulletField(
            label="Project name", field_id="name", placeholder="my-service"
        )
        assert field.field_id == "name"


class TestBulletSelect:
    """Tests for BulletSelect widget."""

    def test_bullet_select_cycles_values(self):
        from create.utils._interactive import BulletSelect

        widget = BulletSelect(
            label="ORM",
            field_id="orm",
            choices=("sqlalchemy", "tortoise"),
            value="sqlalchemy",
        )
        assert widget.value == "sqlalchemy"
        assert widget.field_id == "orm"


class TestBulletToggleList:
    """Tests for the NoSQL multi-select widget."""

    def test_toggle_list_reports_selected_values_in_choice_order(self):
        from create.utils._interactive import BulletToggleList

        widget = BulletToggleList(
            label="NoSQL",
            field_id="nosql",
            choices=("mongodb", "neo4j"),
            value=("neo4j", "mongodb"),
        )

        assert widget.value == ("mongodb", "neo4j")
        assert widget.field_id == "nosql"

    def test_toggle_list_enables_and_disables_providers_independently(self):
        from create.utils._interactive import BulletToggleList

        widget = BulletToggleList(
            label="NoSQL",
            field_id="nosql",
            choices=("mongodb", "neo4j"),
            value=(),
        )

        widget.toggle()
        widget.move(1)
        widget.toggle()
        widget.move(-1)
        widget.toggle()

        assert widget.value == ("neo4j",)


@pytest.mark.skipif(
    not hasattr(
        __import__(
            "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
        ),
        "TEXTUAL_AVAILABLE",
    )
    or not __import__(
        "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
    ).TEXTUAL_AVAILABLE,
    reason="textual not installed",
)
class TestTechnicalScreen:
    """Tests for Stage 2 screen."""

    def test_technical_screen_exists(self):
        from create.utils._interactive import TechnicalScreen

        screen = TechnicalScreen()
        assert screen is not None


@pytest.mark.skipif(
    not hasattr(
        __import__(
            "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
        ),
        "TEXTUAL_AVAILABLE",
    )
    or not __import__(
        "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
    ).TEXTUAL_AVAILABLE,
    reason="textual not installed",
)
class TestIdentityScreen:
    """Tests for Stage 1 screen."""

    def test_identity_screen_exists(self):
        from create.utils._interactive import IdentityScreen

        screen = IdentityScreen()
        assert screen is not None


@pytest.mark.skipif(
    not hasattr(
        __import__(
            "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
        ),
        "TEXTUAL_AVAILABLE",
    )
    or not __import__(
        "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
    ).TEXTUAL_AVAILABLE,
    reason="textual not installed",
)
class TestInteractiveCreateAppScreens:
    """Tests for the rewritten screen-based App."""

    def test_app_initializes_state_from_defaults(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )

        defaults = InteractiveCreateConfig(
            name="test-app",
            destination="/tmp/test",
            orm="tortoise",
            design="mvc",
            package_manager="poetry",
            uid="uuidv4",
            broker="rabbitmq",
            nosql=("neo4j",),
        )
        app = InteractiveCreateApp(defaults)
        assert app.state["name"] == "test-app"
        assert app.state["destination"] == "/tmp/test"
        assert app.state["orm"] == "tortoise"
        assert app.state["design"] == "mvc"
        assert app.state["package_manager"] == "poetry"
        assert app.state["uid"] == "uuidv4"
        assert app.state["broker"] == "rabbitmq"
        assert app.state["nosql"] == ("neo4j",)

    def test_app_normalizes_defaults(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )

        defaults = InteractiveCreateConfig(
            name="  padded  ",
            destination="",
            orm="invalid",
            design="invalid",
            package_manager="invalid",
            uid="invalid",
            broker="invalid",
            nosql=("invalid",),
        )
        app = InteractiveCreateApp(defaults)
        assert app.state["name"] == "padded"
        assert app.state["destination"] == "."
        assert app.state["orm"] == "sqlalchemy"
        assert app.state["design"] == "ddd"
        assert app.state["package_manager"] == "uv"
        assert app.state["uid"] == "none"
        assert app.state["broker"] == "none"
        assert app.state["nosql"] == ()


@pytest.mark.skipif(
    not hasattr(
        __import__(
            "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
        ),
        "TEXTUAL_AVAILABLE",
    )
    or not __import__(
        "create.utils._interactive", fromlist=["TEXTUAL_AVAILABLE"]
    ).TEXTUAL_AVAILABLE,
    reason="textual not installed",
)
class TestInteractiveFlow:
    """Integration tests for the full staged wizard flow."""

    @pytest.mark.asyncio
    async def test_full_flow_produces_config(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )

        defaults = InteractiveCreateConfig(
            name="",
            destination=".",
            orm="sqlalchemy",
            design="ddd",
            package_manager="uv",
            uid="none",
            broker="none",
            nosql=(),
        )
        app = InteractiveCreateApp(defaults)

        async with app.run_test(size=(100, 40)) as pilot:
            # Stage 1: type project name
            await pilot.press("t", "e", "s", "t", "-", "a", "p", "p")
            # Press the Next button and wait for TechnicalScreen to appear
            await pilot.click("#next")
            await pilot.pause(delay=0.2)
            # Stage 2: press Create with defaults
            await pilot.click("#create-btn")

        assert isinstance(app.return_value, InteractiveCreateConfig)
        assert app.return_value.name == "test-app"
        assert app.return_value.destination == "."
        assert app.return_value.orm == "sqlalchemy"
        assert app.return_value.broker == "none"
        assert app.return_value.nosql == ()

    @pytest.mark.asyncio
    async def test_cancel_from_stage1_returns_none(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )

        defaults = InteractiveCreateConfig(
            name="",
            destination=".",
            orm="sqlalchemy",
            design="ddd",
            package_manager="uv",
            uid="none",
            broker="none",
            nosql=(),
        )
        app = InteractiveCreateApp(defaults)

        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.click("#cancel")

        assert app.return_value is None

    @pytest.mark.asyncio
    async def test_back_from_stage2_preserves_values(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )

        defaults = InteractiveCreateConfig(
            name="my-app",
            destination="/tmp/test",
            orm="sqlalchemy",
            design="ddd",
            package_manager="uv",
            uid="none",
            broker="redis",
            nosql=("mongodb",),
        )
        app = InteractiveCreateApp(defaults)

        async with app.run_test(size=(100, 40)) as pilot:
            # Stage 1: advance with prefilled values
            await pilot.click("#next")
            # Wait for TechnicalScreen to appear
            await pilot.pause(delay=0.2)
            # Stage 2: go back
            await pilot.click("#back")
            # Wait for IdentityScreen to be restored
            await pilot.pause(delay=0.2)
            # Stage 1 again: name should still be there
            await pilot.click("#next")
            # Wait for TechnicalScreen again
            await pilot.pause(delay=0.2)
            # Stage 2: create
            await pilot.click("#create-btn")

        assert isinstance(app.return_value, InteractiveCreateConfig)
        assert app.return_value.name == "my-app"
        assert app.return_value.destination == "/tmp/test"
        assert app.return_value.broker == "redis"
        assert app.return_value.nosql == ("mongodb",)

    @pytest.mark.asyncio
    async def test_empty_name_shows_error_on_stage1(self):
        from create.utils._interactive import (
            InteractiveCreateApp,
            InteractiveCreateConfig,
        )
        from textual.widgets import Static

        defaults = InteractiveCreateConfig(
            name="",
            destination=".",
            orm="sqlalchemy",
            design="ddd",
            package_manager="uv",
            uid="none",
            broker="none",
            nosql=(),
        )
        app = InteractiveCreateApp(defaults)

        async with app.run_test(size=(100, 40)) as pilot:
            # Try to advance without name
            await pilot.click("#next")
            # Should still be on Stage 1 (error shown, click includes pause)
            error = app.screen.query_one("#error", Static)
            assert "required" in str(error.content).lower()
