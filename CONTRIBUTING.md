# Contributing

Thanks for taking the time to improve this project.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check          # ruff, mypy --strict, pytest with 85% coverage gate
make policy         # tfpolicy check + formatting check on terraform/
```

## What a change needs

- Terraform changes pass `tfpolicy check` with no findings, or carry a `tfpolicy:ignore` comment with a written reason that a reviewer can accept.
- A new rule has an ID, severity, rationale, fix, framework reference, a failing and a passing test, and a row in `docs/compliance-mapping.md`. Run `make docs` to regenerate `docs/policies.md`.
- Changes to network exposure, identity or logging update the threat model or an ADR in the same pull request.
- Python is typed (`mypy --strict`), formatted with `ruff format`, and keeps coverage at or above 85%.
- Update `CHANGELOG.md` for anything a user of the modules or the checker would notice.

## Pull requests

Keep them focused, describe the behaviour change and how you tested it, and make sure
CI is green. Security issues go through private reporting, see [SECURITY.md](SECURITY.md).
