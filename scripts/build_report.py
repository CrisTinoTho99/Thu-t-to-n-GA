"""Build a PDF report and Markdown slides from measured benchmark artifacts.

The report source is docs/report_content.md. PDF generation requires reportlab;
optional rendering uses PyMuPDF. No benchmark values are invented or substituted.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import textwrap
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def inline(text: str) -> str:
    """Convert the small Markdown inline subset used by project documentation."""
    # PDF's standard Courier has no Vietnamese/math subset glyphs. Keep
    # mathematical notation explicit and portable, and use embedded Arial for
    # inline source fragments containing non-ASCII characters.
    replacements = {
        "cᵢⱼ = sqrt((xᵢ − xⱼ)² + (yᵢ − yⱼ)²)": "c(i,j) = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)",
        "min L(π) = c(d,π₁) + Σₖ₌₁ⁿ⁻¹ c(πₖ,πₖ₊₁) + c(πₙ,d)": "min L(pi) = c(d,pi_1) + sum(k=1..n-1)c(pi_k,pi_(k+1)) + c(pi_n,d)",
        "(xᵢ,yᵢ)": "(x_i,y_i)", "10⁻¹²": "10^-12", "O(n²2ⁿ)": "O(n^2 * 2^n)", "O(n2ⁿ)": "O(n * 2^n)",
        "−": "-", "–": "-", "—": "-", "‑": "-",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    # Protect code before parsing emphasis: multiplication signs in formulas
    # must not become italic tags spanning multiple <font> elements.
    code_fragments = []

    def code_token(match):
        value = match.group(1)
        font = "Report" if any(ord(char) > 127 for char in value) else "Courier"
        code_fragments.append(f'<font face="{font}">{escape(value)}</font>')
        return f"\x00CODE{len(code_fragments) - 1}\x00"

    text = re.sub(r"`([^`]+)`", code_token, text)
    text = escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#4338CA">\1</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^\s*][^*]*[^\s*])\*(?!\*)", r"<i>\1</i>", text)
    for index, fragment in enumerate(code_fragments):
        text = text.replace(f"\x00CODE{index}\x00", fragment)
    return text


def register_fonts() -> None:
    """Use bundled Windows Arial, or a caller-provided portable font directory."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    font_dir = Path(os.environ.get("TSP_REPORT_FONT_DIR", "C:/Windows/Fonts"))
    candidates = [
        ("Report", "arial.ttf"), ("Report-Bold", "arialbd.ttf"),
        ("Report-Italic", "ariali.ttf"), ("Report-BoldItalic", "arialbi.ttf"),
    ]
    if not all((font_dir / filename).exists() for _, filename in candidates):
        raise RuntimeError("Arial font files are unavailable. Set TSP_REPORT_FONT_DIR to a directory containing arial.ttf, arialbd.ttf, ariali.ttf and arialbi.ttf.")
    for name, filename in candidates:
        pdfmetrics.registerFont(TTFont(name, str(font_dir / filename)))
    pdfmetrics.registerFontFamily("Report", normal="Report", bold="Report-Bold", italic="Report-Italic", boldItalic="Report-BoldItalic")


