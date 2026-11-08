# PROMPT TRIỂN KHAI MÔ PHỎNG XE GIAO HÀNG

## 1. Nhiệm vụ và phạm vi

Tiếp tục phát triển **TSP AI Route Optimizer** trong workspace hiện tại. Bổ sung tính năng **Delivery Simulation**: xe giao hàng 2D chạy theo kết quả tối ưu thật, có điều khiển phát, thống kê và sự kiện đồng bộ.

Trực tiếp đọc mã nguồn, tạo/chỉnh các tệp cần thiết, chạy kiểm thử và xác minh ứng dụng. Hoàn thành tính năng hoạt động được; không dừng ở kế hoạch hoặc giao diện minh họa.

Giữ các thuật toán, dữ liệu, benchmark và chức năng hiện có hoạt động. Không viết lại dự án, không thêm dịch vụ trả phí/API key và không sửa số liệu thực nghiệm để phục vụ animation. Ưu tiên một mô phỏng 2D ổn định, dễ trình diễn.

## 2. Kiểm tra codebase và dùng đúng dữ liệu

Trước khi sửa, đọc hướng dẫn trong repo và kiểm tra các module liên quan. Các điểm tích hợp hiện tại cần xác nhận lại bằng source:

- `src/tsp/models.py`: `Dataset`, `Location`, `OptimizationResult`.
- `src/tsp/services.py`: điều phối chạy các bộ giải.
- `src/tsp/ui/application.py`: điều hướng, `st.session_state`, dataset và kết quả đang dùng.
- `src/tsp/validation.py`: kiểm tra tuyến hợp lệ.
- `src/tsp/visualization/`: biểu đồ hiện có.

Hợp đồng dữ liệu cần giữ:

- `Dataset.locations` chứa tọa độ; `Dataset.depot_index` xác định kho. Kho có thể nằm ở bất kỳ hàng nào.
- `OptimizationResult.route` là tuyến **đã khép kín**, gồm chỉ số hàng của dataset: `[depot_index, ..., depot_index]`. Đây không phải danh sách ID và không mặc định kho bằng `0`.
- Kết quả thật đang được lưu trong session. Bộ chọn thuật toán mô phỏng lấy từ những kết quả này, ưu tiên GA, Nearest Neighbor và Random Search; có thể hỗ trợ các bộ giải còn lại nếu cùng hợp đồng.
- Chọn tuyến đã có, Play, Pause, tua hoặc đổi tốc độ phát **không gọi lại bộ giải**. Trong luồng mô phỏng, chỉ chạy tối ưu khi người dùng thực hiện hành động chạy tối ưu rõ ràng. Giữ cơ chế tính mẫu một lần khi khởi tạo phiên hiện có của ứng dụng.
- Nếu chưa có kết quả phù hợp, hiển thị empty state và hướng dẫn chạy tối ưu; không tạo tuyến giả hoặc tự nhận một tuyến là tối ưu toàn cục.

## 3. Trải nghiệm demo

Thêm mục **Delivery Simulation** vào điều hướng và một lối vào dễ thấy từ Dashboard. Tận dụng dataset/kết quả đang có để người dùng có thể chọn tuyến và nhấn Play ngay.

Bố cục:

- **Trên cùng:** bộ chọn kết quả đã tính, tên thuật toán, seed, số khách hàng và tổng khoảng cách.
- **Khu vực chính:** bản đồ tọa độ 2D và bảng trạng thái xe bên cạnh.
- **Bên dưới:** playback controls, thanh tua và timeline sự kiện.
- Bảng địa điểm có thể thu gọn để bản đồ đủ lớn trên laptop 1366 × 768; màn hình hẹp chuyển bảng trạng thái xuống dưới.

Dùng màu sắc, typography và khoảng cách của dashboard hiện tại. Xe là SVG van/truck nhìn từ trên xuống, đầu xe rõ ràng, xoay theo hướng đi; không thay xe bằng một chấm. Có nhãn `Vehicle 01`, icon kho riêng, tên/ID và thứ tự ghé thăm.

Bản đồ hiển thị toàn tuyến, phần đã đi, phần còn lại, điểm đến hiện tại và vị trí xe. Click địa điểm mở thông tin ID, tên, tọa độ, thứ tự và trạng thái. Giữ tỷ lệ hai trục bằng nhau, có fit/reset view và không để icon che mất nhãn quan trọng.

Hiển thị rõ đây là **mô phỏng Euclid theo đơn vị tọa độ**, không phải đường bộ, km hay ETA giao hàng ngoài thực tế.

