# Working on DevKit 3

Read `docs/design.md` first; it is one page and it is the authority.

- Python 3.14, uv, no runtime dependencies.
- Before committing: `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q`.
- Tests call the product the way its user does (`tests/conftest.py`), with a small script
  standing in for the agent. Write the failing test first.
- `tests/test_shape.py` holds the size and independence rules. Do not raise its limits to
  make something fit; split or simplify instead.
- Add protection only for a problem that has actually happened, and say which.
- Never start a real agent program or a paid model from tests or without the user asking.
- Documentation and code are in English. New domain words go in `docs/glossary.md`.
