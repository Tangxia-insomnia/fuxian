# E12-1 + E12-2 execution log

1. Read the complete user attachment and all frozen preflight inputs. Verified experiment/E12 at 3d58641c8c62e80d60e82d137b03bcba7b8ed5cd, clean worktree and main at f4850309b19cd049ff38356881549bb33c615144. Fetched only Git branch metadata/objects; downloaded no source/dataset.
2. Compared all five original preflight files against the fetched remote commit and publication checkout bytes. Captured preservation_baseline.json before creating implementation or result files.
3. Confirmed existing Z3 4.13.4 / z3-solver 4.13.4.0; installed nothing. Added the frozen finite semantic contract, separate Python reference, SMT implementation and E12-only tests.
4. Parsed three initial Python files, loaded all fixed source/dataset/preflight/contract gates, and wrote input_verification.json plus implementation_preflight.json. Zero solver checks at this point; no original index invented.
5. Ran e12_nullness_smt.py once using the existing Python -B. Saved exactly Q1/Q2/Q3/Q4 and their JSON records. Results SAT/UNSAT/SAT/SAT with models (false,false), none, (false,true), (true,true); four solver checks total. The separate Python reference enumerated all four inputs, without Z3.
6. Ran test_e12_nullness_smt.py once using Python -B. 22 tests passed, no failures/errors or extra solver checks. Saved 16 formula/reference truth comparisons; solver constructors were blocked throughout the suite.
7. Ran complete_e12_audit.py for read-only file/hash/Git checks, acceptance, reports and final artifact hashes. This step invokes no solver or historical tests. No implementation, result, preflight or failure record was overwritten.

Publication is conditional on every acceptance criterion. Only new E12 files are eligible for the existing experiment/E12 branch; main is never a push destination. Q3 is counterfactual, Q4 is INVALID_ENCODING_DIAGNOSTIC_ONLY. Original-alert decision remains null, filtering authority false, full-program semantics UNKNOWN.
