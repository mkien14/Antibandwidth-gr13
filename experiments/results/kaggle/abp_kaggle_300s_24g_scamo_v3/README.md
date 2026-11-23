# Kaggle benchmark: SCAMO v3

This directory stores the complete 24-instance benchmark export (one run per method) and the original Kaggle checkpoint archive.

- Experiment: bp_kaggle_300s_24g_scamo_v3
- Limits: 300 seconds and 24,576 MiB per attempt; one run per graph and method
- Methods: pairwise, order, scamo, cplex_cp, cplex_mip, gurobi, cp_sat
- Coverage: 24 graphs x 7 methods = 168 result rows; 39 Optimal, 129 Timeout
- Source fingerprint from experiment.json: $sourceHash; verified against the current project using the notebook's file-ordering procedure
- Environment snapshots for batch indices 0 and 1 are in metadata/; the checkpoint archive also retains all solver logs

esults.csv and sat-diagnostics.csv are convenience copies of the corresponding files in the checkpoint. A Timeout row's est_k, when present, is an incumbent and is not an optimality proof. A blank est_k means no incumbent was recorded before the attempt timed out.

The ZIP is retained as the unmodified Kaggle export and contains experiment.json, both environment snapshots, both CSV files, and the solver logs. To reproduce analyses, start with the two CSVs and consult the archived logs when checking SAT phase timings or individual solver runs.