## 4. Một mô hình thời gian duy nhất

Tiền xử lý tuyến thành một lịch trình xác định gồm các pha `travel` và `service`. Mỗi khách hàng có thời gian dừng giao hàng; đoạn cuối là quay về kho, không tạo thêm một đơn giao tại kho.

Quy ước:

```text
L_i = khoảng cách Euclid của đoạn i
v   = vận tốc cơ sở, đơn vị tọa độ / giây mô phỏng, v > 0
d   = thời gian dừng tại mỗi khách hàng, giây mô phỏng, d >= 0
r   = hệ số phát: 0.5, 1, 2 hoặc 4
T   = sum(L_i / v) + số_khách_hàng * d
t   = thời điểm mô phỏng hiện tại, được chặn trong [0, T]
```

Trong phiên đã bắt đầu, `t` là nguồn dữ liệu duy nhất để suy ra vị trí, pha, quãng đường, đơn đã giao và sự kiện. Trước lần Play đầu tiên, trạng thái idle giữ mọi khách hàng Pending và chưa ghi sự kiện xuất phát. Không duy trì các bộ đếm độc lập có thể lệch nhau.

Trong đoạn đang chạy, với tỷ lệ đoạn `u` thuộc `[0, 1]`:

```text
position = (1-u) * start + u * end
heading  = atan2(end.y - start.y, end.x - start.x)
```

Thời gian chạy mỗi đoạn phải tỷ lệ với chiều dài. Khi dừng giao hàng, `t` tăng nhưng vị trí và quãng đường giữ nguyên. Đổi hướng xe theo vector di chuyển; nếu làm mượt góc quay, dùng góc quay ngắn nhất và không làm xe rời tuyến.

Phân biệt hai loại tiến độ:

- **Tiến độ thời gian / thanh tua:** `t / T`, có tính thời gian dừng.
- **Tiến độ quãng đường:** `distance_traveled / total_distance`, không tính thời gian dừng.

Thống kê phải thỏa `distance_traveled + remaining_distance ≈ total_distance`. Thời gian mô phỏng còn lại là `T - t`; thời gian phát còn lại tại hệ số hiện tại là `(T - t) / r`. Ghi đúng tên chỉ số, không gọi các giá trị này là thời gian giao hàng thực tế.

Vận tốc cơ sở và hệ số phát là hai cấu hình khác nhau. Đổi hệ số phát phải giữ nguyên vị trí và thời điểm hiện tại, rồi tiếp tục bằng tốc độ mới; hệ số này áp dụng cho cả di chuyển và thời gian dừng.

Demo mẫu 6–12 khách hàng nên dễ quan sát và hoàn tất khoảng 20–40 giây ở 1x. Có thể bổ sung Auto-fit demo để tính vận tốc từ tuyến tham chiếu. Nếu so sánh các tuyến, phải giữ chung vận tốc cơ sở và thời gian dừng; không tự điều chỉnh từng tuyến về cùng thời lượng rồi diễn giải như một phép so sánh tốc độ thuật toán.

## 5. Trạng thái và điều khiển chính xác

Tách **trạng thái phát** `idle / playing / paused / stopped / completed` khỏi **pha hành trình** `at_depot / moving / delivering`. UI có thể hiển thị cả hai, ví dụ `Paused · Delivering`.

| Điều khiển | Hành vi |
|---|---|
| Play | Bắt đầu từ idle; tiếp tục từ paused hoặc stopped. Có thể đổi nhãn thành Resume. |
| Pause | Chốt thời điểm hiện tại và giữ nguyên vị trí, đơn đã giao, quãng đường. |
| Stop | Dừng đồng hồ, giữ nguyên tiến trình và chuyển sang stopped; không đưa xe tức thời về kho. |
| Restart | Đưa về thời điểm 0, đặt xe tại kho, xóa tiến trình và trở về idle; không tự phát. |
| Speed | Chọn 0.5x, 1x, 2x, 4x mà không reset hoặc nhảy vị trí. |
| Seek | Kéo thanh tua sẽ tạm dừng; cập nhật toàn bộ trạng thái theo thời điểm được chọn. Thả thanh vẫn paused; tua đến cuối thì completed. |

Disable các thao tác không hợp lệ. Khi completed, dùng Restart để chạy lại. Gọi lại Pause/Stop khi đã ở trạng thái đó không phát sinh tác dụng phụ.

