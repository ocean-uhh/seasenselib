# Contributing to SeaSenseLib

Thank you for helping improve SeaSenseLib. Bug reports, documentation fixes,
tests, and code contributions are welcome. By participating, you agree to
follow our [Code of Conduct](CODE_OF_CONDUCT.md).

By submitting a contribution, you agree that it will be licensed under the
[MIT License](LICENSE) and confirm that you have the right to submit it.

For substantial changes, open an issue before starting work so that the scope
and approach can be discussed. Small, focused fixes may be submitted directly.
Please do not use public issues to report security vulnerabilities. Contact the
maintainer listed in [`pyproject.toml`](pyproject.toml) privately instead.

## Development setup

If you do not have write access to the SeaSenseLib repository, first fork it on
GitHub and clone your fork. Maintainers and collaborators with write access may
clone the main repository directly. Then create a virtual environment and
install the package with its development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create a branch from the latest `main` branch and keep each pull request focused
on one change.

## Coding standards

- Follow PEP 8 and the style of the surrounding code. Use four spaces for
  indentation and clear, descriptive names.
- Add docstrings to new public modules, classes, functions, and methods. Add
  type hints to new public interfaces where practical.
- Preserve backward compatibility unless a breaking change has been discussed
  and documented.
- For scientific or format-specific behavior, document assumptions and retain
  source metadata and provenance where possible.
- Keep dependencies and test data minimal. Do not commit generated files,
  credentials, private data, or data that cannot be redistributed.
- Update user documentation when behavior or public APIs change.

## Testing expectations

Run the test suite before submitting a pull request:

```bash
python -m pytest tests/
```

New features and bug fixes should include focused tests, including relevant
edge cases. A bug fix should contain a regression test that fails without the
fix. Changes to readers or writers should use the smallest redistributable test
fixture that demonstrates the behavior.

For documentation changes, also build the documentation and address warnings
introduced by the change:

```bash
make -C docs html
```

Continuous integration runs the test suite on the supported Python versions.

## Pull request checklist

- [ ] The change is focused and its purpose is clearly described.
- [ ] Relevant tests were added or updated and pass locally.
- [ ] Documentation and examples were updated where needed.
- [ ] Public API and compatibility implications are described.
- [ ] New dependencies have been justified and documented. New data files
      include their sources and terms that permit redistribution.
- [ ] The branch contains no unrelated changes, generated files, or sensitive
      information.
- [ ] User-facing changes are noted in the pull request description.

## Review workflow

1. Open a pull request against `main` and link any related issue. Draft pull
   requests are welcome for early feedback.
2. Automated checks run on the pull request. Please resolve failures before
   requesting final review.
3. A maintainer reviews the design, scientific correctness, tests,
   documentation, and compatibility. Other community members may also review.
4. Address feedback with additional commits and resolve discussions with the
   reviewer. Review may take more than one round.
5. A maintainer merges the pull request after the checks pass, required changes
   are addressed, and at least one maintainer has approved it.

Review is collaborative. Keep discussions technical, constructive, and aligned
with the [Code of Conduct](CODE_OF_CONDUCT.md).
