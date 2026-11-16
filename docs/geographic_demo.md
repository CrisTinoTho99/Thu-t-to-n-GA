# Demo giao hàng trên bản đồ thực tế

## Chạy ứng dụng

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Mở **http://localhost:8501/?demo=hcm** để nạp đủ 10 khách, chạy GA mặc định và chuẩn bị sẵn tuyến; sau đó nhấn **Play**. Có thể khởi chạy bằng `.\run_demo.ps1` từ PowerShell bình thường. Không cần chạy với quyền quản trị.

Python >=3.11. Các dependency Python trực tiếp đã khóa phiên bản; `requirements-lock.txt` giữ toàn bộ môi trường. Leaflet **1.9.4** được lưu cục bộ cùng giấy phép, nên không cần npm/CDN lúc chạy ứng dụng. Nền OpenStreetMap và routing điểm mới cần mạng Internet; không cần API key hoặc tài khoản thanh toán. Demo GA mặc định có response OSRM thật đã đóng gói, nên vẫn chạy được khi Python bị chặn kết nối tới OSRM.

## Demo từng bước

1. Mở ứng dụng, chọn **Bản đồ thực tế** trong sidebar. Lần chuyển đầu tiên nạp đầy đủ bộ TP.HCM.
2. Nhấn **▶ Chạy demo TP.HCM** để nạp một kho và 10 địa điểm, chọn nguồn OSRM và chạy GA mặc định ngay; sau đó nhấn Play. Có thể tiếp tục dùng luồng từng bước bên dưới với **Tải dữ liệu demo**. Đây là các điểm minh họa ở khu vực công cộng, không phải địa chỉ đơn giao hàng cá nhân.
3. Giữ nguồn **OSRM · đường bộ**. Trong **Thuật toán tối ưu bản đồ**, giữ **Genetic Algorithm** (có thể chọn thêm NN, Random Search, NN + 2-opt, Exact Solver). Thiết lập GA trong sidebar được áp dụng bằng nút **Áp dụng cấu hình GA**; nút **Tối ưu tuyến** dùng cấu hình đã áp dụng gần nhất. Sidebar không còn bộ sinh x/y hoặc một nút chạy solver thứ hai trong chế độ GPS.
4. Nhấn **Tối ưu tuyến**. Ứng dụng lấy một ma trận có hướng cho toàn bộ địa điểm, chạy các solver trên cùng ma trận và lấy hình học tuyến theo thứ tự solver trả về. Chờ trạng thái tải hoàn tất.
5. Tuyến xanh trên Leaflet là các chặng đường OSRM trả về. Kho có biểu tượng riêng; khách có số thứ tự. Nhấp marker xem tên, latitude/longitude, thứ tự và trạng thái.
6. Nhấn **Play**. Xe nội suy dọc polyline, dừng giao từng khách rồi quay về kho. Pause/Stop giữ vị trí, Resume tiếp tục, Restart về đầu. Tốc độ 0.5×–4× và thanh tua xử lý trong JavaScript. Tua lùi tính lại trạng thái giao hàng và timeline theo thời gian đã chọn.
7. Dùng **Vừa khung bản đồ** để thấy toàn tuyến. Thanh **Nền bản đồ** cho phép đổi nguồn tile hoặc **Tải lại nền** mà không chạy lại solver/routing. Khi toàn bộ tile của OpenStreetMap Standard lỗi, ứng dụng thử OSM DE một lần; nếu cả hai lỗi, thông báo yêu cầu kiểm tra kết nối/DNS. Mở cài đặt hành trình để đổi số giây giao hàng/khách và thời lượng demo; các thuật toán dùng chung hệ số nén thời gian theo tuyến GA tham chiếu.
8. Mở phần thứ tự giao để tải JSON chứa dataset, ma trận, kết quả, hình học và lịch trình.

