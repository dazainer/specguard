# pagination

First-party MIT-licensed synthetic benchmark subject. Included for: One-based indexing, empty inputs, clamping, and off-by-one arithmetic.

Pin: `7a9f522b5294f5bf48041699094b1c96d3b2336e`. The bundle contains source, native tests, license and a standard-library-only dependency lock. Specifications and interfaces are authored with the subject. Native tests are excluded from model context. `generation-fixture.json` is handwritten, intentionally smaller than the native suite.

Run with the [evaluation guide](../../../docs/evaluation-cli.md). Rebuild from the repository root using `python3 benchmarks/rebuild_subject.py benchmarks/subjects/pagination` and explicitly update the manifest pin if it changes.
