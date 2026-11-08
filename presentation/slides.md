# TSP AI Route Optimizer

Nội dung trình chiếu học thuật. Mỗi phần dưới đây là một slide. Dữ liệu kết quả lấy trực tiếp từ benchmark đã lưu. DOCX và PPTX chưa xuất do môi trường không cung cấp bộ phụ thuộc artifact và trình kết xuất bắt buộc.

## Slide 1  Tối ưu tuyến giao hàng bằng thuật toán di truyền

- Bài toán: một kho, nhiều khách hàng, mỗi khách hàng được thăm đúng một lần.
- Sản phẩm: ứng dụng Streamlit với sáu trang và mã nguồn thuật toán độc lập.
- Phạm vi: tọa độ Euclid, hành trình khép kín, không phải dữ liệu đường bộ.

Ghi chú thuyết trình: Giới thiệu mục tiêu giảm tổng chiều dài hành trình. Chỉ giải thích kết quả được tính thật trong benchmark kèm dự án.

## Slide 2  Mô hình toán học

- Khách hàng là một hoán vị π của tập chỉ số không chứa kho d.
- Hành trình là [d, π₁, …, πₙ, d].
- Khoảng cách d(i,j) = sqrt((xi-xj)^2 + (yi-yj)^2).
- Mục tiêu là tối thiểu hóa tổng khoảng cách các cạnh liên tiếp.

Ghi chú thuyết trình: Cùng một bộ dữ liệu bất biến được dùng cho mọi thuật toán. Tập điểm không đổi trong khi tối ưu.

## Slide 3  Biểu diễn và đánh giá lời giải

- Chromosome chỉ chứa khách hàng, không chứa kho.
- Khởi tạo toàn bộ quần thể bằng các hoán vị ngẫu nhiên hợp lệ.
- Chọn lọc tối thiểu hóa distance. Fitness hiển thị là 1 / (distance + 10^-12).
- Kiểm tra đầu ra bảo đảm đủ khách hàng, không lặp, có hai đầu kho.

Ghi chú thuyết trình: Không dùng NN để khởi tạo GA và không ghép 2-opt vào GA thuần.

## Slide 4  Các toán tử di truyền

- Tournament Selection lấy các ứng viên không hoàn lại trong mỗi giải đấu.
- Order Crossover giữ một đoạn của cha mẹ thứ nhất và thứ tự vòng của cha mẹ thứ hai.
- Inversion Mutation đảo một đoạn con.
- Crossover rate áp dụng theo cặp cha mẹ. Mutation rate áp dụng độc lập cho từng con.

Ghi chú thuyết trình: Các toán tử bảo toàn hoán vị. Mutation rate không phải xác suất theo từng gene.

## Slide 5  Elitism và điều kiện dừng

- Elitism giữ nguyên các cá thể tốt nhất và tái sử dụng khoảng cách đã tính.
- Kết thúc khi đủ số thế hệ hoặc đủ số thế hệ liên tiếp không cải thiện.
- Lịch sử lưu thế hệ 0 và từng thế hệ hoàn thành.
- Bộ đếm đánh giá GA bằng population + generations × (population - elites) khi tắt dừng sớm.

Ghi chú thuyết trình: Kết quả trả về lời giải tốt nhất từng gặp. Thời gian chạy phụ thuộc máy và tải hệ thống.

## Slide 6  Thuật toán đối chứng

- Random Search lấy hoán vị độc lập và giữ tuyến tốt nhất, hỗ trợ ngân sách đánh giá.
- Nearest Neighbor chọn khách hàng chưa thăm gần nhất và phá hòa theo thứ tự dòng.
- Held-Karp tìm tối ưu chính xác, giới hạn cứng 12 khách hàng.
- NN + 2-opt cải thiện tuyến bằng đảo đoạn, được báo cáo riêng.

Ghi chú thuyết trình: DP transitions của exact solver khác đơn vị với số lần đánh giá tuyến hoàn chỉnh của GA và Random Search.

## Slide 7  Kiến trúc và luồng dữ liệu

- UI nhận dữ liệu mẫu, CSV hoặc bảng chỉnh sửa và xác thực trước khi áp dụng.
- Dataset và config đi vào các thuật toán thuần, độc lập với Streamlit.
- Kết quả chứa route, distance, runtime, evaluations, seed, parameters và history.
- Session state lưu kết quả để đổi trang hoặc kéo slider không chạy lại thuật toán.

Ghi chú thuyết trình: Các lớp dữ liệu, tối ưu, trực quan hóa và đánh giá có trách nhiệm riêng.

## Slide 8  Giao diện và kịch bản trình diễn

- Dashboard hiển thị chỉ số và tuyến tốt nhất từ lần chạy thật.
- Route Playground hỗ trợ nhập CSV, chỉnh tọa độ, chọn kho và xuất dữ liệu.
- GA Lab phát lại lịch sử bằng thanh trượt thế hệ.
- Delivery Simulation phát tuyến đã tính bằng xe SVG, Play/Pause/Resume, Stop, Restart, tua và đổi tốc độ.
- Comparison và Experiments hiển thị bảng, biểu đồ và xuất kết quả.

