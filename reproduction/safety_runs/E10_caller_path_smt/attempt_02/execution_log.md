# E10 attempt_02 execution record

Every output used exclusive creation. Acquired source bytes used xb. No first-attempt record or prior experiment was overwritten.

1. Checked Git HEAD/status; established the8168-file preservation baseline before creating outputs. Recomputed the raw JSON UTF-8 body hash and compared it independently with two E09 records.
2. git ls-remote confirmed v6.9.6 annotated tag185c18dcbe7edb086251c0a4fadb752f0b42aaaa and peeled commit9c5a72fbc90d829ffb761da64a73c23cd4e0503f. No clone/build.
3. fetch_fixed_sources.py fetched fixed-commit C/headers in the recorded batches; three Kconfig metadata files were separately fetched.29 saved files,516867 bytes;30 raw HTTP requests including one404. Three extension-gate rejections made no HTTP request. All failures remain recorded.
4. extract_source_contract.py failed before final certificate output or solving: an evidence clip requested end line88 in an87-line header. The original helper and development_failure_01.json remain. extract_source_contract_v2.py corrects only that endpoint to87; development_revision_01.json records exact hashes/diff. Source/semantics unchanged.
5. The v2 helper generated53 source facts, five configuration tables, explicit effect review and a frozen caller contract. preflight_checks.json records source/span/hash admission and both formula constructions with zero solver checks.
6. Existing Python -B caller_path_smt.py ran exactly two solver.check calls:32-bitUNSAT and64-bitUNSAT. Exact SMT, results and timings were saved separately. No failed or repeated SMT query.
7. Existing Python -B test_caller_path_smt.py ran once:15/15 methods,16 required boundary observations,26 finite formula substitutions, zero additional solver checks. No native C/kernel execution.
8. A report-helper bootstrap command had a nested-quote SyntaxError before creating a helper/report; development_failure_02.json records it. A direct literal here-string assembled the report and preservation/acceptance/hash records. No source, contract, query or test output was edited or rerun.

Runtime: reproduction/.venv/Scripts/python.exe -B; existing z3-solver4.13.4.0. No installation. LLM/Harness/old analyzer/R01-R05/624 regressions:0. No commit/push. Research review pending.
