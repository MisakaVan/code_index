# Repo-level code index

This project aims to build a repo-level source code index to help LLMs/agents understand and navigate large codebases to
perform vulnerability detection and code understanding tasks.

## Features
- Python, C, C++ support (C++ method is not fully supported)
- Index function definition and calling
- Query function usage across the codebase
- Call graph generation and analysis
- MCP integration

## Installation

Clone the repo and cd into it.

Suggest using `uv` to manage the virtual environment. A `requirements.txt` file is also provided for conda and pip.

### Using uv

With uv installed, create the virtual environment:

```bash
uv venv
```

Install the dependencies. This will install all the dependency groups.

```bash
uv sync --all-groups
```

Activate the virtual environment:

```bash
souce .venv/bin/activate
```

If not activated, you can also run commands in the virtual environment with `uv run <command>`. `<command>` can be `pytest`, `ruff`, `sphinx-build`, etc.

### Using conda/mamba

Create a conda environment:

```bash
conda create -n env_name python=3.13
conda activate env_name
```

Then install the dependencies with pip:

```bash
pip install -r requirements.txt
```

## Development

### .env file

Check the `.env.example` file for the required environment variables. Create a `.env` and an optional `.env.test` file in the project root for better configuration (currently controls logging level).

### Lint, Format, Git Hooks

`ruff` is used for linting and formatting. To lint the code, run:

```bash
ruff check
```
To format the code, run:

```bash
ruff format
```

Refer to ruff documentation for more details.

`pre-commit` is used to manage git hooks, which runs `ruff` and `pytest` before each commit.

To install the git hooks, run:

```bash
pre-commit install
```

To manually run the git hooks, run:

```bash
pre-commit run --all-files
```

### Testing

`pytest` is used for testing. To run the tests, run:

```bash
pytest tests
```

### Type Checking

Static type checking is not forced in the codebase and the git hooks. `mypy` is included as a dev dependency, though. To run `mypy`, run:

```bash
mypy path/to/src
```

### Documentation

`sphinx` is used for documentation. To build the documentation, run:

```bash
cd docs
sphinx-build -b html ./source ./build
```

Then open `docs/build/index.html` in a web browser to view the documentation.