def build_pdf(source: Path, output: Path, summary_path: Path) -> None:
    """Render the complete Markdown report with measured table and figures."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Preformatted, Image, PageBreak, KeepTogether,
    )
    register_fonts()
    output.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    usable = page_width - 4 * cm
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBody", fontName="Report", fontSize=10.1, leading=14.5,
                              spaceAfter=8, textColor=colors.HexColor("#1F2937"), splitLongWords=True))
    styles.add(ParagraphStyle(name="ReportTitle", fontName="Report-Bold", fontSize=24, leading=30,
                              spaceAfter=20, textColor=colors.black))
    styles.add(ParagraphStyle(name="ReportHeading", fontName="Report-Bold", fontSize=14, leading=19,
                              spaceBefore=14, spaceAfter=8, textColor=colors.black, keepWithNext=True))
    styles.add(ParagraphStyle(name="ReportSubheading", fontName="Report-Bold", fontSize=11.2, leading=16,
                              spaceBefore=10, spaceAfter=6, textColor=colors.black, keepWithNext=True))
    styles.add(ParagraphStyle(name="ReportBullet", parent=styles["ReportBody"], leftIndent=12, firstLineIndent=0,
                              bulletIndent=0, spaceAfter=5))
    styles.add(ParagraphStyle(name="ReportCode", fontName="Courier", fontSize=7.5, leading=10.5, spaceAfter=10))
    styles.add(ParagraphStyle(name="ReportCell", fontName="Report", fontSize=8, leading=11, spaceAfter=0))
    styles.add(ParagraphStyle(name="ReportCellHead", parent=styles["ReportCell"], fontName="Report-Bold", textColor=colors.white))
    styles.add(ParagraphStyle(name="ReportCaption", fontName="Report-Italic", fontSize=9, leading=13,
                              textColor=colors.HexColor("#475569"), spaceAfter=10))
    story: list = []

    def table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
        count = max(len(row) for row in rows)
        formatted = [[Paragraph(inline(value), styles["ReportCellHead" if i == 0 else "ReportCell"])
                      for value in row + [""] * (count - len(row))] for i, row in enumerate(rows)]
        result = Table(formatted, colWidths=widths or [usable / count] * count, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return result

    lines = source.read_text(encoding="utf-8").splitlines()
    position = 0
    while position < len(lines):
        line = lines[position].strip()
        if not line or line == "---":
            position += 1
            continue
        if line.startswith("```"):
            code = []
            position += 1
            while position < len(lines) and not lines[position].strip().startswith("```"):
                code.extend(textwrap.wrap(lines[position], width=94, replace_whitespace=False, drop_whitespace=False) or [""])
                position += 1
            story.append(Preformatted("\n".join(code), styles["ReportCode"]))
            position += 1
            continue
        if line.startswith("|"):
            rows = []
            while position < len(lines) and lines[position].strip().startswith("|"):
                parts = [part.strip() for part in lines[position].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", part) for part in parts):
                    rows.append(parts)
                position += 1
            if rows:
                story.extend([table(rows), Spacer(1, 10)])
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading:
            level = len(heading.group(1))
            style = "ReportTitle" if level == 1 else "ReportHeading" if level == 2 else "ReportSubheading"
            story.append(Paragraph(inline(heading.group(2)), styles[style]))
            position += 1
            continue
        bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)", line)
        if bullet:
            story.append(Paragraph(inline(bullet.group(1)), styles["ReportBullet"], bulletText="-"))
            position += 1
            continue
        paragraph = [line]
        position += 1
        while position < len(lines) and lines[position].strip() and not re.match(r"^(#|\||```|[-*]\s|\d+[.)]\s)", lines[position].strip()):
            paragraph.append(lines[position].strip())
            position += 1
        story.append(Paragraph(inline(" ".join(paragraph)), styles["ReportBody"]))

    # The compact appendix is read directly from the benchmark export, never
    # from hand-entered numbers in prose.
    with summary_path.open(encoding="utf-8-sig", newline="") as stream:
        measured = list(csv.DictReader(stream))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Measured benchmark appendix", styles["ReportHeading"]))
    story.append(Paragraph("Distances use abstract Euclidean units. Runtime is measured wall time in seconds. Standard deviation uses repeated runs. The complete machine-readable table and raw seeds accompany this report.", styles["ReportBody"]))
    rows = [["n", "Algorithm", "Runs", "Mean", "Std", "Best", "Time s"]]
    for row in measured:
        short = row["algorithm"].replace("Genetic Algorithm", "GA").replace("Nearest Neighbor", "NN").replace("Random Search", "Random").replace("Exact (Held–Karp)", "Exact")
        rows.append([row["customer_count"], short, row["runs"],
                     f'{float(row["mean_distance"]):.2f}', f'{float(row["std_distance"]):.2f}',
                     f'{float(row["best_distance"]):.2f}', f'{float(row["mean_runtime_seconds"]):.4f}'])
    story.append(table(rows, [45, 116, 36, 61, 50, 61, usable - 369]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Source: results/final/benchmark_summary.csv. Exact-solver evaluation counts describe DP transitions and should not be compared to counts of full-tour evaluations.", styles["ReportCaption"]))
    for filename, caption in (
        ("benchmark_mean_distance.png", "Mean route distance across repeated runs"),
        ("benchmark_mean_runtime_seconds.png", "Mean runtime across repeated runs"),
    ):
        image_path = ROOT / "results" / "figures" / filename
        if image_path.exists():
            image = Image(str(image_path))
            factor = min(usable / image.imageWidth, (page_height * 0.42) / image.imageHeight)
            image.drawWidth, image.drawHeight = image.imageWidth * factor, image.imageHeight * factor
            story.extend([Spacer(1, 12), KeepTogether([image, Paragraph(caption, styles["ReportCaption"])])])

    def furniture(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Report", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(2 * cm, page_height - 1.15 * cm, "TSP AI Route Optimizer")
        canvas.drawRightString(page_width - 2 * cm, 1.15 * cm, str(document.page))
        canvas.restoreState()

    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm,
                                 topMargin=1.85 * cm, bottomMargin=1.8 * cm,
                                 title="TSP AI Route Optimizer academic report", author="TSP AI Route Optimizer project")
    document.build(story, onFirstPage=furniture, onLaterPages=furniture)


def build_slides(summary_path: Path, destination: Path) -> None:
    """Prepare complete presentation content, including measured outcomes."""
    with summary_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ga = [row for row in rows if row["algorithm"] == "Genetic Algorithm"]
    table = ["| Khách hàng | GA mean | NN | Random mean | GA cải thiện so với NN |", "|---:|---:|---:|---:|---:|"]
    losses = []
    for row in ga:
        size = row["customer_count"]
        matching = {candidate["algorithm"]: candidate for candidate in rows if candidate["customer_count"] == size}
        nn = matching.get("Nearest Neighbor")
        random = matching.get("Random Search")
        table.append(f'| {size} | {float(row["mean_distance"]):.2f} | {float(nn["mean_distance"]):.2f} | {float(random["mean_distance"]):.2f} | {float(row["mean_improvement_percent"]):.2f}% |')
        if nn and float(row["mean_distance"]) > float(nn["mean_distance"]):
            losses.append(f'- Với {size} khách hàng, GA có khoảng cách trung bình {float(row["mean_distance"]):.2f}, lớn hơn NN {float(nn["mean_distance"]):.2f}.')
        if random and float(row["mean_distance"]) > float(random["mean_distance"]):
            losses.append(f'- Với {size} khách hàng, GA có khoảng cách trung bình lớn hơn Random Search trong thiết lập này.')
    findings = (ROOT / "results/final/findings.md")
    real_findings = findings.read_text(encoding="utf-8") if findings.exists() else "\n".join(losses)
    content = """# TSP AI Route Optimizer

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

