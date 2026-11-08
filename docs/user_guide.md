# Hướng dẫn sử dụng

## Demo xe giao hàng

1. Mở Dashboard và chọn **Open delivery simulation**, hoặc chọn **Delivery Simulation** trong điều hướng.
2. Chọn kết quả từ **Simulation route**. Nếu chưa có kết quả, chạy tối ưu từ sidebar trước.
3. Nhấn Play. Xe xuất phát từ kho, chạy qua từng khách hàng, dừng giao hàng rồi quay về kho.
4. Pause/Resume để xem từng pha; Stop giữ nguyên tiến trình; Restart về thời điểm 0. Tua thanh Timeline progress sẽ tạm dừng và cập nhật cả trạng thái, đơn giao và sự kiện.
5. Chọn hệ số phát 0.5×, 1×, 2× hoặc 4×. Muốn đổi vận tốc cơ sở hoặc thời gian dừng, mở Journey settings và áp dụng; thao tác này reset mô phỏng.
6. Bấm marker hoặc một hàng trong Location manifest để xem ID, tên, tọa độ, thứ tự và trạng thái. Kéo bản đồ để pan, cuộn để zoom, Fit view để về khung ban đầu.

Màu tuyến cyan biểu thị phần đã đi. Delivered chỉ xuất hiện sau khi kết thúc thời gian dừng; giao đủ đơn vẫn chưa hoàn tất nếu xe còn đang quay về kho. Timeline progress tính theo thời gian, bao gồm dừng; Distance covered chỉ tính quãng đường. Các giá trị này có thể khác nhau.

Nút fit ~30 giây dùng tuyến đang chọn để hiệu chỉnh vận tốc cơ sở chung. Khi chuyển thuật toán, vận tốc và thời gian dừng được giữ nguyên để có thể so sánh. Tốc độ phát không phải thời gian chạy thuật toán hoặc thời gian giao hàng thực tế. Dữ liệu thay đổi thì cần tối ưu lại; chuyển giữa những kết quả đã tính không chạy lại bộ giải.

Ẩn tab sẽ tạm dừng. Khi component được tạo lại, vị trí được phục hồi từ checkpoint hợp lệ và giữ paused; reload toàn phiên Streamlit có thể bắt đầu lại. Hãy tải JSON nếu cần giữ lịch trình lâu dài.

## Khởi chạy

Từ thư mục dự án, chạy `python -m streamlit run app.py` bằng Python đã cài requirements. Nếu đang dùng môi trường ảo Windows: `.\.venv\Scripts\python.exe -m streamlit run app.py`. Mở địa chỉ được in trong terminal; dừng máy chủ bằng `Ctrl+C`.

## Dashboard

Dashboard tóm tắt bộ dữ liệu và lần chạy đã hoàn thành. Lần mở phiên đầu tiên chạy một phép tối ưu hóa thật trên dataset mặc định để có kết quả khám phá ngay. Các KPI gồm số địa điểm, khoảng cách tuyến đang chọn, runtime và mức cải thiện so với NN. Khoảng cách dùng đơn vị tọa độ. Thay đổi cấu hình không tự biến giá trị cũ thành kết quả mới.

Chọn dataset, seed và thuật toán ở vùng điều khiển, sau đó nhấn nút chạy. Dùng bảng kết quả để đọc cả khoảng cách và số đánh giá; thuật toán có khoảng cách nhỏ nhất không nhất thiết có runtime ngắn nhất.

## Route Playground

Tạo tọa độ ngẫu nhiên với số khách hàng và seed, chọn một bộ mẫu, tải CSV hoặc sửa bảng dữ liệu. Mỗi hàng là một địa điểm. `is_depot` đánh dấu kho; cần đúng một hàng được chọn. Lưu/áp dụng thay đổi trước khi chạy.

CSV phải có đủ `id,name,x,y,is_depot`. Ví dụ:

```csv
id,name,x,y,is_depot
D,Kho,0,0,true
A,Điểm A,1,0,false
B,Điểm B,1,1,false
```

