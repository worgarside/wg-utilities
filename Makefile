clean:
	find . \( -name "__pycache__" -o -name "build" -o -name "dist" \) -type d -exec rm -rf {} +

vscode-shortcut-9:
	ruff check .
