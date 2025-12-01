# robyn-config

[![Downloads](https://static.pepy.tech/personalized-badge/robyn-config?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Downloads)](https://pepy.tech/project/robyn-config)
[![PyPI version](https://badge.fury.io/py/robyn-config.svg)](https://badge.fury.io/py/robyn-config)
[![License](https://img.shields.io/badge/License-MIT-black)](https://github.com/Lehsqa/robyn-config/blob/main/LICENSE)
![Python](https://img.shields.io/badge/Support-Version%20%E2%89%A5%203.11-brightgreen)

`robyn-config` is a CLI tool designed to scaffold [Robyn](https://robyn.tech) backend projects. It provides templates for **Domain-Driven Design (DDD)** and **Model-View-Controller (MVC)** architectures, with support for **SQLAlchemy** and **Tortoise ORM**.

## 📦 Installation

You can simply use Pip for installation.

```bash
pip install robyn-config
```

## 🤔 Usage

### 🚀 Create a Project

To create a new project with your preferred architecture and ORM, run:

```bash
robyn-config create my-service --orm sqlalchemy --design ddd ./my-service
```

Or for an MVC layout with Tortoise ORM:

```bash
robyn-config create newsletter --orm tortoise --design mvc ~/projects/newsletter
```

### 🏃 CLI Options

```
Usage: robyn-config [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  create  Scaffold a new Robyn project.
```

**`create` command options:**

- `name`: Sets the project name used in templated files like `pyproject.toml` and `README.md`.
- `--orm`: Selects the database layer. Options: `sqlalchemy`, `tortoise`.
- `--design`: Toggles between the architecture templates. Options: `ddd`, `mvc`.
- `destination`: The target directory. Defaults to `.`.

## 🐍 Python Version Support

`robyn-config` is compatible with the following Python versions:

> Python >= 3.11

Please make sure you have the correct version of Python installed before starting to use this project.

## 💡 Features

- **Scaffolding**: Quickly generate Robyn backend projects.
- **Architecture Choices**: Support for DDD and MVC patterns.
- **ORM Flexibility**: Choose between SQLAlchemy and Tortoise ORM.
- **Docker Ready**: Includes Docker and Docker Compose configurations.
- **Development Tools**: Comes with `ruff`, `pytest`, and `black` configured.

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
    ruff check src
    pytest
    ```

## ✨ Special thanks

Special thanks to the [Robyn](https://github.com/sparckles/Robyn) team for creating such an amazing framework!
