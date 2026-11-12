# Validation and Release Evidence

## Local checks

From the repository root, with Python 3.11 or later:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

Tests use synthetic temporary files. They must prove preservation, safe recovery,
malformed-manifest handling, path/collision controls, corruption detection, and
consent refusal at the user boundary.

## CI configuration

The workflow runs behavioral tests on Linux and Windows with Python 3.11 and
3.14. Actions are pinned to reviewed immutable commit identifiers, workflow
permissions are read-only, and checkout does not retain its token in Git
configuration. The workflow performs validation only.

A committed workflow is configuration, not evidence of a successful remote run.
Record the actual run URL, commit, job status, and relevant failures after GitHub
executes it. Local success does not establish Windows success.

## Engineering review

Typed annotations, standard-library-only runtime dependencies, and tests support
review; they do not prove the entire Golden Coding Standard automatically.
Static type checking and additional lint tools may be introduced after a pinned
development dependency policy is adopted.

## Release record

Each release should state:

- Exact source commit and toolchain.
- Supported inputs and operating systems.
- Tests and fault scenarios actually executed.
- Benchmark environment, dataset, methodology, and observed limits.
- Legal/consent version and deployment-specific data-handling behavior.
- Known gaps and capability claims excluded from that release.

No test or benchmark report can certify legal enforceability or complete
coverage of a user's account.
