# robyn-config

[![Downloads](https://static.pepy.tech/personalized-badge/robyn-config?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/robyn-config)
[![PyPI version](https://badge.fury.io/py/robyn-config.svg)](https://badge.fury.io/py/robyn-config)
[![License](https://img.shields.io/badge/License-MIT-black)](https://github.com/Lehsqa/robyn-config/blob/main/LICENSE)
![Python](https://img.shields.io/badge/Support-Version%20%E2%89%A5%203.11-brightgreen)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-Lehsqa%2Frobyn--config-blue.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/Lehsqa/robyn-config)

`robyn-config` is a comprehensive CLI tool designed to bootstrap and manage [Robyn](https://robyn.tech) applications. It streamlines your development workflow by generating production-ready project structures and automating repetitive tasks, allowing you to focus on building your business logic.

Think of it as the essential companion for your Robyn projects-handling everything from initial setup with best practices to injecting new feature components as your application grows.

## 📦 Installation

You can simply use Pip for installation.

```bash
pip install robyn-config
```

## 🤔 Usage

### 🚀 Create a Project

To bootstrap a new project with your preferred architecture and ORM, run:

```bash
# Create a DDD project with SQLAlchemy (uses uv by default)
robyn-config create my-service --orm sqlalchemy --design ddd ./my-service
```

```bash
# Create an MVC project with Tortoise ORM, locking with poetry
robyn-config create newsletter --orm tortoise --design mvc --package-manager poetry ~/projects/newsletter
```

### ➕ Add Business Logic

Once inside a project, you can easily add new entities (models, routes, repositories, etc.) using the `add` command. This automatically generates all necessary files and wiring based on your project's architecture.

```bash
# Add a 'product' entity to your project
cd my-service
robyn-config add product
```

This will:
- Generate models/tables.
- Create repositories.
- Setup routes and controllers.
- Register everything in the app configuration.
- Respect your configured paths: `add` reads injection targets from `[tool.robyn-config.add]` in `pyproject.toml` (e.g., domain/operational/presentation paths for DDD or views/repository/urls for MVC). You can customize those paths before running `add` to steer where new code is written.

### 🏃 CLI Options

```
Usage: robyn-config [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  add     Add new business logic to an existing robyn-config project.
  create  Copy the template into destination with specific configurations.
```

**`create` command options:**

- `name`: Sets the project name used in templated files like `pyproject.toml` and `README.md`.
- `--orm`: Selects the database layer. Options: `sqlalchemy` (default), `tortoise`.
- `--design`: Toggles between the architecture templates. Options: `ddd` (default), `mvc`.
- `--package-manager`: Choose how dependencies are locked/installed. Options: `uv` (default), `poetry`.
- `destination`: The target directory. Defaults to `.`.

**`add` command options:**

- `name`: The name of the entity/feature to add (e.g., `user`, `order-item`).
- `project_path`: Path to the project root. Defaults to current directory.

## 🐍 Python Version Support

`robyn-config` is compatible with the following Python versions:

> Python >= 3.11

Please make sure you have the correct version of Python installed before starting to use this project.

## 💡 Features

- **Rapid Scaffolding**: Instantly generate robust, production-ready Robyn backend projects.
- **Integrated Component Management**: Use the CLI to inject models, routes, and repositories into your existing architecture, ensuring consistency and best practices.
- **Architectural Flexibility**: Native support for **Domain-Driven Design (DDD)** and **Model-View-Controller (MVC)** patterns.
- **ORM Choice**: Seamless integration with **SQLAlchemy** or **Tortoise ORM**.
- **Package Manager choice**: Lock/install via **uv** (default) or **poetry**, with fresh lock files generated in quiet mode.
- **Resilient operations**: `create` cleans up generated files if it fails; `add` rolls back using a temporary backup to keep your project intact.
- **Production Ready**: Includes Docker, Docker Compose, and optimized configurations out of the box.
- **DevEx**: Pre-configured with `ruff`, `pytest`, `black`, and `mypy` for a superior development experience.

## 🗒️ How to contribute

### 🏁 Get started

Feel free to open an issue for any clarifications or suggestions.

### ⚙️ To Develop Locally

#### Prerequisites

- Python >= 3.11
- `uv` (recommended) or `pip`

#### Setup

1.  Clone the repository:

    ```bash
    git clone https://github.com/Lehsqa/robyn-config.git
    ```

2.  Setup a virtual environment and install dependencies:

    ```bash
    uv venv && source .venv/bin/activate
    uv pip install -e .[dev]
    ```

3.  Run linters and tests:

    ```bash
    make check
    ```

## ✨ Special thanks

Special thanks to the [Robyn](https://github.com/sparckles/Robyn) team for creating such an amazing framework!