Ghi chú thuyết trình: Chạy bộ 10 khách hàng, mở Delivery Simulation và chọn Play. Tạm dừng giữa một đoạn, tua tới pha giao hàng, rồi phát tiếp đến khi quay về kho. Đổi kết quả đã lưu để so sánh mà không chạy lại thuật toán. Giữ nguyên seed để chứng minh tái lập route và history.

## Slide 9  Thiết kế thực nghiệm

- Bốn bộ dữ liệu cố định với 5, 10, 20 và 30 khách hàng cộng một kho.
- GA và Random Search chạy tối thiểu 10 seed cho mỗi bộ.
- Random Search dùng cùng số lần đánh giá tuyến thực tế với lần GA tương ứng.
- Lưu toàn bộ seed, config, tọa độ, tuyến, thời gian và lịch sử.
- Báo cáo mean, best, worst, sample standard deviation và gap khi có exact optimum.

Ghi chú thuyết trình: Ngân sách đánh giá bằng nhau không có nghĩa runtime bằng nhau. Bốn bộ tổng hợp không đủ để khái quát cho mọi bài toán TSP.

## Slide 10  Kết quả đo được

| Khách hàng | GA mean | NN | Random mean | GA cải thiện so với NN |
|---:|---:|---:|---:|---:|
| 5 | 255.46 | 255.50 | 255.46 | 0.01% |
| 10 | 368.83 | 422.28 | 404.10 | 12.66% |
| 20 | 381.02 | 380.68 | 659.66 | -0.09% |
| 30 | 493.38 | 609.25 | 1131.35 | 19.02% |

Đơn vị khoảng cách Euclid. Mean lấy từ số lần chạy ghi trong bảng CSV.

Ghi chú thuyết trình: Tỷ lệ cải thiện dương nghĩa là ngắn hơn NN, âm nghĩa là dài hơn. Không suy ra GA luôn tốt hơn từ một thiết lập.

## Slide 11  Phân tích kết quả thực tế

# Measured benchmark findings

These observations are generated from the saved runs. Positive improvement means a shorter route than Nearest Neighbor.

## 5 customers + one depot

GA mean distance: 255.463365; Random Search mean: 255.463365; Nearest Neighbor: 255.497576.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 0.013%. Mean GA time: 0.554662 s; mean Random Search time: 0.049896 s.
Exact optimum: 255.463365; GA mean optimality gap: 0.000%.

## 10 customers + one depot

GA mean distance: 368.833300; Random Search mean: 404.099751; Nearest Neighbor: 422.284877.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 12.658%. Mean GA time: 0.694632 s; mean Random Search time: 0.063480 s.
Exact optimum: 368.392706; GA mean optimality gap: 0.120%.

## 20 customers + one depot

GA mean distance: 381.024630; Random Search mean: 659.655220; Nearest Neighbor: 380.682773.
GA was worse than Nearest Neighbor in 3/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: -0.090%. Mean GA time: 1.011534 s; mean Random Search time: 0.088152 s.
Exact optimum was not computed because the dataset exceeds the 12-customer limit.

The measured losses are consistent with finite-budget stochastic search. The pure GA starts from random permutations; tournament selection and finite population diversity can converge to a local region. Nearest Neighbor exploits local geometry immediately. This experiment does not establish a single causal mechanism or universal algorithm ranking.

## 30 customers + one depot

GA mean distance: 493.378999; Random Search mean: 1131.349229; Nearest Neighbor: 609.247341.
GA was worse than Nearest Neighbor in 0/10 runs and worse than its paired Random Search run in 0/10 runs.
GA mean improvement over Nearest Neighbor: 19.018%. Mean GA time: 0.863258 s; mean Random Search time: 0.074160 s.
Exact optimum was not computed because the dataset exceeds the 12-customer limit.

## Interpretation limits

There is one generated geometry per problem size. Repetitions measure algorithm RNG variability on that geometry, not variability across all delivery networks. Matching complete-tour evaluations does not match wall-clock time: crossover, selection, and Python overhead differ. Timings are machine-specific. Distances are Euclidean coordinate units and exclude roads, capacity, time windows, traffic, and multiple vehicles.


Ghi chú thuyết trình: Đọc cùng raw benchmark để kiểm tra biến thiên giữa seed. NN là greedy nhanh và có thể tốt hơn GA khi ngân sách thấp hoặc GA hội tụ sớm.

## Slide 12  Giới hạn và hướng phát triển

- Chỉ xét một xe, một kho và khoảng cách Euclid đối xứng.
- Chưa có tải trọng, khung giờ, giao thông hay API bản đồ.
- GA là heuristic và không bảo đảm tối ưu.
- Có thể mở rộng sang nhiều bộ dữ liệu, điều chỉnh toán tử và bài toán VRP.

Ghi chú thuyết trình: Kết luận dựa trên số liệu kèm dự án. Bắt đầu phần hỏi đáp bằng việc mở mã nguồn, kiểm thử hình vuông và các tệp kết quả.

## Tài liệu trình chiếu và nguồn

- docs/algorithm_design.md giải thích toán tử và quy ước xác suất.
- docs/experimental_protocol.md ghi cách tái lập.
- results/raw/benchmark.json và results/final/benchmark_summary.csv là nguồn các số đo.
- report/TSP_AI_Route_Optimizer_Report.pdf chứa báo cáo đầy đủ.
