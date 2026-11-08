# TSP AI Route Optimizer

Ứng dụng Python/Streamlit tối ưu tuyến giao hàng bằng thuật toán di truyền (Genetic Algorithm, GA), so sánh với Random Search, Nearest Neighbor, Held–Karp và Nearest Neighbor + 2-opt. Giao diện gồm Dashboard, Delivery Simulation, Route Playground, Genetic Algorithm Lab, Algorithm Comparison, Experiments & Analytics và About & Documentation.

Khoảng cách trong dự án là **khoảng cách Euclid trên mặt phẳng**, có đơn vị tọa độ. Ứng dụng không truy vấn bản đồ đường bộ, giao thông hoặc thời gian giao hàng thực tế.

## Cài đặt và chạy

Yêu cầu Python 3.11 trở lên. Mở terminal tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Trên macOS/Linux, thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python`. Truy cập địa chỉ mà Streamlit in ra, mặc định `http://localhost:8501`.

Không cần API key, tài khoản dịch vụ hay kết nối bản đồ. Sau khi cài dependencies, tối ưu hóa và nhập/xuất dữ liệu chạy cục bộ.

`requirements-lock.txt` ghi phiên bản đã chạy trên Windows/Python 3.14; dùng `requirements.txt` cho cài đặt đa nền tảng. Nếu cần tạo lại PDF, cài thêm `python -m pip install -r requirements-report.txt`; nhóm thư viện này không bắt buộc để chạy ứng dụng.

## Sử dụng nhanh

1. Chọn bộ dữ liệu hoặc tạo tọa độ ngẫu nhiên. Số khách hàng không bao gồm một kho hàng.
2. Trong Route Playground, tải CSV hoặc chỉnh bảng tọa độ. Áp dụng dữ liệu sau khi sửa; dữ liệu phải có đúng một kho.
3. Cấu hình seed và GA, sau đó nhấn nút chạy tối ưu hóa. Các thuật toán sử dụng cùng bộ tọa độ.
4. Xem tuyến khép kín, khoảng cách, thời gian và số lần đánh giá. GA Lab cho phép xem lại từng thế hệ đã lưu.
5. Tải dataset, kết quả và biểu đồ. Thay đổi trang hoặc thanh trượt xem lịch sử không khởi chạy lại bộ giải.

Khi mở phiên lần đầu, ứng dụng thực hiện một lần tính thật trên dataset mặc định để có thể khám phá kết quả ngay. Sau đó các thuật toán chỉ chạy qua hành động chạy rõ ràng. Benchmark mới từ giao diện lưu trong `results/interactive/`, tách khỏi release benchmark đã có trong `results/`.

Chi tiết: [hướng dẫn sử dụng](docs/user_guide.md).

## Dữ liệu CSV

```csv
id,name,x,y,is_depot
D,Kho trung tâm,0,0,true
A,Khách hàng A,1,0,false
B,Khách hàng B,1,1,false
C,Khách hàng C,0,1,false
```

Các cột bắt buộc là `id,name,x,y,is_depot`. ID phải duy nhất, tên không rỗng, tọa độ là số hữu hạn, có ít nhất một khách hàng và đúng một kho. Kho không bắt buộc nằm ở hàng đầu tiên. Các vị trí trùng tọa độ vẫn là các khách hàng riêng nếu ID khác nhau.

## Thuật toán và ý nghĩa chỉ số

| Thuật toán | Cách hoạt động | Bảo đảm |
|---|---|---|
| Genetic Algorithm | Hoán vị khách hàng; tournament selection, OX, inversion, elitism | Tuyến hợp lệ; không bảo đảm tối ưu toàn cục |
| Random Search | Lấy mẫu hoán vị ngẫu nhiên theo ngân sách | Giữ tuyến tốt nhất đã đánh giá |
| Nearest Neighbor | Chọn khách hàng chưa thăm gần nhất từ vị trí hiện tại | Heuristic xác định, phụ thuộc vị trí kho và quy tắc phá hòa |
| Held–Karp | Quy hoạch động theo tập khách hàng đã thăm | Tối ưu toàn cục cho bài toán được cung cấp; giới hạn 12 khách hàng |
| Nearest Neighbor + 2-opt | Cải thiện tuyến NN bằng đảo đoạn | Không làm xấu tuyến xuất phát; có thể dừng ở tối ưu cục bộ |

