# Xác minh tính năng Delivery Simulation

Ngày 07/11/2026, múi giờ Asia/Saigon. Đây là trạng thái bản bổ sung mô phỏng; dữ liệu benchmark gốc được giữ nguyên.

## Đã triển khai và xác minh

- **117 kiểm thử Python đạt trong 12,59 giây**: `python -m pytest -q -p no:cacheprovider --basetemp=tmp/simulation_final_02`. Gồm 79 ca gốc, 33 ca lịch trình/nội suy/đối chiếu Python–JavaScript, 3 ca tích hợp ứng dụng/checkpoint và 2 ca chống lỗi định dạng công thức khi xuất PDF.
- **24 kiểm thử JavaScript đạt** qua `npm run test:simulation`. Gồm 21 ca snapshot/fake clock và 3 ca DOM dùng jsdom để thực thi các handler frontend thật. Lần chạy sau cùng hoàn tất khoảng 2,92 giây.
- DOM kiểm tra bridge componentReady/setComponentValue, SVG van, Play/Pause/Resume/Stop/Restart, tốc độ, tua và hoàn tất; kiểm tra màu/trạng thái, số liệu, timeline không nhân đôi, chọn marker/manifest, pan/reset, echo không tạo loop thứ hai, remount paused, tab ẩn và escape tên từ CSV.
- Tam giác tính tay 3–4–5 có kho ở hàng 1: tuyến dài 12, hai lần service 2 giây, vận tốc 1, tổng 16 giây. Python và JavaScript khớp các mốc độc lập ở đầu, giữa, cuối các pha.
- Kiểm tra dữ liệu cùng tọa độ, đoạn dài 0, service 0, tổng thời lượng 0; bảo toàn quãng đường; checkpoint sai khóa/không hữu hạn bị từ chối.
- Chuyển giữa GA, NN, Random Search dùng đúng route kết quả, giữ chung vận tốc cơ sở và không tăng số lần chạy tối ưu. Cấu hình lịch trình thay đổi tạo route key mới.
- `python -m pip check` trả `No broken requirements found`. Frontend chạy trực tiếp, không cần npm lúc chạy ứng dụng.
- Máy chủ Streamlit được khởi động lại để bỏ code cũ trong bộ nhớ. Health endpoint trả HTTP 200. Kiểm tra giao thức trên máy chủ thật mở được trang thứ bảy Delivery Simulation, nhận component `tsp.simulation.component.delivery_simulation`; `index.html`, `app.js`, `engine.js`, `styles.css` đều trả HTTP 200 với MIME đúng.
- Lịch trình demo thực từ server: GA, 20 khách hàng, 372,61089697508004 đơn vị tọa độ, 30,000000000000004 giây mô phỏng. Chênh lệch cuối là sai số số thực; tuyến không bị thay đổi để khớp thời lượng.
- PDF cập nhật có 10 trang; đã render và xem từng trang, có phần 12.1 về mô phỏng và không phát hiện lỗi glyph/cắt chữ/bảng. Nội dung trình chiếu 12 slide đã cập nhật kịch bản demo xe.

## Đã triển khai nhưng chưa xác minh trực quan

Animation dùng requestAnimationFrame với mục tiêu cập nhật khoảng 30 FPS. CSS có bố cục responsive, SVG giữ tỷ lệ trục, zoom/pan/reset và nhãn phương tiện. Kiểm tra DOM không thực hiện layout hay đo FPS thực tế. Công cụ CUA trả danh sách browsers rỗng, nên chưa xem hoặc chụp được giao diện thực tế trên trình duyệt. Không có screenshot/GIF giả và chưa có số liệu hiệu năng trình duyệt.

## Giới hạn vận hành

Một xe, một kho, các đoạn thẳng Euclid, vận tốc cơ sở không đổi và service time chung cho mọi khách. Seek tạm dừng; Stop giữ tiến trình; Restart về idle. Remount khôi phục checkpoint hợp lệ ở paused; reload cả phiên Streamlit có thể reset. Node.js và jsdom là công cụ kiểm thử phát triển, không phải dependency của ứng dụng Python khi chạy demo.
