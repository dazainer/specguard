# intervals

First-party MIT-licensed synthetic benchmark subject. Included for: Half-open interval semantics, symmetry, negative endpoints, and min/max selection.

Pin: `b9f0b1517ba4012a629dd9b33a2ef4873c14c74b`. The bundle contains source, native tests, license and a standard-library-only dependency lock. Specifications and interfaces are authored with the subject. Native tests are excluded from model context. `generation-fixture.json` is handwritten, intentionally smaller than the native suite.

Run with the [evaluation guide](../../../docs/evaluation-cli.md). Rebuild from the repository root using `python3 benchmarks/rebuild_subject.py benchmarks/subjects/intervals` and explicitly update the manifest pin if it changes.
