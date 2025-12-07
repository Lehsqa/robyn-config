# robyn-config

[![Downloads](https://static.pepy.tech/personalized-badge/robyn-config?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/robyn-config)
[![PyPI version](https://badge.fury.io/py/robyn-config.svg)](https://badge.fury.io/py/robyn-config)
[![License](https://img.shields.io/badge/License-MIT-black)](https://github.com/Lehsqa/robyn-config/blob/main/LICENSE)
![Python](https://img.shields.io/badge/Support-Version%20%E2%89%A5%203.11-brightgreen)

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
# Create a DDD project with SQLAlchemy
robyn-config create my-service --orm sqlalchemy --design ddd ./my-service
```

```bash
# Create an MVC project with Tortoise ORM
robyn-config create newsletter --orm tortoise --design mvc ~/projects/newsletter
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

### 🏃 CLI Options

```
Usage: robyn-config [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  create  Scaffold a new Robyn project.
  add     Add business logic component to an existing project.
```

**`create` command options:**

- `name`: Sets the project name used in templated files like `pyproject.toml` and `README.md`.
- `--orm`: Selects the database layer. Options: `sqlalchemy`, `tortoise`.
- `--design`: Toggles between the architecture templates. Options: `ddd`, `mvc`.
- `destination`: The target directory. Defaults to `.`.

**`add` command options:**

- `name`: The name of the entity/feature to add (e.g., `user`, `order-item`).
- `-p`, `--project-path`: Path to the project root. Defaults to current directory.

## 🐍 Python Version Support

`robyn-config` is compatible with the following Python versions:

> Python >= 3.11

Please make sure you have the correct version of Python installed before starting to use this project.

## 💡 Features

- **Rapid Scaffolding**: Instantly generate robust, production-ready Robyn backend projects.
- **Integrated Component Management**: Use the CLI to inject models, routes, and repositories into your existing architecture, ensuring consistency and best practices.
- **Architectural Flexibility**: Native support for **Domain-Driven Design (DDD)** and **Model-View-Controller (MVC)** patterns.
- **ORM Choice**: Seamless integration with **SQLAlchemy** or **Tortoise ORM**.
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
