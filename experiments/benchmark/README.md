# Benchmark

- `run_sat_vs_ilp_cp.py`: chạy các phương pháp theo cấu hình ở đầu file. Lệnh `python experiments/benchmark/run_sat_vs_ilp_cp.py` dùng giới hạn và output được cấu hình trong file; đọc các giá trị trước khi chạy. Runner mặc định ghi CSV và log tại đây.
- `audit_scamo_structure.py`: audit cấu trúc SCAMO; kết quả không phải số đo thời gian benchmark.
- `test_benchmark.py`: kiểm tra runner.
- `kaggle/abp_kaggle.ipynb`: nguồn notebook Kaggle. Kiểm tra notebook và hash SCAMO bằng `python experiments/benchmark/kaggle/sync_notebook.py --check`. Để tạo file các cell cục bộ, dùng `--export`; file này được Git bỏ qua.
- `kaggle/abp_kaggle_source.zip`: gói nguồn/dữ liệu Kaggle được giữ với cấu trúc `abp_source/benchmark/` như thí nghiệm đã chạy. Thư mục benchmark trong ZIP khác vị trí của runner local; khi cập nhật gói cho thí nghiệm mới phải đối chiếu hash và cấu hình checkpoint.
- `visualize/`: notebook và hình kết quả; xem [hướng dẫn](visualize/README.md).

Khi tiếp tục một thí nghiệm, dùng checkpoint và cấu hình phù hợp với chính thí nghiệm đó. CSV tổng hợp `report_scl_nsc` được ghép từ hai thí nghiệm và không dùng làm checkpoint resume.
