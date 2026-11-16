# CI/CD do backend

A configura??o vigente est? em [MySQL e Railway ? servi?o ?nico](docs/database-migrations.md).

Backend CI valida Ruff, pytest, MySQL 8.4, Alembic, actionlint e Docker.
Backend production reutiliza a valida??o e publica somente push em prod, com
aprova??o do environment production, checksum do artefato, rejei??o de SHA antigo
e acompanhamento do deployment exato. A migration ocorre no pre-deploy da API.
Actions fixadas por SHA; Railway CLI 5.74.0. PRs e merges s?o manuais.
