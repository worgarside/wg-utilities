clean:
	find . \( -name "__pycache__" -o -name "build" -o -name "dist" \) -type d -exec rm -rf {} +

install:
	poetry install --sync

test:
	poetry run pytest

vscode-shortcut-9:
	ruff check .
