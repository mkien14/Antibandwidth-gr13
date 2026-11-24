# SAT Encodings for the Antibandwidth Problem

Nghiên cứu bài toán Antibandwidth (ABP) với ba mã hóa SAT incremental và bốn phương pháp tối ưu trực tiếp.

| Thư mục | Nội dung |
| --- | --- |
| `src/` | Các bộ giải Pairwise, Order, SCAMO SCL/NSC, CPLEX CP, CPLEX MIP, Gurobi, CP-SAT và đọc đồ thị. |
| `data/hb/` | 24 đồ thị Harwell–Boeing dùng trong benchmark. |
| `experiments/benchmark/` | Runner, kiểm tra, audit SCAMO, notebook Kaggle và trực quan hóa. |
| `experiments/results/kaggle/` | Kết quả, checkpoint và metadata thực nghiệm. |
| `report/` | Nguồn LaTeX và PDF báo cáo cục bộ; hiện bị Git bỏ qua. |
| `tests/` | Kiểm tra các phương pháp. |
| `docs/` | Ghi chú bàn giao cục bộ; Git bỏ qua thư mục này. |

## Kết quả dùng trong báo cáo

Sử dụng [`experiments/results/kaggle/report_scl_nsc/results.csv`](experiments/results/kaggle/report_scl_nsc/results.csv)
để phân tích 24 đồ thị và bảy phương pháp. Bộ này ghép 24 hàng SCAMO SCL/NSC mới với 144 hàng của sáu phương pháp từ thí nghiệm trước. Nguồn, giới hạn và checksum được ghi trong [README bộ kết quả](experiments/results/kaggle/report_scl_nsc/README.md). Một `best_k` ở trạng thái `Timeout` là nghiệm tốt nhất được ghi nhận, không phải giá trị tối ưu đã chứng minh.

## Thực nghiệm và hình vẽ

- [`experiments/benchmark/kaggle/abp_kaggle.ipynb`](experiments/benchmark/kaggle/abp_kaggle.ipynb) là notebook benchmark chính. Xem [hướng dẫn benchmark](experiments/benchmark/README.md) trước khi chạy lại.
- `experiments/benchmark/visualize/thu.ipynb` là notebook vẽ cục bộ và được Git bỏ qua; hình xuất ra nằm trong `experiments/benchmark/visualize/figures/`.
- `experiments/benchmark/sat_vs_ilp_cp.csv` và `experiments/benchmark/logs/` là output của runner cục bộ, không phải CSV tổng hợp dùng cho báo cáo.
- CPLEX và Gurobi cần runtime và giấy phép phù hợp. Không đưa giấy phép, secret hay log nhạy cảm vào Git.

Trong workspace có thể xem `docs/CODEX_HANDOFF.md` để biết ngữ cảnh và các quyết định đã thống nhất; thư mục này được Git bỏ qua.
