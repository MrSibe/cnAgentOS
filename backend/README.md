# cnAgentOS backend

FastAPI backend for cnAgentOS. Shared product, API, database, planning, and workflow documentation lives in the repository-level `docs/` directory.

Common commands from this directory:

```bash
uv sync
uv run alembic upgrade head
uv run python main.py
uv lock --check
uv run pytest
```
