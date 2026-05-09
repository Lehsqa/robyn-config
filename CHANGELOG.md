# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking Changes

### Added

### Changed

### Fixed

### Security

---

## [0.6.0] - 2026-04-04

### Added

- Interactive mode for `create` command with Textual UI (#30)
- `Annotated` field support for Pydantic models (#29)
- `monitoring` command to scaffold full observability stack (#28)
- `--uid` flag to generate projects with custom UID schemes (uuidv4, uuidv7, nanoid, ulid, sparkid) (#27)

### Changed

- Updated README.md with new features (#26)

## [0.5.1] - 2026-03-21

### Fixed

- Logging permission and environment variable handling (#22)

## [0.5.0] - 2026-03-09

### Added

- `adminpanel` command to scaffold admin panel with Dark/Light themes (#23)
- Admin panel authentication with configurable superadmin credentials
- Auto-discovery of project models in admin navigation
- CRUD operations for discovered model tables

### Changed

- Refactored `adminpanel/` and `utils/` for `create/` and `add/` (#24)
- Added presentation layer to DDD architecture
- Updated README.md with adminpanel documentation

## [0.4.1] - 2026-02-26

### Fixed

- Minor bug fixes and improvements

## [0.4.0] - 2026-02-18

### Added

- Interactive mode for `create` command (#21)
- AI agent skills support (#20)

### Changed

- Updated documentation with skills feature

## [0.3.1] - 2026-02-01

### Fixed

- Changed paths and including all files for package (#19)

## [0.3.0] - 2025-12-14

### Added

- Community standards docs (CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md)
- Custom routes for `add` method — configurable injection paths via `[tool.robyn-config.add]` in `pyproject.toml` (#16)
- `--package-manager` flag to choose between `uv` and `poetry` (#15)

### Changed

- Updated README.md linking (#14)

## [0.2.0] - 2025-12-07

### Added

- New `add` command to inject business logic (models, repositories, routes) into existing projects (#12)
- Sphinx documentation with API reference and build configuration (#11)
- Unit tests for `cli.py` (#13)

### Changed

- Enhanced README with badges, detailed usage, features, and development guidelines (#10)

## [0.1.1] - 2025-11-30

### Added

- Integration tests for the project (#9)

### Fixed

- Configuration naming issues (#8)
- Makefile templating bugs (#7)

## [0.1.0] - 2025-11-23

### Added

- Initial release of robyn-config
- CLI tool to bootstrap Robyn projects with DDD and MVC designs
- Support for SQLAlchemy and Tortoise ORM
- `create` command with `--orm` and `--design` flags
- Docker Compose templates for development and production
- Project scaffolding with authentication, caching, and mailing modules

---

## Version Scheme

Starting from 1.0.0, this project will follow strict semantic versioning:

- **MAJOR** — breaking changes to CLI interface or generated project structure
- **MINOR** — backward-compatible features (new commands, new template options)
- **PATCH** — backward-compatible bug fixes
