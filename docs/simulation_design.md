# Thiết kế mô phỏng phương tiện giao hàng

## Mục đích và phạm vi

Delivery Simulation phát lại một kết quả tuyến đã tính trong TSP AI Route Optimizer. Xe xuất phát tại kho, đi theo đúng thứ tự các chỉ số trong `OptimizationResult.route`, dừng giao hàng tại từng khách hàng rồi quay lại kho. Mô phỏng không tìm thêm lời giải và không đổi tập tọa độ.

Mô hình là một xe trên mặt phẳng Euclid. Khoảng cách dùng đơn vị tọa độ; thời gian là thời gian mô phỏng được chọn từ vận tốc cơ sở và thời gian dừng. Đây không phải khoảng cách đường bộ, ETA giao hàng thực tế hay chi phí vận tải đã được xác minh ngoài thực địa.

## Hợp đồng tuyến và danh tính phiên

`Dataset.depot_index` xác định kho, có thể khác 0. `OptimizationResult.route` là danh sách **chỉ số hàng**, có kho ở cả hai đầu. `build_schedule` gọi kiểm tra tuyến và tính lại tổng khoảng cách trên dataset; nếu khoảng cách không khớp kết quả đã ghi, mô phỏng từ chối dữ liệu đó.

Khóa `route_key` được băm từ dataset fingerprint, thuật toán, tuyến, số lần chạy tối ưu và cấu hình vật lý. Thay một thành phần này tạo khóa khác để checkpoint của tuyến cũ không thể áp dụng vào tuyến mới. Hệ số tốc độ phát không nằm trong khóa vì nó không thay lịch trình.

## Kiến trúc

| Thành phần | Vai trò |
|---|---|
| `simulation/models.py` | `SimulationConfig`, kiểm tra vận tốc và thời gian dừng |
| `simulation/timeline.py` | Tạo các pha, điểm dừng và sự kiện; nội suy snapshot bằng thời gian xác định |
| `simulation/component.py` | Cầu nối giữa session Streamlit và frontend component |
| `simulation/frontend/engine.js` | Sampler JavaScript và playback controller dùng đồng hồ có thể thay bằng fake clock |
| `simulation/frontend/app.js` | Gắn controls, SVG, số liệu, timeline và giao tiếp với Streamlit |
| `simulation/frontend/styles.css` | Bố cục responsive và màu sắc thống nhất dashboard |
| `tests/fixtures/simulation_cases.json` | Lịch trình và giá trị kỳ vọng độc lập dùng chung giữa Python và JavaScript |

Python tạo lịch trình một lần khi dữ liệu đầu vào thay đổi. Frontend nhận lịch trình đó và tự cập nhật xe cùng các chỉ số. Animation không gọi GA, NN hoặc Random Search và không gửi từng frame về Python.

## Lịch trình và nội suy

Với chiều dài đoạn `L_i`, vận tốc cơ sở `v > 0`, thời gian dừng `d >= 0` và `n` khách hàng:

```text
travel_duration_i = L_i / v
total_duration = sum(travel_duration_i) + n * d
```

Lịch trình xen kẽ `travel` và `service`. Đoạn cuối quay về kho không có service. Mỗi pha giữ thời gian bắt đầu/kết thúc, chỉ số đầu/cuối, khoảng cách tích lũy và hướng xe. Các pha có độ dài hoặc thời lượng 0 vẫn được biểu diễn để bảo toàn thứ tự sự kiện.

Trong pha travel, tỷ lệ `u = (t - start_time) / (end_time - start_time)` được chặn vào `[0,1]`; vị trí là `(1-u) * start + u * end`. Hướng xe là `atan2(dy, dx)`. Nếu đoạn dài 0, giữ hướng hợp lệ trước đó thay vì chia cho 0.

Khoảng thời gian của pha là nửa kín `[start_time, end_time)`. Tại thời điểm đến nơi, xe chuyển sang service; tại thời điểm kết thúc service, khách hàng được đánh dấu Delivered và pha tiếp theo bắt đầu. Sampler bỏ qua pha có thời lượng 0 khi chọn pha đang hoạt động. Các sự kiện tức thời vẫn tồn tại và giữ thứ tự tuyến.

Một snapshot chứa vị trí, hướng, pha, điểm đến, số đơn đã giao/còn lại, quãng đường đã đi/còn lại, hai loại tiến độ, thời gian và các ID sự kiện đang thấy. Những dữ liệu này đều được suy ra từ cùng một thời điểm; không có bộ đếm giao hàng độc lập tích lũy qua frame.

## Trạng thái phát và trạng thái xe

Trạng thái phát và pha hành trình được tách riêng:

- Playback: `idle`, `playing`, `paused`, `stopped`, `completed`.
- Pha: `at_depot`, `moving`, `delivering`.
- Địa điểm: `Pending`, `In Transit`, `Delivering`, `Delivered`; kho là `Warehouse`.

Ở idle, xe ở kho, thời điểm bằng 0, khách hàng đều Pending và timeline chưa có sự kiện. Play bắt đầu hoặc tiếp tục; Pause và Stop giữ nguyên thời điểm. Restart đặt về idle, xóa tiến độ phát và không tự chạy. Play ở completed không chạy lại; cần Restart.

Seek chọn một thời điểm tuyệt đối, tạm dừng và dựng lại snapshot. Seek đến cuối chuyển completed. Vì kết quả được suy ra từ thời gian, tua lùi hoàn nguyên cả trạng thái Delivered, quãng đường và sự kiện tương lai. Hoàn tất giao đủ đơn chưa có nghĩa hoàn thành hành trình: xe còn phải đi đoạn về kho.

## Đồng hồ, vận tốc và tốc độ phát