Địa điểm đi qua các trạng thái `Pending → In Transit → Delivering → Delivered`. Chỉ Delivered sau khi hết thời gian dừng. Tua lùi phải hoàn nguyên đúng trạng thái và số đơn đã giao. Kho không tính vào completed deliveries.

Chỉ `completed` sau khi đã giao đủ khách hàng **và quay về kho**. Có thể xảy ra trạng thái giao đủ đơn nhưng xe vẫn đang quay về.

Các trường hợp biên bắt buộc:

- Đoạn dài 0: không chia cho 0, không sinh NaN; đến nơi tức thời và vẫn xử lý thời gian giao hàng.
- Khi không có vector di chuyển, giữ hướng hợp lệ trước đó hoặc hướng mặc định.
- Tất cả đoạn và thời gian dừng bằng 0: ban đầu vẫn idle, 0%; khi Play, xử lý các sự kiện tức thời theo thứ tự tuyến và chuyển completed, 100%, không lặp vô hạn.
- Tại ranh giới các pha, định nghĩa thứ tự arrival → delivery completed → departure rõ ràng; không giao một đơn hai lần.

## 6. Timeline và tính nhất quán

Tạo trước danh sách sự kiện có timestamp và ID ổn định từ lịch trình: xuất phát, đến khách hàng, hoàn tất giao hàng, rời khách hàng, về kho, hoàn tất hành trình.

Timeline hiển thị các sự kiện đã đạt tại thời điểm đang xem. Tua lùi ẩn sự kiện tương lai; phát lại hiển thị cùng các sự kiện đó, không append bản sao. Sự kiện cùng timestamp có thứ tự ổn định theo tuyến và loại sự kiện.

Nếu ghi thao tác Play/Pause/Seek, tách chúng khỏi timeline giao hàng để không nhầm việc xem lại với một lần giao hàng mới.

Bảng trạng thái gồm: vị trí `(x, y)`, điểm đến/pha hiện tại, đơn đã giao/tổng đơn, đơn còn lại, quãng đường đã đi/còn lại/tổng, tiến độ thời gian, thời gian mô phỏng đã qua/còn lại và trạng thái phát. Tất cả lấy từ cùng snapshot với xe trên bản đồ.

## 7. Frontend và Streamlit

Animation chạy trong **một frontend component tích hợp thật**, dùng SVG/Canvas và đồng hồ như `requestAnimationFrame`. Bản đồ, xe, thống kê, controls và timeline cập nhật đồng bộ trong component; Python không điều khiển từng frame.

- Không dùng vòng lặp Python blocking, `sleep` liên tục, rerun toàn trang mỗi frame hoặc dựng lại toàn bộ Plotly chart để chạy xe.
- Chọn API component phù hợp phiên bản Streamlit thực tế; kiểm tra tài liệu chính thức khi cần. Dùng cách tích hợp nhỏ nhất đáp ứng được dữ liệu và trạng thái, không tự thay web framework.
- Python truyền dataset, kết quả đã chọn, lịch trình/cấu hình và khóa định danh. Frontend quản lý đồng hồ phát; đồng bộ checkpoint khi Pause, Stop, Seek, Restart, Completed hoặc một tần suất thấp nếu cần. Không gửi frame về Python.
- Nếu có logic cùng tồn tại ở Python và JavaScript, chia sẻ lịch trình và dùng các fixture kỳ vọng chung để kiểm tra chúng cho cùng kết quả; không để hai bên tự suy ra hai tuyến khác nhau.
- Khóa mô phỏng phải nhận diện dataset fingerprint, kết quả/lần chạy, thuật toán, tuyến và cấu hình làm đổi lịch trình như vận tốc cơ sở/thời gian dừng. Hệ số phát không làm đổi khóa.
- Đổi dataset, kết quả hoặc cấu hình lịch trình: dừng phiên cũ, reset và bỏ checkpoint cũ. Đổi tuyến đã lưu không chạy lại thuật toán.
- Rerun giao diện thông thường không reset mô phỏng. Nếu component bị remount, phục hồi từ checkpoint hợp lệ ở trạng thái paused; không tự chạy tiếp từ trạng thái không chắc chắn. Reload toàn phiên có thể reset và phải được ghi rõ.
- Khi tab trình duyệt bị ẩn, tạm dừng để tránh xe nhảy một quãng lớn khi quay lại. Hủy animation loop và event listeners khi component bị tháo; không để hai vòng animation chạy đồng thời.
- Tên địa điểm từ CSV phải được render như text, không chèn trực tiếp vào HTML/SVG không escape.

