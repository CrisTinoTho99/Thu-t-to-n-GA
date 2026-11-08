# Báo cáo dự án

`TSP_AI_Route_Optimizer_Report.pdf` là báo cáo tiếng Việt, xuất từ `docs/report_content.md` và dữ liệu benchmark thật. Báo cáo có 20 phần nội dung, bảng số liệu và hình thực nghiệm. Mã tạo báo cáo: `scripts/build_report.py`.

Bản bàn giao cập nhật có 10 trang, đã render và kiểm tra từng trang để xác nhận chữ tiếng Việt, công thức, bảng và hình không bị cắt hoặc thiếu glyph. Phần 12.1 trình bày mô phỏng xe giao hàng, điều khiển, đồng bộ và kết quả kiểm thử.

Tạo lại trên Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv\Scripts\python.exe scripts/build_report.py --render
```

Generator dùng Arial trong `C:/Windows/Fonts`. Trên hệ điều hành khác, đặt `TSP_REPORT_FONT_DIR` tới thư mục chứa `arial.ttf`, `arialbd.ttf`, `ariali.ttf`, `arialbi.ttf`. Render PDF dùng PyMuPDF; ảnh kiểm tra nằm trong `.qa/report/` và không đưa vào gói phát hành.

Nội dung thuyết trình 12 slide và ghi chú nằm trong `presentation/slides.md`. Word DOCX và PowerPoint PPTX chưa xuất được vì môi trường không có artifact runtime theo quy trình bắt buộc của các công cụ này.
