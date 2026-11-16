# Kiểm chứng và bàn giao bản đồ thực tế

Ngày kiểm tra: 16/11/2026 (Asia/Saigon).

## Kết quả đã xác minh

- Luồng Streamlit thật qua AppTest: mở ứng dụng → Bản đồ thực tế → Tải dữ liệu demo → Tối ưu tuyến (Genetic Algorithm) → tạo lịch trình Leaflet. Lần chạy cấu hình mặc định cho tuyến **13.429,2 m**, 10 khách, tổng hành trình ước tính **2.501,2 s** gồm 120 s giao mỗi khách; thời lượng demo **30 s** ở 1×. Snapshot cuối giao đủ 10 khách và quay về kho.
- OSRM thật: table và route được tải/cache thành công. Một lần chạy GA 50×80 khác cho tuyến 14.008,4 m, 11 chặng, 562 đỉnh; từng chặng Route khớp khoảng cách Table (sai lệch 0 m). Kết quả GA phụ thuộc cấu hình, không mặc định bảo đảm tối ưu toàn cục.
- Frontend dùng Leaflet 1.9.4 thật trong jsdom: xe bám đoạn gấp khúc; giữ điểm đã snap; tua lùi trả đúng trạng thái/timeline; giao xong vẫn đi về kho; Play/Pause/Stop/Restart và tốc độ dùng cùng đồng hồ; attribution và popup an toàn.
- Ma trận có hướng được truyền tới mọi solver; kiểm thử bẫy đảo tuyến xác minh 2-opt tính lại toàn bộ các cạnh. Kiểm tra tọa độ sai/đảo thứ tự, null/no-road, HTTP lỗi, timeout, mạng lỗi, dữ liệu sai định dạng, cache và fallback tường minh.
- AppTest xác minh đổi nguồn/dataset/kho/tên làm mất kết quả/checkpoint; điều chỉnh thời gian và chuyển trang dùng lại kết quả/geometry. Có kiểm thử phục hồi khi Table/Route khác data_version bằng Làm mới dữ liệu đường bộ.
- Máy chủ Streamlit chạy thật: health, index.html, app.js, engine.js, leaflet-map.js, styles.css, leaflet.js và leaflet.css đều HTTP **200**. Script được kích hoạt qua giao thức WebSocket của Streamlit để đăng ký component; đây là kiểm tra máy chủ, không phải kiểm tra trực quan.
- Chưa kiểm tra trực quan bằng trình duyệt: công cụ trả inventory trình duyệt rỗng và `Browser is not available: iab`. Không suy diễn kiểm thử DOM thành kiểm chứng bố cục trên browser thật.

## Lệnh và kết quả

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 207 passed

npm run test:simulation
# 36 passed

git diff --check
# Không có lỗi whitespace

