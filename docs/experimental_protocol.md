# Quy trình thực nghiệm

## Câu hỏi nghiên cứu

GA thuần tìm tuyến ngắn đến mức nào so với Random Search khi có cùng số lần đánh giá hàm mục tiêu? Chất lượng đó so với NN và NN + 2-opt ra sao? Với dữ liệu nhỏ, khoảng cách đến nghiệm Held–Karp là bao nhiêu?

Không giả định GA luôn thắng. Kết quả phải bao gồm trường hợp GA kém hơn baseline nếu xuất hiện.

## Dữ liệu và seed

Sử dụng bốn bài toán có 5, 10, 20, 30 **khách hàng**, mỗi bài toán thêm đúng một kho. Mỗi kích thước có một bộ tọa độ cố định trong một chiến dịch benchmark. Tất cả thuật toán và mọi lần lặp của cùng kích thước dùng cùng dataset; seed lấy mẫu lời giải không được thay tọa độ.

Seed của dataset là `1000 + số_khách_hàng`. Với mỗi lần lặp đánh số từ 0, hai seed thuật toán được sinh độc lập bởi `np.random.SeedSequence([base_seed, số_khách_hàng, lần_lặp]).generate_state(2)`. Metadata lưu seed tạo dataset, fingerprint, toàn bộ tọa độ, seed từng lần chạy và cấu hình. Không lựa chọn lại seed sau khi thấy kết quả để làm đẹp báo cáo.

## Thiết kế so sánh

- Chạy GA và Random Search ít nhất 10 lần độc lập mỗi kích thước.
- Mỗi lần Random Search nhận số đánh giá bằng số đánh giá thực tế của lần GA tương ứng, kể cả khi GA dừng sớm.
- NN và NN + 2-opt là xác định; chạy một lần cho mỗi dataset, không nhân bản thành 10 mẫu giả độc lập.
- Held–Karp chỉ chạy ở 5 và 10 khách hàng. Các kích thước lớn hơn không được gán một nghiệm heuristic làm optimum.
- Giữ cùng hệ tọa độ, kho, hàm khoảng cách và quy tắc đóng tuyến.
- Thời gian đo bằng đồng hồ hiệu năng trong từng bộ giải. Giữ các công việc khác trên máy ở mức thấp khi cần so sánh runtime.

Cân bằng số đánh giá hàm mục tiêu giúp kiểm tra hiệu quả tìm kiếm trên cùng ngân sách nhưng không loại bỏ chi phí selection, crossover, quản lý quần thể hay khác biệt vector hóa. Vì thế phải báo cáo cả evaluation và runtime, không suy ra thuật toán nhanh hơn chỉ từ evaluation bằng nhau.

## Chỉ số

| Chỉ số | Định nghĩa |
|---|---|
| Best / mean / worst distance | Min / trung bình / max khoảng cách trên các lần lặp |
| Standard deviation | Độ lệch chuẩn mẫu `ddof=1` giữa các lần ngẫu nhiên; ghi 0 theo quy ước cho phương pháp xác định đo một lần |
| Mean runtime | Trung bình giây chạy bộ giải |
| Evaluations | Số lần tính tổng khoảng cách cho ứng viên; ghi rõ chi phí của solver chính xác không trực tiếp tương đương heuristic |
| Improvement over NN | `100 × (NN − distance) / NN`, có thể âm |
| Optimality gap | `100 × (distance − exact) / exact`, chỉ khi có exact |

Đối với mẫu số 0: hai khoảng cách 0 tương ứng 0% chênh lệch; không báo một số phần trăm hữu hạn khi baseline 0 nhưng nghiệm đang xét dương. Giá trị không xác định phải hiển thị rõ, không thay bằng tỷ lệ đẹp giả tạo.

## Chạy và lưu

```powershell
.\.venv\Scripts\python.exe scripts/run_experiments.py --help
.\.venv\Scripts\python.exe scripts/run_experiments.py
.\.venv\Scripts\python.exe scripts/run_experiments.py --repeats 10 --customers 5 10 20 30 --population 100 --generations 200 --patience 0 --seed 42 --write-samples
```

`results/raw/benchmark_runs.csv` giữ một hàng cho mỗi lần chạy thật. `results/raw/benchmark.json` giữ dataset, cấu hình, route và lịch sử chi tiết. `results/final/benchmark_summary.csv` tổng hợp theo kích thước và thuật toán; `results/final/metadata.json` ghi môi trường và thiết lập; `results/final/findings.md` chứa nhận xét được tạo từ số đo. Dataset nằm trong `results/datasets/`; `--write-samples` xuất thêm dữ liệu mẫu. Hình PNG và HTML tương tác được xuất dưới `results/figures/`; HTML dùng chung `plotly.min.js`, cần giữ nguyên thư mục khi sao chép để xem ngoại tuyến. Có thể đổi thư mục bằng `--output`. Các tệp kết quả được sinh bởi chương trình, không được điền số liệu bằng tay.

Kiểm tra sau chạy: mọi route hợp lệ; tổng khoảng cách tính lại khớp giá trị đã lưu; số lần GA/Random Search đủ yêu cầu; seed không bị thiếu; ngân sách được ghép đúng; exact gap chỉ xuất hiện ở kích thước được giải chính xác. Chạy lại với cùng môi trường để đối chiếu route, distance và history; runtime có thể khác.

## Phân tích và đe dọa hiệu lực

Báo cáo giá trị tuyệt đối cùng độ phân tán, tránh chỉ chọn lần tốt nhất. Đếm số lần GA thua NN hoặc Random Search để nhận diện tính không ổn định. Khi có exact, kiểm tra khoảng cách heuristic không thấp hơn optimum quá sai số số thực.

Mỗi kích thước mới có một instance nên không đại diện cho mọi hình học hoặc phân bố tọa độ. Mười seed đo biến thiên của phương pháp ngẫu nhiên trên instance đó, không phải mười bộ dữ liệu độc lập. Cấu hình GA cố định không phải cấu hình tối ưu cho mọi kích thước. Runtime đơn lẻ của NN/2-opt nhạy với overhead đo; không thực hiện kiểm định ý nghĩa thống kê khi chưa có thiết kế lấy mẫu phù hợp.