Mục tiêu là xe mượt ở khoảng 30 FPS trên dữ liệu demo; không đánh đổi việc điều khiển được để cố đạt 60 FPS. Chỉ công bố chỉ số hiệu năng khi đã đo.

## 8. Tổ chức mã

Tách logic lịch trình/nội suy khỏi UI. Cấu trúc gợi ý, điều chỉnh theo repo để tránh chia quá nhiều file chỉ có vài dòng:

```text
src/tsp/simulation/
    models.py          # cấu hình, lịch trình, snapshot
    timeline.py        # pha di chuyển/dừng, sự kiện, nội suy xác định
    component.py       # cầu nối Streamlit và checkpoint
    frontend/          # xe SVG, bản đồ, playback, thống kê, timeline
src/tsp/ui/
    ...                # trang Delivery Simulation và điểm tích hợp
tests/
    ...                # logic, frontend và tích hợp phù hợp
docs/simulation_design.md
```

Không viết toàn bộ trong `app.py`. Có type hints/docstrings cho phần Python, validation cho tham số và error handling tại ranh giới dữ liệu.

## 9. Kiểm thử và xác minh

Kiểm thử bằng thời gian xác định/fake clock, không dùng chờ thời gian thật để chứng minh logic. Bao phủ:

1. Xuất phát đúng kho, kể cả kho không nằm ở hàng 0; đi đúng thứ tự kết quả, về đúng kho.
2. Nội suy đúng ở đầu/giữa/cuối đoạn và trong thời gian dừng; không Delivered trước khi hết dừng.
3. Pause giữ nguyên; Resume tiếp tục; Stop giữ tiến trình; Restart reset.
4. 2x hoàn thành trong một nửa **thời gian phát** của 1x với cùng lịch trình; đổi tốc độ giữa chừng không nhảy vị trí.
5. Seek tiến/lùi cập nhật đồng bộ xe, màu tuyến, đơn đã giao, thời gian và sự kiện.
6. Bảo toàn tổng khoảng cách trong sai số số học, ETA không âm, chỉ hoàn tất sau khi quay về kho.
7. Một khách hàng, tọa độ trùng nhau, đoạn dài 0, dwell bằng 0 và toàn bộ hành trình thời lượng 0.
8. Không nhân đôi sự kiện hoặc animation loop; không gọi GA/NN/Random Search từ thao tác playback/đổi tuyến đã lưu.
9. Đổi dataset/kết quả/cấu hình không dùng lại checkpoint cũ; rerun thông thường không reset ngoài ý muốn.

Chạy lại bộ kiểm thử hiện có; không hard-code số lượng test, không xóa test thất bại. Kiểm thử frontend bằng công cụ sẵn có nếu khả dụng: chỉ Python tests hoặc Streamlit AppTest không đủ để khẳng định JavaScript animation và nút bấm hoạt động.

Xác minh khởi động Streamlit và thao tác demo trong trình duyệt nếu có công cụ. Nếu không có browser, báo rõ phần chưa xác minh; không bịa screenshot/GIF hoặc tuyên bố animation đã được kiểm tra trực quan.

## 10. Quy trình và bàn giao

Thực hiện lần lượt:

1. Kiểm tra source và tạo checklist ngắn.
2. Xây lịch trình/nội suy/trạng thái, viết kiểm thử xác định.
3. Làm frontend và tích hợp với kết quả đang lưu.
4. Hoàn thiện controls, timeline, checkpoint và các trạng thái biên.
5. Chạy tests, sửa lỗi, xác minh khởi động và demo.
6. Cập nhật README, `docs/simulation_design.md` và phần báo cáo liên quan; giữ nguyên kết quả benchmark đã đo. Chỉ bổ sung ảnh/GIF thật khi đã tạo và kiểm tra được.

Một tính năng chỉ hoàn thành khi xe đi đúng tuyến, controls thực sự hoạt động, số liệu đồng bộ, không chạy lại solver ngoài ý muốn và các chức năng cũ vẫn hoạt động.

Cuối cùng báo cáo ngắn gọn: tính năng/tệp đã thay đổi, lệnh và kết quả kiểm thử thực tế, cách mở demo; tách rõ **đã triển khai và xác minh**, **đã triển khai nhưng chưa xác minh**, **chưa triển khai**. Không trình bày chức năng giả lập hoặc placeholder như đã hoàn thành.

**Bắt đầu triển khai trong codebase hiện tại. Ưu tiên một luồng demo hoàn chỉnh từ chọn kết quả → Play → giao hàng → quay về kho, rồi hoàn thiện các kiểm soát và kiểm thử còn lại.**