.\.venv\Scripts\python.exe -m streamlit run app.py
```

Test mới: `tests/test_routing.py`, `tests/test_road_simulation.py`, `tests/test_map_component.py`, `tests/test_geographic_app.py`; mở rộng `tests/frontend/simulation.test.mjs` và `tests/frontend/simulation_dom.test.mjs`. Các test tự động chạy routing giả lập, không gửi request tới dịch vụ công cộng. Các lần kiểm tra OSRM thật là thao tác kiểm chứng riêng, số lượng nhỏ, tuân thủ limiter.

## File thay đổi

| Nhóm | File |
|---|---|
| GPS, CSV và validation | `src/tsp/models.py`, `data_loader.py`, `validation.py`, `data/samples/hcm_geographic.csv` |
| Chi phí và routing | `src/tsp/distance.py`, `routing.py`, `services.py` |
| Thuật toán | `src/tsp/algorithms/genetic_algorithm.py`, `random_search.py`, `nearest_neighbor.py`, `exact_solver.py`, `two_opt.py` |
| UI và trạng thái | `src/tsp/ui/application.py`, `geographic_page.py`, `src/tsp/simulation/component.py` |
| Lịch trình và animation | `src/tsp/simulation/models.py`, `timeline.py`, `frontend/engine.js`, `app.js`, `leaflet-map.js`, `index.html`, `styles.css` |
| Leaflet đóng gói | `src/tsp/simulation/frontend/vendor/leaflet/` gồm JS, CSS, ảnh marker và LICENSE |
| Nhãn biểu đồ | `src/tsp/visualization/comparison_plot.py`, `convergence_plot.py`, `route_plot.py` |
| Phiên bản, đóng gói | `requirements.txt`, `package.json`, `package-lock.json`, `pyproject.toml`, `.gitignore`, `scripts/package_release.py` |
| Tài liệu | `README.md`, `docs/geographic_demo.md`, tài liệu này |
| Kiểm thử | Bốn file Python mới và hai file frontend ở trên |

`requirements-lock.txt` đã có các phiên bản Python tương ứng nên không cần thay nội dung. Cache `.cache/`, `.qa/`, môi trường ảo và node_modules bị loại khỏi bản đóng gói.

Gói `release/TSP-AI-Route-Optimizer.zip` đã được dựng lại từ các file trong Git index bằng `scripts/package_release.py --tracked-only`, có Leaflet/license, mã nguồn GPS, snapshot OSRM thật và tài liệu mới; kiểm tra ZIP không phát hiện thành viên hỏng hoặc cache cá nhân lọt vào gói. Snapshot demo là tài sản dữ liệu được đóng gói tường minh, độc lập với `.cache/`.

## Giới hạn còn lại

- OSRM và tile OSM công cộng cần mạng, không có cam kết khả dụng; không có API key hay phí tài khoản. Demo giới hạn 25 điểm, tối đa 1 request/giây, timeout 15 s, không retry tự động và không tải tile hàng loạt/offline.
- Dữ liệu đường bộ phản ánh profile ô tô của OSRM; chưa có profile xe máy, tải trọng, giờ cấm, traffic trực tiếp, geocoding, nhiều xe hoặc khung giờ giao hàng.
- Mục tiêu khoảng cách cộng khoảng cách của các đường đi nhanh nhất do OSRM trả về; không tìm đường ngắn nhất trên toàn mạng. Nếu chỉ có duration, mục tiêu là giây; khoảng cách hiển thị lấy từ Route.
- ETA dùng cùng ma trận solver và thời gian phục vụ giả định. Hình học lấy từ Route; số liệu Route riêng có trong JSON để kiểm tra chênh lệch. Dữ liệu khác phiên bản hoặc geometry không nối được sẽ bị từ chối và cần refresh/chọn lại điểm.
- Xe dừng tại điểm provider snap trên đường; marker vẫn thể hiện GPS đầu vào. Vận tốc nội suy đều dọc mỗi chặng, không mô phỏng đèn tín hiệu hay gia tốc.
- Biểu đồ Plotly ở GA Lab/Comparison chỉ nối GPS để minh họa thứ tự; bản đồ đường bộ và xe nằm ở Dashboard/Delivery Simulation/Route Playground trong chế độ thực tế.

Hướng dẫn thao tác và chính sách nguồn: [geographic_demo.md](geographic_demo.md).

## Sửa lỗi nền trống và khung Euclid bị chồng

Ảnh chụp người dùng cho thấy Leaflet có marker nhưng nền trống, còn lưới/xe SVG nằm bên dưới. Đã sửa việc gán `SVGElement.hidden` (không phản chiếu thành thuộc tính HTML) bằng `toggleAttribute("hidden", ...)`; test kiểm tra cả attribute và CSS computed display khi chuyển editor → playback → Euclid.

Kiểm tra tại máy demo: `tile.openstreetmap.org` lỗi DNS `[Errno 11001] getaddrinfo failed`, trong khi `tile.openstreetmap.de` phân giải được và một tile TP.HCM trả HTTP 200, `image/png`, 34.947 byte. Không thay đổi cấu hình DNS của máy. Bổ sung `frontend/basemap.js`: chuyển sang OSM DE một lần khi toàn vùng nhìn lỗi, có chọn nguồn/tải lại nền, trạng thái tải/thiếu/lỗi/thành công và xóa cảnh báo sau khi hồi phục. Giữ referrer và HTTP cache; không tải hàng loạt hoặc dùng API key.

Frontend hiện có **36 test đạt**, gồm hồi phục với Leaflet thật, không reset xe/tuyến hoặc gửi event chạy solver khi tải lại nền. `pytest -q tests/test_map_component.py tests/test_simulation_app.py tests/test_geographic_app.py` có **21 test đạt**. Các test mạng vẫn giả lập. Giới hạn: chưa có browser automation khả dụng để xác minh trực quan trên Edge của người dùng; kiểm tra HTTP từ host và DOM không thay thế kiểm tra render thực tế.

## Sửa lỗi không chạy demo khi Python bị chặn socket

Ảnh lỗi tiếp theo ghi `WinError 10013`: tiến trình Streamlit cũ chạy trong môi trường hạn chế socket. Đồng thời lần chuyển chế độ chỉ nạp 1 khách, không khớp cache 10 khách; form x/y và hai nút chạy thuật toán gây nhầm thao tác. Đã khởi động lại đúng máy chủ cổng 8501 với quyền mạng bình thường (không quyền quản trị, không đổi cấu hình bảo mật), nạp đủ TP.HCM khi chuyển chế độ, bỏ form Euclid trong GPS và đổi nút sidebar thành áp dụng cấu hình.

Thêm **▶ Chạy demo TP.HCM** và link `?demo=hcm`: nạp đúng dataset, nguồn OSRM, chạy GA mặc định và dựng lịch trình để nhấn Play. Ba response OSRM thật đã lưu được đóng gói trong `data/demo/hcm_osrm_snapshot.json`; không phải đường thẳng hoặc kết quả solver giả. Snapshot chỉ dùng theo exact request key và có thời gian ghi nhận/attribution, không áp dụng cho tọa độ khác.

`tests/test_demo_snapshot.py` có 7 test: cache rỗng + socket bị chặn vẫn chạy GA/road geometry/return đúng; đổi tọa độ không dùng nhầm snapshot; refresh lỗi giữ dữ liệu có nhãn; cache lỗi hồi phục; WinError 10013 có hướng xử lý; link demo và nút chạy demo không gọi mạng. Nhóm routing/demo/app gồm 49 test đạt.

Kiểm tra máy chủ Streamlit đang chạy qua WebSocket thật với `demo=hcm` nhận đúng component phát: 10 khách, 13.429,2 m, 30 s, source OSRM. Đưa chính schedule này vào JavaScript Playback: Play hoàn thành 10 khách và quay về kho; tua về đầu trả delivered_count về 0. Kiểm tra riêng hai điểm với quyền mạng bình thường cũng nhận Table + hai chặng Route OSRM thành công. Không tuyên bố đã bấm Play trên browser thật vì công cụ browser chưa kết nối.