Bản đồ chiếm toàn bộ chiều ngang nội dung, cao 560–840 px trên máy tính và 460 px trên màn hình nhỏ. Play/Pause và thanh tua nằm ngay bên dưới; thông tin xe được bố trí thành bảng gọn phía dưới. Mở **Dữ liệu và cấu hình tối ưu** để chọn thuật toán hoặc sửa điểm, **Chỉ số hành trình và nguồn dữ liệu** để xem các chỉ số Python và thông tin nguồn.

## Tương tác dữ liệu

Trước khi tối ưu, nhấp nền bản đồ để thêm khách. Sau khi có kết quả, nhấn **Chỉnh sửa trên bản đồ** để quay lại chế độ thêm điểm. Mở **Sửa điểm giao hàng, tọa độ và kho** để đổi tên/tọa độ, xóa khách hoặc chọn một điểm khác làm kho. Đổi kho rồi lưu trước khi xóa kho cũ. Giữ tối thiểu một kho và một khách. Demo dịch vụ công cộng giới hạn 25 địa điểm gồm kho.

CSV GPS: `id,name,latitude,longitude,is_depot`. Latitude thuộc [-90,90], longitude thuộc [-180,180]; phải có đúng một kho. Các điểm trong một dataset phải cùng hệ tọa độ. CSV cũ `id,name,x,y,is_depot` vẫn đọc và chạy trong **Mô phỏng Euclid**; tuyệt đối không tự hiểu x/y là GPS. Dữ liệu GPS có x=longitude/y=latitude là bí danh nội bộ, không phải tọa độ Euclid để tính chi phí. Leaflet nhận `[latitude,longitude]`; OSRM và GeoJSON nhận `[longitude,latitude]`.

Mọi thay đổi điểm, kho, chế độ hoặc nguồn ma trận sẽ xóa kết quả, lịch trình và checkpoint trước đó. Cache mạng độc lập vẫn có thể dùng lại khi tọa độ/cấu hình khớp.

## Đọc chỉ số đúng

- **Mục tiêu solver:** ưu tiên tổng khoảng cách (m) của các đường đi nhanh nhất mà OSRM Table trả về. Nếu provider không trả ma trận khoảng cách, mục tiêu là tổng thời gian (s) và được ghi rõ. Đây không phải cam kết tìm đường ngắn nhất trên toàn bộ mạng đường.
- **Ma trận bất đối xứng:** không lấy trung bình hai chiều. 2-opt đánh giá lại đầy đủ mỗi tuyến đảo, tính cả các cạnh bên trong bị đổi hướng.
- **Thời gian thuật toán:** đo riêng CPU/wall time của solver; không phải ETA, không bao gồm tải mạng.
- **Di chuyển/giao hàng/hành trình ước tính:** tính từ thời gian đường bộ của cùng ma trận và số giây phục vụ/khách. Không dùng dữ liệu giao thông thời gian thực.
- **Thời lượng demo:** thời gian hành trình được nén để dễ trình diễn (mặc định GA khoảng 30 giây ở 1×). Playback speed tiếp tục nhân tốc độ phát, không sửa ETA.
- Ma trận quyết định mục tiêu, quãng đường và lịch trình; hình học quyết định vị trí xe. Có thể có chênh lệch nhỏ giữa thông số Route và Table do làm tròn hoặc cập nhật provider. Các chặng phải nối liên tục, không thay bằng đường thẳng ngầm.

## Cache, lỗi mạng và dịch vụ công cộng

Cache JSON nằm trong `.cache/routing/`, tối đa 128 mục. Khóa chứa tọa độ theo thứ tự, provider, profile và cấu hình truy vấn; tuyến thêm thứ tự đi. Có thể xóa thư mục cache khi ứng dụng tắt. Mặc định timeout 15 giây, giới hạn chung tối đa 1 request/giây, không tự retry. Chỉ lấy tuyến mới khi dataset/thứ tự thay đổi; Play/Pause/tua không gọi solver hoặc OSRM.

