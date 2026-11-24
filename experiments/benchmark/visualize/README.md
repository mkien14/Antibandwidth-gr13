# Trực quan hóa kết quả

`thu.ipynb` là notebook làm việc cục bộ và được Git bỏ qua. CSV được chọn cho báo cáo nằm ở `experiments/results/kaggle/report_scl_nsc/results.csv`. Các hình được tạo bởi notebook nằm trong `figures/`; kiểm tra nội dung notebook và các hình trước khi đưa vào báo cáo.

Yêu cầu bài tập sử dụng `cnsplots`. Cài thư viện vào Python kernel của notebook theo [hướng dẫn cài đặt](https://cnsplots.farid.one/latest/installation.html). Đối với báo cáo LaTeX, có thể xuất PDF vector; PNG phù hợp để xem nhanh.

Khi phân tích, phân biệt `Optimal` với `Timeout`: `best_k` trên lượt Timeout là nghiệm tốt nhất được ghi nhận, chưa chứng minh tối ưu. CSV hiện tại không có số biến hay số mệnh đề, nên cần thu thập thêm nếu vẽ so sánh các chỉ số đó.
