"""Formula multiplication must survive Markdown-to-PDF inline conversion."""
from xml.etree import ElementTree

import pytest
from scripts.build_report import inline


@pytest.mark.parametrize("source", [
    "Duration `T = sum(L_i / v) + n*d`. Position `P = (1-u)*P_start + u*P_end`.",
    "**Formula `a*b`** and *emphasis* with `x < 2` and `d >= 0`.",
])
def test_code_formula_is_not_parsed_as_italic_markup(source):
    markup = inline(source)
    root = ElementTree.fromstring(f"<p>{markup}</p>")
    for code in root.iter("font"):
        assert not list(code), "Emphasis markup must not be inserted inside source code"
    assert "*" in "".join(root.itertext())