Vận tốc cơ sở có đơn vị tọa độ trên giây mô phỏng. Hệ số phát 0.5x, 1x, 2x hoặc 4x điều khiển tốc độ trôi của đồng hồ và áp dụng cho cả travel lẫn service. Đổi hệ số chốt thời điểm theo hệ số cũ trước, rồi đặt mốc mới; vị trí không nhảy khi đổi tốc độ.

Tiến độ thời gian bằng `elapsed / total_duration`; tiến độ khoảng cách bằng `distance_traveled / total_distance`. Trong lúc giao hàng, loại thứ nhất tăng nhưng loại thứ hai giữ nguyên. Thời gian mô phỏng còn lại bằng `total_duration - elapsed`; thời gian phát ước tính còn lại chia giá trị này cho hệ số hiện tại.

Nếu tổng thời lượng bằng 0, idle vẫn có tiến độ 0%. Khi Play, các sự kiện tức thời được xử lý theo thứ tự và trạng thái chuyển completed, tiến độ 100%. Không có vòng lặp di chuyển chờ một khoảng thời gian dương không tồn tại.

## Timeline sự kiện

Python tạo sự kiện có ID ổn định từ route key, số thứ tự và loại sự kiện: `started`, `departed`, `arrived`, `delivered`, `returned`, `completed`. Khách hàng có thể cùng tọa độ nhưng vẫn có sự kiện riêng theo thứ tự tuyến.

Timeline lọc danh sách theo timestamp. Nó không append một bản sao sự kiện khi Pause/Resume hay tua lại, nên cùng một lần giao không bị nhân đôi. Tại một thời điểm có nhiều sự kiện, thứ tự trong lịch trình xác định thứ tự hiển thị. Các thao tác điều khiển không được diễn giải thành một đơn giao mới.

## Frontend và phục hồi trạng thái

Frontend dùng SVG cho xe, kho, marker và đường đi; bộ điều khiển phát cập nhật từ đồng hồ monotonic. Vị trí, quãng đường, số đơn và timeline đọc cùng snapshot. Nhãn từ dataset phải được gắn như văn bản để CSV không trở thành mã HTML thực thi.

Checkpoint chứa route key, thời điểm, hệ số, trạng thái, dấu hiệu đã bắt đầu và sequence. Checkpoint khác route key bị bỏ qua. Khi phục hồi một phiên đã bắt đầu, frontend giữ vị trí và trở về paused; phiên đã đến cuối giữ completed. Rerun bình thường không tạo một bộ giải mới hoặc một animation loop thứ hai. Ẩn tab sẽ tạm dừng thay vì để xe nhảy quãng dài lúc quay lại.

Frontend giữ một checkpoint gần nhất trong browser sessionStorage khoảng một lần mỗi giây và khi điều khiển/pagehide. Chỉ các hành động điều khiển và hoàn tất gửi checkpoint về Python, nên lưu trong trình duyệt không gây rerun mỗi giây. Khi đổi route key, checkpoint cũ bị xóa. Khi khởi tạo lại, checkpoint cục bộ được so với checkpoint backend theo sequence rồi thời điểm; phiên đang chạy chỉ phục hồi ở paused.

## Chiến lược kiểm thử

Fixture chính được tính tay từ tam giác cạnh 3, 4, 5; kho ở hàng 1, tuyến `[1,0,2,1]`, vận tốc 1 và hai lần service dài 2. Khoảng cách đúng là 12 và thời lượng đúng là 16. Điểm `(3,0)` được đến ở giây 3, giao xong ở giây 5; điểm `(3,4)` được đến ở giây 9, giao xong ở giây 11; xe về kho ở giây 16.

Python và JavaScript cùng kiểm tra các giá trị kỳ vọng này. Một kiểm thử khác truyền lịch trình thật do Python tạo sang Node.js và đối chiếu các snapshot để phát hiện lệch giữa hai sampler. Kiểm thử fake clock xác minh Pause/Resume, Stop, Restart, Seek, đổi tốc độ liên tục và thời gian phát 2x mà không dùng chờ thời gian thật.

Các kiểm thử còn bao phủ: đoạn dài 0, toàn bộ thời lượng 0, một khách hàng, tham số không hữu hạn, tuyến sai, khoảng cách kết quả sai, khóa checkpoint và bảo toàn tổng khoảng cách.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_simulation.py
node --test tests/frontend/simulation.test.mjs
npm ci
npm run test:simulation
.\.venv\Scripts\python.exe -m pytest
```

Các bài kiểm thử logic và AppTest không thay thế việc xem animation trong trình duyệt. Trạng thái kiểm tra giao diện thực tế được ghi trong tài liệu xác minh bản bàn giao; không suy ra tốc độ FPS hoặc chất lượng responsive chỉ từ việc test logic đạt.

`simulation_dom.test.mjs` dùng jsdom và fake requestAnimationFrame để thực thi module frontend thật: bridge, nút bấm, tua, bảng số liệu, timeline, chọn địa điểm và lifecycle. Đây là kiểm tra DOM, không phải browser rendering. Tên địa điểm được kiểm tra bằng chuỗi chứa HTML để xác nhận chúng vẫn hiển thị như text.

## Giới hạn

Một xe, một kho, tốc độ cơ sở không đổi theo đoạn và thời gian service chung cho khách hàng. Không có mạng đường bộ, giao thông, tải trọng, thời gian giao hàng thực tế hay nhiều phương tiện. Thời gian mô phỏng giữa các thuật toán chỉ so sánh có ý nghĩa khi giữ cùng vận tốc và thời gian dừng. Chất lượng tối ưu và runtime tìm tuyến vẫn lấy từ kết quả solver đã đo, tách khỏi tốc độ phát animation.
