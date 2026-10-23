# ADR-001 — Runtime: Python 3.12, managed with uv

**Status:** accepted · **Evidence:** compatibility constraints (no benchmark).

## Context

The assignment asks for a Python pipeline and names spaCy, sentence embeddings and NetworkX. The runtime must install the same way on a reviewer's machine and give the same results.

## Decision

- Python **3.12**, pinned with `requires-python = ">=3.12,<3.13"`.
- [uv](https://docs.astral.sh/uv/) manages the environment, with a committed `uv.lock`.
- The spaCy models are installed as URL dependencies of the project, not with `spacy download`.

## Why no benchmark

Nothing here changes linking quality, so there is nothing to measure. The choice is forced by version constraints, checked on PyPI on 2026-10-22:

| Package | Constraint |
|---|---|
| networkx 3.7 | needs Python ≥ 3.12, and excludes 3.14.1 |
| spaCy 3.8.16 | ships wheels for 3.10–3.14 |
| en_core_web_* 3.8.0 models | built for spaCy 3.8 |

Python 3.12 is the oldest version that satisfies all of these. The oldest version is the safest choice for the compiled dependencies (torch, blis, thinc).

uv was chosen for its lockfile. Its install speed against pip was not measured, because install time does not affect the deliverable. Declaring the spaCy models as URL dependencies matters because `spacy download` calls pip and bypasses the lockfile.

## Consequences

`uv sync` installs everything needed, including the default `en_core_web_trf` pipeline and the lightweight `en_core_web_sm`. The `md` and `lg` pipelines are an optional extra (`--extra models`), used only by the benchmark in ADR-004.