ID phải duy nhất; tên không rỗng; x và y là số hữu hạn. Nếu dữ liệu bị từ chối, sửa cột/hàng được báo rồi áp dụng lại. Đừng dùng chuỗi tùy ý thay cho `true`/`false` trong cột kho.

Trong biểu đồ, kho có marker riêng. Rê chuột xem ID, tên và tọa độ; tuyến đóng về kho. Dùng công cụ Plotly để zoom, pan, reset axes và tải PNG. Thứ tự ghé thăm có thể đọc từ route hoặc bảng kết quả, bắt đầu và kết thúc tại kho.

## Genetic Algorithm Lab

- Population size: số cá thể trong quần thể.
- Generations: số thế hệ tối đa sau quần thể ban đầu.
- Crossover rate: xác suất lai mỗi cặp bố mẹ.
- Mutation rate: xác suất đảo đoạn mỗi con.
- Elitism count: số cá thể tốt nhất được giữ nguyên.
- Tournament size: số ứng viên tham gia mỗi lần chọn bố mẹ.
- Seed: seed cho thuật toán ngẫu nhiên, không phải cam kết tìm tối ưu.
- Early stopping patience: số thế hệ không cải thiện trước khi dừng; 0 tắt dừng sớm.

Sau khi chạy, dùng thanh trượt để chọn thế hệ đã lưu. Đây là phát lại lịch sử, không khởi chạy một lần tối ưu hóa mới. Best fitness càng lớn càng tốt; best distance càng nhỏ càng tốt. Average fitness được tính từ fitness từng cá thể.

## Algorithm Comparison

Xem các tuyến cạnh nhau và so sánh khoảng cách, runtime, evaluations. Improvement dương nghĩa là tốt hơn NN, âm nghĩa là kém hơn. Các thuật toán phải dùng cùng dataset; đổi tọa độ cần chạy lại trước khi so sánh.

NN + 2-opt là phương pháp riêng, không phải GA. Exact chỉ dùng tối đa 12 khách hàng. Ở bài toán lớn hơn, ứng dụng không có cơ sở để hiển thị optimality gap chính xác.

## Experiments & Analytics

Chọn số lần lặp và các kích thước 5, 10, 20, 30 khách hàng. Benchmark dùng cấu hình GA đã áp dụng ở lần tối ưu gần nhất; nếu cần cấu hình khác, áp dụng bằng Run optimization trước. Một benchmark có thể mất nhiều thời gian hơn một lần tối ưu vì chạy nhiều seed. Đợi thông báo hoàn thành trước khi xuất bảng. Đọc mean, standard deviation và worst distance cùng best distance để thấy độ ổn định.

Khi chưa chạy benchmark trong phiên, trang hiển thị release benchmark đã lưu trong `results/`. Benchmark mới từ giao diện được lưu riêng trong `results/interactive/`, giữ nguyên thí nghiệm đi kèm bản phát hành. Các tệp raw cần được giữ cùng summary để có thể kiểm tra kết luận. Nếu dùng benchmark có sẵn, xem metadata và cấu hình của chính benchmark đó; đừng gán cấu hình widget hiện tại cho các số liệu đã lưu trước đây.

## Xuất và tái lập

Tải CSV dataset để giữ tọa độ. Tải JSON kết quả để giữ seed, cấu hình, route và history. Lưu CSV bảng chỉ số để đưa vào báo cáo; dùng Plotly download hoặc hình benchmark để xuất biểu đồ.

Để tái lập: dùng đúng dataset, seed, cấu hình và phiên bản thư viện. Runtime không cần giống nhau. Thay đổi thứ tự hàng trong CSV có thể đổi cách phá hòa, nên giữ nguyên dataset đã xuất nếu cần đối chiếu chính xác.

## Giới hạn

Ứng dụng giải TSP Euclid một xe quay về kho. Không mô hình hóa đường cấm, giao thông, tải trọng, thời gian phục vụ hoặc nhiều xe. GA và 2-opt không chứng minh tối ưu toàn cục. Dữ liệu/kết quả giao diện được giữ trong phiên Streamlit; xuất tệp trước khi đóng phiên nếu cần lưu lâu dài.
