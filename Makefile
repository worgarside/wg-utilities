clean:
	find . \( -name "__pycache__" -o -name "build" -o -name "dist" \) -type d -exec rm -rf {} +

install:
	poetry install --sync

vscode-shortcut-9:
	ruff check .
