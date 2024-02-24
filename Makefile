clean:
	find . \( -name "__pycache__" -o -name "build" -o -name "dist" \) -type d -exec rm -rf {} +

build-docs:
	poetry run mkdocs build

install:
	poetry install --sync --all-extras

test:
	poetry run pytest

vscode-shortcut-9:
	ruff check .
