"""Interactive create-mode UI powered by Textual."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ._config import (
    DESIGN_CHOICES,
    INTERACTIVE_BROKER_CHOICES,
    INTERACTIVE_NOSQL_CHOICES,
    ORM_CHOICES,
    PACKAGE_MANAGER_CHOICES,
    UID_CHOICES,
    _normalize_nosql,
)

TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

try:
    from textual import events
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.screen import Screen
    from textual.widgets import Button, Input, Static

    TEXTUAL_AVAILABLE = True
except ModuleNotFoundError as exc:
    if exc.name != "textual":
        raise
    TEXTUAL_AVAILABLE = False
    TEXTUAL_IMPORT_ERROR = exc


def _pick_choice(value: str, choices: Sequence[str]) -> str:
    normalized = value.lower().strip()
    return normalized if normalized in choices else choices[0]


def _pick_nosql(values: Sequence[str]) -> tuple[str, ...]:
    try:
        return _normalize_nosql(values)
    except ValueError:
        return ()


@dataclass(frozen=True, slots=True)
class InteractiveCreateConfig:
    """Collected values from interactive create mode."""

    name: str
    destination: str
    orm: str
    design: str
    package_manager: str
    uid: str
    broker: str
    nosql: tuple[str, ...]


if TEXTUAL_AVAILABLE:

    BANNER_ART = r"""
 ____       _                     ____             __ _