GA thuần không được âm thầm thêm 2-opt. Crossover rate áp dụng cho mỗi cặp bố mẹ; mutation rate áp dụng cho mỗi con. Lịch sử bao gồm quần thể khởi tạo tại thế hệ 0.

`Improvement over NN (%) = 100 × (distance_NN − distance) / distance_NN`. Giá trị âm nghĩa là kém hơn NN. `Gap to optimal (%) = 100 × (distance − optimum) / optimum` chỉ có khi exact solver thực sự được chạy. Trường hợp mẫu số bằng 0 được xử lý riêng trong module metrics.

`Evaluations` đếm số lần tính giá trị hàm mục tiêu, không phải số thế hệ. Trong GA, cá thể elite giữ lại giá trị đã tính; nếu không dừng sớm, ngân sách bằng `population_size + generations × (population_size − elitism_count)`.

## Kiểm thử và thực nghiệm

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/run_experiments.py --help
.\.venv\Scripts\python.exe scripts/run_experiments.py
.\.venv\Scripts\python.exe scripts/run_experiments.py --repeats 10 --write-samples
```

Bộ kiểm thử bao phủ khoảng cách, tính hợp lệ của tuyến, kho ở hàng bất kỳ, OX/inversion, elitism, tái lập seed, NN, ngân sách Random Search, CSV, tham số sai và JSON. Hình vuông cạnh 1 có nghiệm chính xác bằng 4. Kiểm thử GA không yêu cầu thuật toán ngẫu nhiên luôn đạt nghiệm tối ưu.

Bản dựng có mô phỏng đã chạy **117 kiểm thử Python** và **24 kiểm thử JavaScript** đạt. AppTest kiểm tra các trang và việc chuyển kết quả mô phỏng không chạy lại solver. Kiểm thử DOM chạy các handler thật cho nút bấm, thanh tua, SVG, sự kiện và giao tiếp component; kiểm tra máy chủ thật xác nhận cả bốn tài nguyên component trả HTTP 200. Chưa kiểm tra trực quan trong trình duyệt vì môi trường công cụ không có browser khả dụng. Xem [xác minh mô phỏng](docs/simulation_verification.md) và [xác minh bản gốc](docs/verification.md).

## Demo xe giao hàng

Từ Dashboard, chọn **Open delivery simulation**, hoặc mở trang **Delivery Simulation** ở sidebar. Chọn một kết quả đã tính rồi nhấn **Play**. Xe SVG chạy đúng thứ tự tuyến, dừng giao hàng và quay về kho. Các kết quả GA, NN, Random Search, 2-opt hoặc exact đã có đều có thể phát lại.

Play đổi thành Resume khi tạm dừng. Pause và Stop giữ vị trí; Restart về kho ở thời điểm 0. Tua sẽ dừng phát và cập nhật ngược/xuôi mọi thống kê, trạng thái địa điểm và timeline. Hệ số 0.5×–4× thay tốc độ phát cả di chuyển và giao hàng; không sửa tuyến hoặc chạy lại GA.

Trong Journey settings có vận tốc cơ sở (đơn vị tọa độ/giây mô phỏng) và thời gian giao mỗi khách. Vận tốc tham chiếu ban đầu được dùng chung giữa các thuật toán. Nút fit ~30 giây hiệu chỉnh vận tốc chung theo tuyến đang chọn; không thể fit nếu riêng thời gian dừng đã đạt 30 giây hoặc tổng quãng đường bằng 0. Chọn địa điểm trên bản đồ hoặc manifest để xem chi tiết, kể cả khi các điểm trùng tọa độ.

Frontend chạy trực tiếp từ các tệp JavaScript/SVG cục bộ, không cần npm để chạy ứng dụng. Node.js chỉ cần cho kiểm thử phát triển:

```powershell
npm ci
npm run test:simulation
```

Kiểm thử fake clock không cần thư viện DOM có thể chạy riêng bằng `node --test tests/frontend/simulation.test.mjs`. Chi tiết: [thiết kế mô phỏng](docs/simulation_design.md).

Benchmark mặc định có 5, 10, 20, 30 khách hàng, tối thiểu 10 lần GA và Random Search trên mỗi bộ dữ liệu. Tọa độ được giữ nguyên giữa các thuật toán và các lần lặp của một kích thước. Seed, cấu hình, tuyến, lịch sử, khoảng cách và runtime được lưu để kiểm tra lại. Random Search nhận cùng số đánh giá thực tế của lần chạy GA tương ứng. So sánh này cân bằng ngân sách hàm mục tiêu; chi phí selection/crossover và triển khai NumPy khác nhau nên không đồng nghĩa cân bằng thời gian CPU.

Kết quả được tạo trong `results/`: `raw/benchmark.json`, `raw/benchmark_runs.csv`, `final/benchmark_summary.csv`, `final/metadata.json`, `final/findings.md`, datasets và hình PNG/HTML. Xem [quy trình thực nghiệm](docs/experimental_protocol.md) và [nội dung báo cáo](docs/report_content.md) để đọc thiết lập cùng kết quả thực tế.

## Cấu trúc

```text
app.py                       Điểm khởi chạy Streamlit
src/tsp/models.py            Mô hình dữ liệu, cấu hình và kết quả
src/tsp/data_loader.py       Nhập CSV, chuyển bảng, sinh dữ liệu
src/tsp/validation.py        Kiểm tra dữ liệu và tuyến
src/tsp/distance.py          Ma trận Euclid, tổng độ dài tuyến
src/tsp/algorithms/          GA, Random Search, NN, exact, 2-opt
src/tsp/visualization/       Biểu đồ Plotly
src/tsp/evaluation/          Metrics và benchmark
src/tsp/simulation/          Lịch trình, nội suy và frontend xe giao hàng
data/samples/               CSV mẫu
scripts/run_experiments.py   Chạy benchmark từ terminal
tests/                      Kiểm thử tự động
docs/                       Hướng dẫn và thiết kế
report/                     Báo cáo xuất bản
presentation/               Nội dung/slide thuyết trình
```

Xem [kiến trúc](docs/architecture.md) và [thiết kế thuật toán](docs/algorithm_design.md).

## Bản bàn giao

- [Gói dự án đầy đủ](release/TSP-AI-Route-Optimizer.zip), gồm mã nguồn, dữ liệu mẫu, kiểm thử, kết quả, báo cáo và tài liệu; không gồm `.venv`.
- [Báo cáo PDF](report/TSP_AI_Route_Optimizer_Report.pdf) và [nội dung thuyết trình 12 slide](presentation/slides.md).
- [Trạng thái kiểm chứng](docs/verification.md) và [số liệu tổng hợp](results/final/benchmark_summary.csv).

Đóng gói lại bằng `python scripts/package_release.py`. Tạo lại PDF theo [hướng dẫn báo cáo](report/README.md).

Tài liệu có nội dung Markdown và báo cáo PDF; thuyết trình có nội dung slide Markdown. Chưa xuất `.docx` và `.pptx` vì môi trường artifact hiện tại không hỗ trợ quy trình xuất các định dạng này. GA Lab xem lại thế hệ bằng thanh trượt; Delivery Simulation có animation xe trên tuyến đã tính, độc lập với quá trình tối ưu.

## Tái lập và giới hạn

Cùng dataset, seed, cấu hình và phiên bản thư viện cho cùng tuyến/lịch sử của các thuật toán ngẫu nhiên. Runtime thay đổi theo máy và tải hệ thống. Số khách hàng tối đa bị giới hạn để tránh cấp phát hoặc tính toán ngoài ý muốn; exact solver có giới hạn riêng thấp hơn. GA và 2-opt là heuristic, có thể kém hơn NN trên một số dữ liệu. Thí nghiệm trên một bộ tọa độ mỗi kích thước chưa đủ để kết luận tổng quát cho mọi phân bố dữ liệu.

Phiên làm việc của giao diện được lưu trong Streamlit session; tải JSON/CSV nếu cần giữ kết quả sau khi đóng ứng dụng. Bộ dữ liệu có thay đổi cần được tối ưu lại trước khi so sánh với kết quả cũ.

## Nguồn tham khảo

- Held, M. & Karp, R. M. (1962). *A Dynamic Programming Approach to Sequencing Problems*. Journal of the Society for Industrial and Applied Mathematics, 10(1), 196–210. [DOI và trang nhà xuất bản](https://epubs.siam.org/doi/abs/10.1137/0110015).
- Holland, J. H. (1992). *Adaptation in Natural and Artificial Systems*. MIT Press. [Trang nhà xuất bản](https://doi.org/10.7551/mitpress/1090.001.0001).
- Streamlit. [AppTest API](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
