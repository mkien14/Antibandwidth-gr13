# Report benchmark: incremental SCL/NSC SCAMO

`results.csv` contains 168 rows: the 24 SCAMO rows from `scamo-results.csv` replace the SCAMO v3 rows in `../abp_kaggle_300s_24g_scamo_v3/results.csv`. The other 144 rows are unchanged. Keys are `(instance, method, run)`; each appears once. This is an analysis dataset assembled from two experiments, not a single resumable benchmark checkpoint.

- SCAMO experiment: `abp_kaggle_300s_24g_scl_nsc_refactor`; original SCAMO-only checkpoint and environment metadata are retained here.
- Six other methods: experiment `abp_kaggle_300s_24g_scamo_v3`; its original data, checkpoint and environment metadata remain in the adjacent directory.
- Each attempt: 300 seconds, memory limit 24,576 MiB, one run. SCAMO source SHA-256: `f5f3f34a4bb335317e83645c54b8a9519b97492a681edeab61edb2baa1b028e9`. Full SCAMO experiment source fingerprint: `b3b183be997455f75974c85a2f968262f4acf270bcdcb6e74fda138f0bd10e0a`.
- The source fingerprints differ between experiments. Recorded CPU model, logical CPU count, total RAM, OS and Python match, but the runs occurred in separate sessions; this metadata does not prove identical effective performance. SCAMO metadata records batch index 0 with all 24 instances; avoid inferring two separately documented batches.
- Combined status: 41 Optimal, 127 Timeout. SCAMO alone: 9 Optimal, 15 Timeout. A nonempty `best_k` on Timeout is an incumbent, not a proven optimum.

The SCAMO checkpoint contains the original logs. Every nonempty SCAMO `best_k` was checked against the maximum valid SAT value in its corresponding log; all matched. `SHA256SUMS.txt` hashes these stored artifacts.
