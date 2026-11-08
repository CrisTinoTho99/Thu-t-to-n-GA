# Thiết kế thuật toán

## Mô hình TSP

Gọi `0` là ký hiệu toán học của kho, không nhất thiết là hàng đầu của dataset; có `n` khách hàng. Một chromosome `π` là hoán vị của toàn bộ khách hàng. Tuyến là `(0, π₁, …, πₙ, 0)`.

Khoảng cách `d(i,j) = sqrt((xᵢ−xⱼ)² + (yᵢ−yⱼ)²)`; mục tiêu là tối thiểu hóa `L(π) = d(0,π₁) + Σ d(πₖ,πₖ₊₁) + d(πₙ,0)`. Không có ràng buộc thời gian, sức chứa hay nhiều phương tiện. Các khách hàng trùng tọa độ vẫn có chỉ số khác nhau và phải được thăm.

## Genetic Algorithm

1. Khởi tạo `P` hoán vị ngẫu nhiên hợp lệ bằng bộ sinh `numpy.random.default_rng(seed)` cục bộ. GA thuần không chèn nghiệm NN và không âm thầm dùng 2-opt.
2. Đánh giá tổng khoảng cách; giá trị nhỏ hơn là tốt hơn. Fitness hiển thị là `1 / (distance + epsilon)`, giá trị lớn hơn là tốt hơn.
3. Chọn bố mẹ bằng tournament: lấy một nhóm cá thể rồi chọn cá thể có khoảng cách nhỏ nhất.
4. Với xác suất crossover rate cho **mỗi cặp**, thực hiện Order Crossover (OX). Nếu không lai, sao chép bố mẹ.
5. Với xác suất mutation rate cho **mỗi cá thể con**, đảo thứ tự một đoạn liên tiếp (inversion mutation).
6. Giữ nguyên `E` cá thể tốt nhất (elitism); điền con mới cho đủ kích thước quần thể.
7. Lưu thống kê và tuyến tốt nhất của mỗi thế hệ. Dừng khi hết số thế hệ hoặc đạt patience không cải thiện, nếu patience lớn hơn 0.

### OX và tính hợp lệ

Chọn hai điểm cắt trên chromosome. Sao chép đoạn từ bố mẹ thứ nhất vào đúng vị trí. Đi qua bố mẹ thứ hai theo thứ tự vòng quanh và điền các gene chưa có vào các ô trống. Vì chỉ thêm gene chưa xuất hiện, chromosome con chứa đúng tập gene ban đầu. Trường hợp rất ít khách hàng được xử lý riêng để không yêu cầu lấy hai điểm cắt từ tập có một phần tử.

Ví dụ chromosome chỉ chứa khách hàng: `[A, B, C, D, E]`. Kho không được đưa vào crossover hoặc mutation; nó được thêm ở hai đầu khi đánh giá/xuất tuyến. Inversion chỉ đổi thứ tự nên không làm mất hay nhân đôi khách hàng.

### Lịch sử và đánh giá

Thế hệ 0 là quần thể khởi tạo. Mỗi hàng history chứa generation, best_distance, average_distance, best_fitness, average_fitness và route. Average fitness là trung bình fitness từng cá thể, không phải nghịch đảo average distance.

Nếu không dừng sớm, số đánh giá hàm mục tiêu là `P + G(P−E)`. Giá trị của elite được tái sử dụng. Thống kê thời gian không tính vào tính tái lập của seed. Với elitism dương, best distance không tăng qua các thế hệ; điều này không chứng minh đã đạt tối ưu toàn cục.

## Random Search

Sinh đúng `B` hoán vị bằng seed cục bộ, đánh giá từng tuyến, giữ tuyến tốt nhất đã thấy. Lặp lại một hoán vị vẫn được tính là một đánh giá vì thuật toán thật sự tính hàm mục tiêu. Ngân sách là số lần đánh giá, không phải thời gian. Benchmark sử dụng `B` bằng số đánh giá thực tế của GA tương ứng.

## Nearest Neighbor

Bắt đầu tại kho, chọn khách hàng chưa thăm có khoảng cách nhỏ nhất, rồi lặp lại đến hết và quay về kho. Phá hòa theo chỉ số hàng giúp kết quả xác định. NN có độ phức tạp bậc hai theo số khách hàng và không bảo đảm tối ưu toàn cục.

## Held–Karp

Quy hoạch động lưu `C(S,j)`: chi phí nhỏ nhất đi từ kho, thăm đúng tập `S`, kết thúc tại `j`. Khởi tạo `C({j},j)=d(0,j)`. Chuyển trạng thái `C(S,j)=minᵢ[C(S\{j},i)+d(i,j)]`. Kết quả là `minⱼ[C(V,j)+d(j,0)]`, kèm backtracking để phục hồi tuyến.

Độ phức tạp thời gian `O(n²2ⁿ)`, bộ nhớ `O(n2ⁿ)`. Giới hạn cứng 12 khách hàng tránh chi phí tăng mất kiểm soát. Chỉ exact solver cung cấp chứng nhận tối ưu cho mô hình Euclid đã nhập. Thiết kế dựa trên quy hoạch động của [Held và Karp (1962)](https://epubs.siam.org/doi/abs/10.1137/0110015).

## Nearest Neighbor + 2-opt

Lấy tuyến NN làm đầu vào mặc định. Chọn hai cạnh không kề nhau; đảo đoạn nằm giữa chúng để loại hai cạnh cũ và nối lại. Chấp nhận khi chiều dài giảm, lặp đến khi không còn cải thiện theo cách duyệt đang dùng. Kho được giữ tại hai đầu. Kết quả không dài hơn tuyến ban đầu nhưng có thể là tối ưu cục bộ.

Tên thuật toán phản ánh nguồn tuyến ban đầu. Kết quả này không được trình bày như GA thuần. Có thể đưa tuyến tùy chọn vào `two_opt(dataset, initial_route=...)`, sau khi kiểm tra hợp lệ.

## Các trường hợp đặc biệt

- Chỉ một khách hàng: tuyến kho–khách hàng–kho vẫn hợp lệ; crossover và inversion giữ nguyên chromosome.
- Tất cả tọa độ trùng nhau: khoảng cách 0; fitness cần epsilon; tỷ lệ cải thiện/gap phải xử lý mẫu số 0.
- Kho ở giữa bảng: dùng `depot_index`, không giả định bằng 0.
- GA ngẫu nhiên: cùng seed trong cùng môi trường cho cùng kết quả, nhưng có thể kém hơn NN hoặc Random Search.

## Tham khảo

Nền tảng GA được trình bày trong [Holland, *Adaptation in Natural and Artificial Systems*, MIT Press, 1992](https://doi.org/10.7551/mitpress/1090.001.0001). Các quyết định cụ thể về biểu diễn, OX, inversion, tỷ lệ và ngân sách ở trên mô tả chính triển khai của dự án, không phải khẳng định rằng mọi GA đều dùng cùng cấu hình.
