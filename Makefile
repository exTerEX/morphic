.PHONY: test coverage lint format clean help install run docs

help:
	@echo "Available targets:"
	@echo "  install   - Install dependencies with uv"
	@echo "  run       - Start the web UI"
	@echo "  test      - Run all tests"
	@echo "  coverage  - Run tests with coverage report"
	@echo "  lint      - Run linting checks"
	@echo "  format    - Format code with ruff"
	@echo "  docs      - Build Sphinx documentation"
	@echo "  clean     - Remove build artifacts"

install:
	uv sync --dev --all-extras

run: install
	uv run morphic

test: install
	uv run pytest

coverage: install
	uv run pytest --cov=morphic --cov-report=html --cov-report=term-missing

lint: install
	uv run ruff check src/morphic/
	uv run pyright src/morphic/

format: install
	uv run ruff format src/morphic/ tests/
	uv run ruff check --fix src/morphic/ tests/

docs: install
	uv run sphinx-build -b html docs/ docs/_build/html

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .ruff_cache/
	rm -rf docs/_build/
	rm -rf bin/
	find . -type d -name __pycache__ -exec rm -rf {} +

# Go targets
.PHONY: go-build go-test go-run go-vet go-tidy

go-tidy:
	go mod tidy

go-build: go-tidy
	go build -o ./bin/morphic ./cmd/morphic

go-test:
	go test ./...

go-vet:
	go vet ./...

go-run: go-build
	./bin/morphic
