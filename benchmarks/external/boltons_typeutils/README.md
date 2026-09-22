# boltons typeutils

Selected unmodified module and upstream tests from [boltons 25.0.0](https://github.com/mahmoud/boltons/tree/c23dbdadb6fecdf505eb4231559561913b84c13f), upstream commit `c23dbdadb6fecdf505eb4231559561913b84c13f`. BSD-3-Clause notices are preserved in `target/LICENSE` and source headers.

`upstream.json` hashes every upstream file. The local bundle pins a deterministic subset commit `934b856e5f871d73fa4d1cc11fe1f993f4c98d48`; it is **not** the upstream commit. The extra requirements lock and SpecGuard-authored spec/interface/handwritten fixture are integration inputs. Native tests are copied unchanged; no upstream conftest or plugin configuration is loaded. The fixture is an independent small smoke suite, not a model result. Full-module mutation includes behavior that a small fixture may not cover.

These two boltons subjects come from **one external repository**, not two independent repositories. They are outside the five-subject synthetic benchmark and the default web catalog. Run with the regular evaluator CLI and the pinned runner.
