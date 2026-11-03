# E11 execution record

1. Read publication Git state and remote main: clean at ef1075976d5845c0017df28707a80d6a20bc696d; unrelated local main preserved.
2. Independently recomputed dataset and raw function hashes; both matched the request. Created preservation_baseline.json before implementation.
3. Ran acquire_sources.py once with the existing Python -B environment. Five pinned upstream files fetched; tag association matched; no fetch failures.
4. Ran prepare_evidence.py once. Exact upstream body/line/type checks matched; created source evidence, manifest and finite contract.
5. Parsed initial four Python sources and loaded source gates without solving; preflight_checks.json records the result.
6. Ran local_normalization_smt.py once: four core checks and eight boundary-model checks; A=SAT/B=UNSAT for both widths. All eight boundary models matched the independent reference.
7. Ran test_local_normalization.py once: 15 tests, 1 failure, 0 errors, 0 solver checks. Preserved test file and test_results.json. Failure was equality operand order assumed by test_06.
8. Added development_failure_01.json and test_local_normalization_v2.py; no experiment code, contract, solver query or result overwritten. Ran v2 once: 15 passed, 0 failures/errors, 0 solver checks.
9. Ran complete_audit.py for file preservation, explicit acceptance criteria, documentation and artifact hashes. No solver or old regression is run by this step.

All result/evidence writers use exclusive creation. Completed solver records and first-test failure remain immutable. The final report and commit publication are distinct from research review. No new research stage is started.
