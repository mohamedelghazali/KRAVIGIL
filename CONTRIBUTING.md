# Contributing to KRAVIGIL

## 1. Code of Conduct
We strictly enforce a Zero Trust environment, both in code and in collaboration. Be respectful, professional, and security-minded.

## 2. Development Setup
1. Clone the repository.
2. Create a virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Install pre-commit hooks: `pre-commit install`

## 3. Coding Standards
- **Python**: We follow `black` for formatting and `ruff` for linting. Run `make lint` and `make format` before committing.
- **C++**: We follow the Google C++ Style Guide. Use `clang-format`.
- **Commit Messages**: Use Conventional Commits (e.g., `feat: add new scanner`, `fix: patch RLS bypass`).

## 4. Security Rules
- **Never** commit secrets (API keys, passwords). Use `.env` files for local testing.
- **Always** write tests for new features. PRs without tests will be rejected.
- **Always** use parameterized queries. No raw SQL string formatting.
- **Always** validate user input at the API boundary (Pydantic).

## 5. Pull Request Process
1. Create a feature branch: `git checkout -b feat/my-new-engine`
2. Implement the feature and add tests.
3. Run `make lint` and `make test`.
4. Submit a PR. The CI pipeline must pass (including C++ builds and security tests).
