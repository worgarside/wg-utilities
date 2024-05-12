clean:
	find . \( -name "__pycache__" -o -name "build" -o -name "dist" \) -type d -exec rm -rf {} +

build-docs:
	poetry run mkdocs build

install:
	poetry install --sync --all-extras --with dev,test,docs

test:
	poetry run pytest --cov-report=xml --cov=./

pch:
	pre-commit run --all

vscode-shortcut-9:
	ruff check .