|  _ \ ___ | |__  _   _ _ __    / ___|___  _ __  / _(_) __ _
| |_) / _ \| '_ \| | | | '_ \  | |   / _ \| '_ \| |_| |/ _` |
|  _ < (_) | |_) | |_| | | | | | |__| (_) | | | |  _| | (_| |
|_| \_\___/|_.__/ \__, |_| |_|  \____\___/|_| |_|_| |_|\__, |
                  |___/                                  |___/"""

    class BannerWidget(Static):
        """ASCII art banner displayed at the top of each stage."""

        def render(self) -> str:
            return BANNER_ART

    class StepIndicator(Static):
        """Step N of M — Title indicator."""

        def __init__(
            self, step: int, total: int, title: str, **kwargs
        ) -> None:
            super().__init__(**kwargs)
            self.step = step
            self.total = total
            self.title = title

        def render(self) -> str:
            return f"Step {self.step} of {self.total} — {self.title}"

    class BulletField(Horizontal):
        """A colored bullet + label + Input widget for text entry."""

        DEFAULT_CSS = """
        BulletField {
            height: 3;
            margin-bottom: 1;
        }
        BulletField .bullet {
            width: 3;
            color: #394558;
            padding-top: 1;
        }
        BulletField .bullet.filled {
            color: #2b7f5a;
        }
        BulletField .field-label {
            width: 18;
            color: #a6b3c7;
            padding-top: 1;
        }
        BulletField Input {
            width: 1fr;
            background: #0a0f16;
            color: #f5f8ff;
            border: round #394558;
        }
        BulletField Input:focus {
            border: round #2b7f5a;
        }
        """

        def __init__(
            self,
            label: str,
            field_id: str,
            placeholder: str = "",
            value: str = "",
        ) -> None:
            super().__init__()
            self.field_id = field_id
            self._label_text = label
            self._placeholder = placeholder
            self._initial_value = value

        def compose(self) -> ComposeResult:
            yield Static("○", classes="bullet")
            yield Static(self._label_text, classes="field-label")
            yield Input(
                value=self._initial_value,
                placeholder=self._placeholder,
                id=self.field_id,
            )

        def on_input_changed(self, event: Input.Changed) -> None:
            bullet = self.query_one(".bullet", Static)
            if event.value.strip():
                bullet.update("●")
                bullet.add_class("filled")
            else:
                bullet.update("○")
                bullet.remove_class("filled")

        @property
        def value(self) -> str:
            return self.query_one(Input).value.strip()

    class BulletSelect(Horizontal):
        """A colored bullet + label + cycling value display for selection fields."""

        can_focus = True

        DEFAULT_CSS = """
        BulletSelect {
            height: 3;
            margin-bottom: 1;
            padding: 1;
        }
        BulletSelect:focus {
            background: #161d27;
        }
        BulletSelect .bullet {
            width: 3;
            color: #2b7f5a;
        }
        BulletSelect .field-label {
            width: 18;
            color: #a6b3c7;
        }
        BulletSelect .field-value {
            width: 1fr;
            color: #f5f8ff;
        }
        BulletSelect:focus .field-value {
            color: #2b7f5a;
            text-style: bold;
        }
        BulletSelect .hint {
            width: auto;
            color: #394558;
        }
        BulletSelect:focus .hint {
            color: #91a0b8;
        }
        """

        def __init__(
            self,
            label: str,
            field_id: str,
            choices: Sequence[str],
            value: str,
        ) -> None:
            super().__init__()
            self.field_id = field_id
            self._label_text = label
            self._choices = list(choices)
            self._index = (
                self._choices.index(value) if value in self._choices else 0
            )

        def compose(self) -> ComposeResult:
            yield Static("●", classes="bullet")
            yield Static(self._label_text, classes="field-label")
            yield Static(self._choices[self._index], classes="field-value")
            yield Static("↵ cycle", classes="hint")

        @property
        def value(self) -> str:
            return self._choices[self._index]

        def cycle(self) -> None:
            self._index = (self._index + 1) % len(self._choices)
            self.query_one(".field-value", Static).update(
                self._choices[self._index]
            )

        def on_key(self, event: events.Key) -> None:
            if event.key == "enter":
                self.cycle()
                event.prevent_default()
                event.stop()

    class BulletToggleList(Vertical):
        """A label and independently toggled list of infrastructure options."""

        can_focus = True

        DEFAULT_CSS = """
        BulletToggleList {
            height: auto;
            margin-bottom: 1;
            padding: 0 1;
        }
        BulletToggleList:focus {
            background: #161d27;
        }
        BulletToggleList .field-label {
            color: #a6b3c7;
        }
        BulletToggleList .field-values {
            color: #f5f8ff;
        }
        BulletToggleList:focus .field-values {
            color: #2b7f5a;
            text-style: bold;
        }
        """

        def __init__(
            self,
            label: str,
            field_id: str,
            choices: Sequence[str],
            value: Sequence[str],
        ) -> None:
            super().__init__()
            self.field_id = field_id
            self._label_text = label
            self._choices = tuple(choices)
            self._selected = set(value) & set(self._choices)
            self._index = 0

        def compose(self) -> ComposeResult:
            yield Static(
                f"{self._label_text}  ↑↓ move  ↵ toggle",
                classes="field-label",
            )
            yield Static(self._render_values(), classes="field-values")

        @property
        def value(self) -> tuple[str, ...]:
            return tuple(
                choice for choice in self._choices if choice in self._selected
            )

        def _render_values(self) -> str:
            rows = []
            for index, choice in enumerate(self._choices):
                cursor = "›" if index == self._index else " "
                marker = "x" if choice in self._selected else " "
                rows.append(f"{cursor} [{marker}] {choice}")
            return "\n".join(rows)

        def _refresh(self) -> None:
            values = self.query(".field-values")
            if values:
                values.first(Static).update(self._render_values())

        def move(self, offset: int) -> None:
            self._index = (self._index + offset) % len(self._choices)
            self._refresh()

        def toggle(self) -> None:
            choice = self._choices[self._index]
            if choice in self._selected:
                self._selected.remove(choice)
            else:
                self._selected.add(choice)
            self._refresh()

        def on_key(self, event: events.Key) -> None:
            if event.key == "up":
                self.move(-1)
            elif event.key == "down":
                self.move(1)
            elif event.key in {"enter", "space"}:
                self.toggle()
            else:
                return
            event.prevent_default()
            event.stop()

    class TechnicalScreen(Screen):
        """Stage 2: ORM, design pattern, package manager, UID, broker."""

        BINDINGS = [
            ("escape", "go_back", "Back"),
            ("ctrl+c", "cancel", "Cancel"),
        ]

        DEFAULT_CSS = """
        TechnicalScreen {
            align: center middle;
        }
        TechnicalScreen #shell {
            width: 80;
            max-width: 98%;
            height: auto;
            max-height: 100%;
            border: round #313846;
            background: #10151c;
            padding: 1 2;
        }
        TechnicalScreen #banner {
            color: #f5a623;
            text-align: center;
            margin-bottom: 1;
        }
        TechnicalScreen #step {
            color: #91a0b8;
            margin-bottom: 1;
        }
        TechnicalScreen #actions {
            margin-top: 1;
            align-horizontal: right;
            height: auto;
        }
        TechnicalScreen #back {
            background: #232b36;
            color: #d5dbe3;
        }
        TechnicalScreen #create-btn {
            background: #2b7f5a;
            color: #f5f8ff;
            text-style: bold;
        }
        TechnicalScreen Button {
            margin-left: 1;
            min-width: 10;
        }
        """

        def compose(self) -> ComposeResult:
            app = self.app
            assert isinstance(app, InteractiveCreateApp)
            yield Vertical(
                BannerWidget(id="banner"),
                StepIndicator(2, 2, "Technical Choices", id="step"),
                BulletSelect(
                    label="ORM",
                    field_id="orm",
                    choices=ORM_CHOICES,
                    value=app.state["orm"],
                ),
                BulletSelect(
                    label="Design",
                    field_id="design",
                    choices=DESIGN_CHOICES,
                    value=app.state["design"],
                ),
                BulletSelect(
                    label="Package manager",
                    field_id="package_manager",
                    choices=PACKAGE_MANAGER_CHOICES,
                    value=app.state["package_manager"],
                ),
                BulletSelect(
                    label="UID",
                    field_id="uid",
                    choices=UID_CHOICES,
                    value=app.state["uid"],
                ),
                BulletSelect(
                    label="Broker",
                    field_id="broker",
                    choices=INTERACTIVE_BROKER_CHOICES,
                    value=app.state["broker"],
                ),
                BulletToggleList(
                    label="NoSQL",
                    field_id="nosql",
                    choices=INTERACTIVE_NOSQL_CHOICES,
                    value=app.state["nosql"],
                ),
                Horizontal(
                    Button("← Back", id="back"),
                    Button("Create", id="create-btn"),
                    id="actions",
                ),
                id="shell",
            )

        def on_mount(self) -> None:
            selects = self.query("BulletSelect")
            if selects:
                selects.first().focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self._save_and_go_back()
            elif event.button.id == "create-btn":
                self._submit()

        def action_go_back(self) -> None:
            self._save_and_go_back()

        def action_cancel(self) -> None:
            self.app.exit(None)

        def _save_and_go_back(self) -> None:
            self._save_state()
            self.app.pop_screen()

        def _save_state(self) -> None:
            app = self.app
            assert isinstance(app, InteractiveCreateApp)
            for select in self.query("BulletSelect"):
                assert isinstance(select, BulletSelect)
                app.state[select.field_id] = select.value
            nosql = self.query_one("BulletToggleList", BulletToggleList)
            app.state[nosql.field_id] = nosql.value

        def _submit(self) -> None:
            self._save_state()
            app = self.app
            assert isinstance(app, InteractiveCreateApp)
            app.exit(
                InteractiveCreateConfig(
                    name=app.state["name"],
                    destination=app.state["destination"],
                    orm=app.state["orm"],
                    design=app.state["design"],
                    package_manager=app.state["package_manager"],
                    uid=app.state["uid"],
                    broker=app.state["broker"],
                    nosql=app.state["nosql"],
                )
            )

    class IdentityScreen(Screen):
        """Stage 1: Project name and destination."""

        BINDINGS = [
            ("escape", "cancel", "Cancel"),
            ("ctrl+c", "cancel", "Cancel"),
        ]

        DEFAULT_CSS = """
        IdentityScreen {
            align: center middle;
        }
        IdentityScreen #shell {
            width: 80;
            max-width: 98%;
            height: auto;
            max-height: 100%;
            border: round #313846;
            background: #10151c;
            padding: 1 2;
        }
        IdentityScreen #banner {
            color: #f5a623;
            text-align: center;
            margin-bottom: 1;
        }
        IdentityScreen #step {
            color: #91a0b8;
            margin-bottom: 1;
        }
        IdentityScreen #error {
            color: #ff7f7f;
            min-height: 1;
            margin-top: 1;
        }
        IdentityScreen #actions {
            margin-top: 1;
            align-horizontal: right;
            height: auto;
        }
        IdentityScreen #cancel {
            background: #232b36;
            color: #d5dbe3;
        }
        IdentityScreen #next {
            background: #2b7f5a;
            color: #f5f8ff;
            text-style: bold;
        }
        IdentityScreen Button {
            margin-left: 1;
            min-width: 10;
        }
        """

        def compose(self) -> ComposeResult:
            app = self.app
            assert isinstance(app, InteractiveCreateApp)
            yield Vertical(
                BannerWidget(id="banner"),
                StepIndicator(1, 2, "Project Identity", id="step"),
                BulletField(
                    label="Project name",
                    field_id="name",
                    placeholder="my-service",
                    value=app.state["name"],
                ),
                BulletField(
                    label="Destination",
                    field_id="destination",
                    placeholder=".",
                    value=app.state["destination"],
                ),
                Static("", id="error"),
                Horizontal(
                    Button("Cancel", id="cancel"),
                    Button("Next →", id="next"),
                    id="actions",
                ),
                id="shell",
            )

        def on_mount(self) -> None:
            self.query_one("#name", Input).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self.app.exit(None)
            elif event.button.id == "next":
                self._advance()

        def action_cancel(self) -> None:
            self.app.exit(None)

        def _advance(self) -> None:
            name_field = self.query_one("BulletField", BulletField)
            name = name_field.value
            if not name:
                self.query_one("#error", Static).update(
                    "Project name is required."
                )
                return
            dest_fields = self.query("BulletField")
            destination = dest_fields[-1].value or "."
            app = self.app
            assert isinstance(app, InteractiveCreateApp)
            app.state["name"] = name
            app.state["destination"] = destination
            self.query_one("#error", Static).update("")
            app.push_screen(TechnicalScreen())

        def on_input_changed(self, _event: Input.Changed) -> None:
            self.query_one("#error", Static).update("")

    class InteractiveCreateApp(App[InteractiveCreateConfig | None]):
        """Two-stage wizard for interactive project scaffolding."""

        CSS = """
        Screen {
            background: #0b0f14;
            color: #d5dbe3;
        }
        """

        BINDINGS = [
            ("ctrl+c", "quit_app", "Quit"),
        ]

        def __init__(self, defaults: InteractiveCreateConfig) -> None:
            super().__init__()
            self.state: dict[str, str | tuple[str, ...]] = {
                "name": defaults.name.strip(),
                "destination": defaults.destination.strip() or ".",
                "orm": _pick_choice(defaults.orm, ORM_CHOICES),
                "design": _pick_choice(defaults.design, DESIGN_CHOICES),
                "package_manager": _pick_choice(
                    defaults.package_manager, PACKAGE_MANAGER_CHOICES
                ),
                "uid": _pick_choice(defaults.uid, UID_CHOICES),
                "broker": _pick_choice(
                    defaults.broker,
                    INTERACTIVE_BROKER_CHOICES,
                ),
                "nosql": _pick_nosql(
                    defaults.nosql,
                ),
            }

        def on_mount(self) -> None:
            self.push_screen(IdentityScreen())

        def action_quit_app(self) -> None:
            self.exit(None)


def run_create_interactive(
    defaults: InteractiveCreateConfig,
) -> InteractiveCreateConfig | None:
    """Run interactive create UI and return selected configuration."""
    if not TEXTUAL_AVAILABLE:
        raise RuntimeError(
            "Interactive mode requires the 'textual' package. "
            "Reinstall robyn-config to include dependencies."
        ) from TEXTUAL_IMPORT_ERROR

    app = InteractiveCreateApp(defaults)
    result = app.run()
    if isinstance(result, InteractiveCreateConfig) or result is None:
        return result
    return None
