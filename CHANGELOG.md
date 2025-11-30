# Changelog

All notable changes to this project are documented here.

## 0.1.1 - 2025-11-30

### Changed
- Refined the DDD template so `UsersRepository` is only an ABC in the domain layer, with each infrastructure stack providing a concrete implementation through a shared repository module and factory-driven operational services.
- Added an integration smoke test that scaffolds every design/ORM combination, boots the Docker compose stack, exercises `/users`, `/users/activate`, `/auth/login`, and `/auth/me`, and cleans up containers/volumes along with MailHog polling.
- Improved repository wiring by deriving the ORM table from `BaseRepository` generics, capturing activation links from MailHog, and making login/response handling resilient to the wrapper schema.
- Updated configuration for DB and SMTP with default values.

### Fixed
- Fixed healthcheck endpoint for mvc
- Fixed Makefile templating

## 0.1.0 - 2025-11-23

### Added
- Initial Robyn scaffolding CLI (`robyn-config create`) with ORM selection.
- Support for both SQLAlchemy and Tortoise templates, including compose helpers.
- MVC and DDD project layouts with shared common files and Docker tooling.

### Notes
- First published release cut from commits up to `Chore: Prepare to release first version (#4)`.
