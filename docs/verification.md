# Xác minh bản cơ sở

Tài liệu này ghi lần xác minh 79 kiểm thử của bản cơ sở trước khi bổ sung mô phỏng. Trạng thái mới nhất gồm 117 kiểm thử Python và 24 kiểm thử JavaScript nằm trong [xác minh Delivery Simulation](simulation_verification.md).

Ngày kiểm tra: 07/11/2026 (Asia/Saigon). Môi trường đã thực thi: Windows, Python 3.14.4. Các phiên bản gói dùng cho thực nghiệm nằm trong `results/final/metadata.json`.

## Đã thực hiện và xác minh

- Toàn bộ bộ kiểm thử: **79 passed in 18.92s**. Lệnh: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/release_qa_03`. Tùy chọn cache và basetemp phục vụ quyền thư mục tạm của môi trường kiểm tra; khi chạy bình thường có thể dùng `python -m pytest`.
- 64 kiểm thử lõi, 10 kiểm thử evaluation/visualization và 5 kiểm thử dịch vụ/giao diện. Bao gồm hình vuông tối ưu 4, kho ở hàng bất kỳ, OX/inversion, elitism, seed, ngân sách, CSV, tham số, serialization và biểu đồ hội tụ GA/Random Search trên cùng trục evaluations.
- Streamlit AppTest đi qua cả 6 trang, nhập dữ liệu thủ công, chạy tối ưu, xử lý dữ liệu sai và chạy benchmark từ form.
- Điều hướng và đổi snapshot thế hệ giữ nguyên kết quả, runtime đã lưu và số lần chạy. Khi áp dụng dataset mới, kết quả cũ được xóa khỏi phiên.
- Dữ liệu xuất JSON, CSV, PNG và Plotly figures được kiểm tra qua các bài kiểm thử. Ảnh tuyến PNG được tạo bằng Matplotlib, không cần Kaleido.
- Máy chủ Streamlit đã khởi động tại `http://127.0.0.1:8501`; endpoint `/_stcore/health` trả HTTP 200.
- `python -m pip check` trả `No broken requirements found` sau khi cài dependencies ứng dụng.
- Benchmark thật: 4 bộ dữ liệu cố định, mỗi bộ 10 lần GA và 10 lần Random Search. Tổng cộng 80 lần ngẫu nhiên và 10 kết quả xác định, không nhân bản các lần chạy xác định.
- 40 cặp GA/Random Search đều có ngân sách 19.700 lượt đánh giá tuyến. 90 tuyến trong JSON được kiểm tra lại tính hợp lệ và tổng khoảng cách. 40 lịch sử GA đều có 201 snapshot (gồm thế hệ 0), giữ khoảng cách tốt nhất không tăng.
- Các tệp raw JSON/CSV, summary, metadata, dataset, nhận xét tự sinh, PNG và HTML ngoại tuyến đã được lưu trong `results/`.
- Báo cáo PDF 9 trang đã xuất bằng ReportLab, render đủ 9 trang qua PyMuPDF và kiểm tra ảnh từng trang. Công thức được chuyển sang ký hiệu ASCII tương đương khi cần để tránh thiếu glyph. Nội dung thuyết trình 12 slide có ghi chú và số liệu thật tại `presentation/slides.md`.

## Đã triển khai nhưng chưa kiểm tra trực quan

CSS dashboard, bố cục responsive, hover/zoom/reset và nút tải ảnh trên Plotly đã được triển khai. Giao diện tạo thành công qua AppTest và Figure JSON hợp lệ. Phiên công cụ này không cung cấp trình duyệt (`cua.getState()` trả danh sách browsers rỗng), nên chưa thể xác nhận bằng ảnh chụp màn hình, kiểm tra responsive hoặc thao tác tải file thực tế trong trình duyệt.

## Các phần không triển khai

- Light theme và animation thời gian thực; GA Lab sử dụng snapshot slider hoạt động.
- Dịch vụ bản đồ đường bộ, nhiều xe, tải trọng, thời gian giao hàng, traffic: ngoài phạm vi TSP Euclid của đề tài.
- Xuất DOCX/PPTX: môi trường không cung cấp artifact runtime mà các hướng dẫn Word/Presentations yêu cầu. Có báo cáo Markdown/PDF và nội dung thuyết trình Markdown; xem `report/README.md` để tạo lại PDF.

Không có kết luận GA luôn tốt hơn. Ở bộ 20 khách hàng của thực nghiệm này, GA thua NN trong 3/10 lần, với cải thiện trung bình −0,090%.