`data/demo/hcm_osrm_snapshot.json` là dữ liệu demo cố định gồm response Table và các Route OSRM thật đã lấy trước, có thời điểm ghi nhận và attribution. Khi cache không có, chỉ dùng response có khóa khớp hoàn toàn tọa độ, thứ tự, provider/profile và cấu hình API. GA vẫn tự tính thứ tự trên ma trận này; hình học chỉ được dùng nếu khớp đúng thứ tự vừa tính. Chỉnh điểm/thứ tự ngoài snapshot cần mạng; không gán đường cũ cho điểm mới. Công cụ `scripts/build_road_demo_snapshot.py` đóng gói từ response cache đã kiểm chứng, không tải tile hoặc gửi request mạng.

Nếu gặp **WinError 10013**, Python bị chặn quyền mở socket (có thể do môi trường chạy hạn chế). Dùng nút **Chạy demo TP.HCM** hoặc link `?demo=hcm` để phát bằng dữ liệu OSRM đã lưu. Để routing điểm mới, chạy lệnh Streamlit hoặc `run_demo.ps1` từ PowerShell thông thường. Không cần tắt firewall, đổi DNS hoặc chạy quyền quản trị. Môi trường vẫn chặn mạng sẽ báo lỗi rõ ràng thay vì giả lập thành đường bộ.

Khi OSRM lỗi hoặc không có đường, thông báo giải thích điểm/chặng không dùng được. Một response hợp lệ đã cache được ưu tiên; lỗi không ghi đè cache. Nút thử tải lại chỉ gửi yêu cầu khi người dùng nhấn. **Làm mới dữ liệu đường bộ** yêu cầu lại cả ma trận và hình học rồi tối ưu; dùng khi cache khác phiên bản dữ liệu provider. Cache cũ còn hợp lệ có thể được dùng khi refresh lỗi và sẽ có cảnh báo. Có thể chủ động chuyển sang **Đường thẳng gần đúng** rồi tối ưu lại; dữ liệu này dùng khoảng cách cầu lớn và vận tốc giả định, luôn có cảnh báo và không được gọi là tuyến đường bộ. Không trộn kết quả hai nguồn khi so sánh.

Tile được tải theo vùng đang xem bằng cơ chế cache HTTP của trình duyệt, không có tải hàng loạt/prefetch/offline. Attribution OpenStreetMap luôn hiển thị trên bản đồ, nguồn tuyến OSRM được ghi rõ. Máy chủ công cộng có thể giới hạn, thiếu dữ liệu hoặc ngừng phục vụ; dùng OSRM tự vận hành/provider phù hợp cho tải lớn và triển khai sản xuất.

Nguồn nền mặc định: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Nguồn dự phòng không cần API key: `https://tile.openstreetmap.de/{z}/{x}/{y}.png`, có attribution riêng cho OSM DE và giấy phép hình ảnh. Chỉ chuyển dự phòng khi cả vùng nhìn hiện tại không tải được, không retry tự động liên tục; thao tác tải lại thủ công có khoảng cách tối thiểu 2 giây. Nguồn nền độc lập với **Nguồn chi phí**: đổi nền không đổi mục tiêu tối ưu hoặc tuyến. Xem [OSM DE FAQ](https://www.openstreetmap.de/faq/) và [nguồn tile OSM DE](https://tile.openstreetmap.de/).

Nguồn kỹ thuật/chính sách: [Leaflet 1.9.4](https://leafletjs.com/reference-1.9.4.html), [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [OSRM usage policy](https://github.com/Project-OSRM/osrm-backend/wiki/Api-usage-policy), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/), [OSM copyright](https://www.openstreetmap.org/copyright).

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm ci --ignore-scripts
npm run test:simulation
```

Các kiểm thử OSRM dùng response giả lập, không phụ thuộc máy chủ công cộng. Bao gồm chi phí hai chiều khác nhau, GPS sai, response không có đường/lỗi mạng, cache, hình học gấp khúc, tua ngược trạng thái và quay về kho. Không tải tile trong test tự động.