{table}

Đơn vị khoảng cách Euclid. Mean lấy từ số lần chạy ghi trong bảng CSV.

Ghi chú thuyết trình: Tỷ lệ cải thiện dương nghĩa là ngắn hơn NN, âm nghĩa là dài hơn. Không suy ra GA luôn tốt hơn từ một thiết lập.

## Slide 11  Phân tích kết quả thực tế

{findings}

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
""".replace("{table}", "\n".join(table)).replace("{findings}", real_findings)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def render_pdf(pdf_path: Path, directory: Path) -> int:
    """Render every page with PyMuPDF for visual inspection on Windows."""
    import pymupdf
    directory.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf_path) as document:
        for index, page in enumerate(document):
            page.get_pixmap(matrix=pymupdf.Matrix(1.35, 1.35), alpha=False).save(directory / f"page-{index + 1:02d}.png")
        return len(document)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/report_content.md")
    parser.add_argument("--summary", type=Path, default=ROOT / "results/final/benchmark_summary.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "report/TSP_AI_Route_Optimizer_Report.pdf")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file() or not args.summary.is_file():
        parser.error("Complete report Markdown and measured benchmark summary must exist before export.")
    build_pdf(args.source, args.output, args.summary)
    build_slides(args.summary, ROOT / "presentation/slides.md")
    result = {"pdf": str(args.output), "slides": str(ROOT / "presentation/slides.md")}
    if args.render:
        result["rendered_pages"] = render_pdf(args.output, ROOT / ".qa/report")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
