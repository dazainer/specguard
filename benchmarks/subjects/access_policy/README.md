# access_policy

First-party MIT-licensed synthetic benchmark subject. Included for: Boolean policy composition, deny precedence, and role comparisons.

Pin: `586607e0a313ad78ec7d1e95abdaef2b22bc1ffb`. The bundle contains source, native tests, license and a standard-library-only dependency lock. Specifications and interfaces are authored with the subject. Native tests are excluded from model context. `generation-fixture.json` is handwritten, intentionally smaller than the native suite.

Run with the [evaluation guide](../../../docs/evaluation-cli.md). Rebuild from the repository root using `python3 benchmarks/rebuild_subject.py benchmarks/subjects/access_policy` and explicitly update the manifest pin if it changes.
