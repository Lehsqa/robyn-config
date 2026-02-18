"""Interactive create-mode UI powered by Textual."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .utils import DESIGN_CHOICES, ORM_CHOICES, PACKAGE_MANAGER_CHOICES

TEXTUAL_IMPORT_ERROR: ModuleNotFoundError | None = None

try:
    from textual import events
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, Input, Label, Select, Static

    TEXTUAL_AVAILABLE = True
except ModuleNotFoundError as exc:
    if exc.name != "textual":
        raise
    TEXTUAL_AVAILABLE = False
    TEXTUAL_IMPORT_ERROR = exc


def _pick_choice(value: str, choices: Sequence[str]) -> str:
    normalized = value.lower().strip()
    return normalized if normalized in choices else choices[0]


@dataclass(frozen=True, slots=True)
class InteractiveCreateConfig:
    """Collected values from interactive create mode."""

    name: str
    destination: str
    orm: str
    design: str
    package_manager: str


if TEXTUAL_AVAILABLE:

    class InteractiveCreateApp(App[InteractiveCreateConfig | None]):
        """Single-screen form for interactive project scaffolding."""

        CSS = """
        Screen {
            background: #0b0f14;
            color: #d5dbe3;
            align: center middle;
        }

        #shell {
            width: 100;
            max-width: 98%;
            height: 100%;
            border: round #313846;
            background: #10151c;
            padding: 1;
        }

        #title {
            color: #f5f8ff;
            text-style: bold;
        }

        #subtitle {
            color: #91a0b8;
            margin-bottom: 1;
        }

        #form {
            border: tall #222a35;
            background: #0f141b;
            layout: vertical;
            padding: 0 1;
            height: 1fr;
        }

        #fields {
            height: 1fr;
        }

        #form-grid {
            width: 100%;
            height: auto;
        }

        .column {
            width: 1fr;
        }

        Label {
            color: #a6b3c7;
            margin-top: 0;
            margin-bottom: 0;
        }

        Input, Select {
            background: #0a0f16;
            color: #f5f8ff;
            border: round #394558;
        }

        #error {
            color: #ff7f7f;
            min-height: 0;
        }

        #actions {
            dock: bottom;
            margin-top: 0;
            padding-top: 0;
            border-top: solid #222a35;
            min-height: 3;
            height: auto;
            align-vertical: middle;
            align-horizontal: right;
            width: 100%;
        }

        #cancel {
            background: #232b36;
            color: #d5dbe3;
        }

        #create {
            background: #2b7f5a;
            color: #f5f8ff;
            text-style: bold;
        }

        Button {
            margin-left: 1;
            min-width: 7;
            height: 3;
            content-align: center middle;
            text-align: center;
        }
        """

        BINDINGS = [
            ("ctrl+c", "cancel", "Cancel"),
            ("escape", "cancel", "Cancel"),
            ("enter", "submit", "Create"),
        ]

        def __init__(self, defaults: InteractiveCreateConfig) -> None:
            super().__init__()
            self.defaults = InteractiveCreateConfig(
                name=defaults.name.strip(),
                destination=defaults.destination.strip() or ".",
                orm=_pick_choice(defaults.orm, ORM_CHOICES),
                design=_pick_choice(defaults.design, DESIGN_CHOICES),
                package_manager=_pick_choice(
                    defaults.package_manager, PACKAGE_MANAGER_CHOICES
                ),
            )

        def compose(self) -> ComposeResult:
            yield Vertical(
                Static("robyn-config create", id="title"),
                Static("Interactive project scaffold", id="subtitle"),
                    Vertical(
                        VerticalScroll(
                            Horizontal(
                                Vertical(
                                    Label("Project name"),
                                Input(
                                    value=self.defaults.name,
                                    placeholder="my-service",
                                    id="name",
                                ),
                                Label("ORM"),
                                Select(
                                    [
                                        (choice, choice)
                                        for choice in ORM_CHOICES
                                    ],
                                    value=self.defaults.orm,
                                    allow_blank=False,
                                    id="orm",
                                ),
                                Label("Package manager"),
                                Select(
                                    [
                                        (choice, choice)
                                        for choice in PACKAGE_MANAGER_CHOICES
                                    ],
                                    value=self.defaults.package_manager,
                                    allow_blank=False,
                                    id="package_manager",
                                ),
                                classes="column",
                            ),
                            Vertical(
                                Label("Destination"),
                                Input(
                                    value=self.defaults.destination,
                                    placeholder=".",
                                    id="destination",
                                ),
                                Label("Design"),
                                Select(
                                    [
                                        (choice, choice)
                                        for choice in DESIGN_CHOICES
                                    ],
                                    value=self.defaults.design,
                                    allow_blank=False,
                                    id="design",
                                ),
                                classes="column",
                            ),
                            id="form-grid",
                            ),
                            Static("", id="error"),
                            id="fields",
                        ),
                    Horizontal(
                        Button("Cancel", id="cancel"),
                        Button("Create", id="create"),
                        id="actions",
                    ),
                    id="form",
                ),
                id="shell",
            )

        def action_cancel(self) -> None:
            self.exit(None)

        def action_submit(self) -> None:
            self._submit()

        def on_mount(self) -> None:
            self.query_one("#name", Input).focus()

        def on_descendant_focus(self, event: events.DescendantFocus) -> None:
            if isinstance(event.widget, (Input, Select)):
                event.widget.scroll_visible(animate=False, force=True)

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id in {"name", "destination"}:
                self._clear_error()

        def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id in {"orm", "design", "package_manager"}:
                self._clear_error()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self.exit(None)
                return
            if event.button.id == "create":
                self._submit()

        def _submit(self) -> None:
            config = self._read_form()
            if not config.name:
                self._show_error("Project name is required.")
                return
            if not config.destination:
                self._show_error("Destination is required.")
                return
            self.exit(config)

        def _read_form(self) -> InteractiveCreateConfig:
            name = self.query_one("#name", Input).value.strip()
            destination = self.query_one("#destination", Input).value.strip()
            orm = str(self.query_one("#orm", Select).value)
            design = str(self.query_one("#design", Select).value)
            package_manager = str(
                self.query_one("#package_manager", Select).value
            )
            return InteractiveCreateConfig(
                name=name,
                destination=destination,
                orm=orm,
                design=design,
                package_manager=package_manager,
            )

        def _show_error(self, message: str) -> None:
            self.query_one("#error", Static).update(message)

        def _clear_error(self) -> None:
            self.query_one("#error", Static).update("")


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
