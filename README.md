# QueryForge — NL-to-SQL Engine. Natural language to SQL — no LLM required

NL-to-SQL Engine. Natural language to SQL — no LLM required. QueryForge gives you a focused, inspectable implementation of that idea.

## Why QueryForge

QueryForge exists to make this workflow practical. Nl-to-sql engine. natural language to sql — no llm required. It favours a small, inspectable surface over sprawling configuration.

## Features

- `Schema` — exported from `src/queryforge/core.py`
- Included test suite
- Dedicated documentation folder

## Tech Stack

- **Runtime:** Python

## How It Works

The codebase is organised into `docs/`, `src/`, `tests/`. The primary entry points are `src/queryforge/core.py`, `src/queryforge/__init__.py`. `src/queryforge/core.py` exposes `Schema` — the core types that drive the behaviour.

## Getting Started

```bash
pip install -e .
```

## Usage

```python
from queryforge.core import Schema

instance = Schema()
# See the source for the full API
```

## Project Structure

```
QueryForge/
├── .env.example
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── README.md
├── docs/
├── pyproject.toml
├── src/
├── tests/
```
