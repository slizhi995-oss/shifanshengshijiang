# -*- coding: utf-8 -*-
"""
生成"智教领航"项目投资意向书（通用模板，供投资方签字）
依赖：pip install python-docx
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUTPUT_PATH = "\u6295\u8d44\u610f\u5411\u4e66\uff08\u901a\u7528\u6a21\u677f\uff09.docx"

PROJECT_NAME = ("\u667a\u6559\u9886\u822a\uff1a\u57fa\u4e8eAI\u7684\u5e08\u8303"
                "\u751f\u8bd5\u8bb2\u5168\u6d41\u7a0b\u667a\u80fd\u8d4b\u80fd\u7cfb\u7edf")
SHORT_NAME = "\u667a\u6559\u9886\u822a"
TEAM_NAME = "\u667a\u6559\u9886\u822a\u6559\u80b2\u79d1\u6280\u56e2\u961f"


def rf(run, name="\u4eff\u5b8b", size=12, bold=False, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def para(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         fname="\u4eff\u5b8b", fsize=12, bold=False,
         sb=0, sa=6, indent=True):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(sb)
    pf.space_after = Pt(sa)
    pf.first_line_indent = Pt(fsize * 2) if indent else Pt(0)
    r = p.add_run(text)
    rf(r, name=fname, size=fsize, bold=bold)
    return p


def blank(doc, n=1):
    for _ in range(n):
        p = doc.add_paragraph("")
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)


def remove_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def info_table(doc, rows_data):
    """
    双列信息表：左列标签，右列填写区（无边框）
    rows_data: list of (label, value) tuples
    """
    tbl = doc.add_table(rows=len(rows_data), cols=2)
    tbl.style = "Table Grid"
    # 设置列宽
    for row_idx, (label, value) in enumerate(rows_data):
        cells = tbl.rows[row_idx].cells
        cells[0].width = Cm(3.5)
        cells[1].width = Cm(12)
        for cell in cells:
            # 保留外框，去内部边框的部分样式
            pass
        # 左列
        p_l = cells[0].paragraphs[0]
        p_l.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_l.paragraph_format.first_line_indent = Pt(0)
        p_l.paragraph_format.space_before = Pt(3)
        p_l.paragraph_format.space_after = Pt(3)
        r_l = p_l.add_run(label)
        rf(r_l, name="\u9ed1\u4f53", size=11, bold=True)
        # 右列
        p_r = cells[1].paragraphs[0]
        p_r.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_r.paragraph_format.first_line_indent = Pt(0)
        p_r.paragraph_format.space_before = Pt(3)
        p_r.paragraph_format.space_after = Pt(3)
        r_r = p_r.add_run(value)
        rf(r_r, name="\u4eff\u5b8b", size=11)
    return tbl


def main():
    doc = Document()

    for section in doc.sections:
        section.top_margin = Cm(3.0)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3.2)
        section.right_margin = Cm(3.0)

    # ════════════════════════════════
    # 标题
    # ════════════════════════════════
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.paragraph_format.first_line_indent = Pt(0)
    r_t = p_title.add_run("\u6295  \u8d44  \u610f  \u5411  \u4e66")
    rf(r_t, name="\u9ed1\u4f53", size=22, bold=True)

    # 项目名称副标题
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(2)
    p_sub.paragraph_format.space_after = Pt(16)
    p_sub.paragraph_format.first_line_indent = Pt(0)
    r_s = p_sub.add_run(
        "\u2014\u2014\u201c" + PROJECT_NAME + "\u201d")
    rf(r_s, name="\u4eff\u5b8b", size=12, color=(80, 80, 80))

    # ════════════════════════════════
    # 双方基本信息表
    # ════════════════════════════════
    para(doc, "\u4e00\u3001\u53cc\u65b9\u57fa\u672c\u4fe1\u606f",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    info_table(doc, [
        ("\u7532\u65b9\uff08\u9879\u76ee\u65b9\uff09",
         TEAM_NAME + "\u3000\u6240\u5728\u5b66\u6821\uff1a______________________________"),
        ("\u7532\u65b9\u8054\u7cfb\u4eba", "______________________________\u3000\u8054\u7cfb\u65b9\u5f0f\uff1a______________________________"),
        ("\u4e59\u65b9\uff08\u6295\u8d44\u65b9\uff09",
         "______________________________\uff08\u5355\u4f4d/\u4e2a\u4eba\u540d\u79f0\uff09"),
        ("\u4e59\u65b9\u8054\u7cfb\u4eba",
         "______________________________\u3000\u8054\u7cfb\u65b9\u5f0f\uff1a______________________________"),
    ])

    blank(doc)

    # ════════════════════════════════
    # 项目简介
    # ════════════════════════════════
    para(doc, "\u4e8c\u3001\u9879\u76ee\u7b80\u4ecb",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    para(doc,
         ("\u201c" + PROJECT_NAME + "\u201d\u662f\u4e00\u6b3e\u9762\u5411\u9ad8\u6821\u5e08\u8303\u5b66\u9662\u7684\u591a\u6a21\u6001AI\u8bd5\u8bb2\u8bad\u7ec3\u5e73\u53f0\u3002"
          "\u7cfb\u7edf\u96c6\u6210\u901a\u4e49\u5343\u95ee\u5927\u6a21\u578b\uff08\u6587\u672c\u3001\u97f3\u9891\u3001\u89c6\u89c9\u4e09\u79cd\u6a21\u6001\uff09\uff0c"
          "\u56f4\u7ed5\u201c\u6559\u6848\u667a\u80fd\u5206\u6790\u2014\u89c6\u9891\u591a\u6a21\u6001\u8bc4\u4f30\u2014AI\u5bf9\u8bdd\u5f0f\u5907\u8bfe\u2014AI\u8f85\u52a9\u6279\u6539\u2014\u5b66\u751f\u6210\u957f\u753b\u50cf\u201d"
          "\u4e94\u5927\u6838\u5fc3\u529f\u80fd\u6784\u5efa\u5e08\u8303\u8bd5\u8bb2\u8bad\u7ec3\u95ed\u73af\uff0c\u652f\u6301\u7ba1\u7406\u5458\u3001\u6307\u5bfc\u6559\u5e08\u3001"
          "\u5b66\u751f\u4e09\u7aef\u5dee\u5f02\u5316\u4f7f\u7528\uff0c\u5df2\u5b8c\u6210\u5168\u90e8\u5f00\u53d1\u5e76\u90e8\u7f72\u4e0a\u7ebf\u8fd0\u884c\uff0c"
          "\u8986\u76d633\u4e2a\u529f\u80fd\u9875\u9762\u300180\u4f59\u4e2aAPI\u63a5\u53e3\uff0c\u5df2\u7533\u8bf7\u8f6f\u4ef6\u8457\u4f5c\u6743\u3002"),
         fname="\u4eff\u5b8b", fsize=12, sb=0, sa=6)

    para(doc,
         ("\u76ee\u6807\u5e02\u573a\u65b9\u9762\uff1a\u5168\u56fd\u73b0\u6709\u5e08\u8303\u7c7b\u9662\u6821200\u4f59\u6240\u3001\u5f00\u8bbe\u6559\u80b2\u7c7b\u4e13\u4e1a\u7684\u5408\u7b97\u8fbe600\u4f59\u6240\uff0c"
          "\u5728\u6821\u5e08\u8303\u751f\u7ea6300\u4e07\u4eba\uff0c\u6307\u5bfc\u6559\u5e08\u7ea65\u4e07\u4eba\u3002"
          "\u76ee\u524d\u5e02\u573a\u4e0a\u5c1a\u65e0\u4e00\u6b3e\u80fd\u591f\u5c06AI\u6559\u6848\u5206\u6790\u3001\u591a\u6a21\u6001\u89c6\u9891\u8bc4\u4f30\u3001"
          "\u5bf9\u8bdd\u5f0f\u5907\u8bfe\u8bad\u7ec3\u3001\u6559\u52a1\u7ba1\u7406\u95ed\u73af\u548c\u6210\u957f\u753b\u50cf\u8ffd\u8e2a\u96c6\u6210\u4e8e\u4e00\u4f53\u7684\u4ea7\u54c1\uff0c"
          "\u5148\u53d1\u4f18\u52bf\u663e\u8457\u3002"),
         fname="\u4eff\u5b8b", fsize=12, sb=0, sa=6)

    # ════════════════════════════════
    # 盈利模式
    # ════════════════════════════════
    para(doc, "\u4e09\u3001\u76c8\u5229\u6a21\u5f0f\u4e0e\u56de\u62a5\u9884\u671f",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    profit_items = [
        ("SaaS \u8ba2\u9605\u6536\u5165",
         "\u6309\u5b66\u9662\u548c\u5e74\u5ea6\u5411\u9ad8\u6821\u5e08\u8303\u5b66\u9662\u6536\u53d6\u8ba2\u9605\u8d39\uff0c\u5e74\u5355\u4ef7\u9884\u671f3\u20185\u4e07\u5143/\u9662\u6821\uff0c\u662f\u9879\u76ee\u57fa\u7840\u6536\u5165\u6765\u6e90\u3002"),
        ("\u79c1\u6709\u5316\u90e8\u7f72\u670d\u52a1",
         "\u4e3a\u5927\u578b\u9662\u6821\u63d0\u4f9bDocker\u79c1\u6709\u5316\u90e8\u7f72\uff0c\u4e00\u6b21\u6027\u6536\u53d6\u90e8\u7f72\u670d\u52a1\u8d39\u52a0\u5e74\u5ea6\u7ef4\u62a4\u8d39\uff0c\u5355\u4ef7\u8f83\u9ad8\u3002"),
        ("AI \u80fd\u529b\u5f00\u653e",
         "\u5c06\u6559\u6848\u5206\u6790API\u3001\u89c6\u9891\u5206\u6790API\u5bf9\u7b2c\u4e09\u65b9\u5e73\u53f0\u5f00\u653e\uff0c\u6309\u8c03\u7528\u91cf\u6536\u8d39\uff0c\u5177\u6709\u957f\u671f\u589e\u957f\u6f5c\u529b\u3002"),
    ]
    for title, desc in profit_items:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Pt(24)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"\u300a{title}\u300b  ")
        rf(r1, name="\u9ed1\u4f53", size=12, bold=True)
        r2 = p.add_run(desc)
        rf(r2, name="\u4eff\u5b8b", size=12)

    # ════════════════════════════════
    # 投资意向条款
    # ════════════════════════════════
    para(doc, "\u56db\u3001\u6295\u8d44\u610f\u5411\u58f0\u660e",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    para(doc,
         ("\u4e59\u65b9\u5bf9\u201c" + PROJECT_NAME +
          "\u201d\u9879\u76ee\u7684\u5546\u4e1a\u6a21\u5f0f\u3001\u6280\u672f\u5b9e\u529b\u53ca\u5e02\u573a\u524d\u666f\u6709\u6df1\u5165\u4e86\u89e3\uff0c"
          "\u8ba4\u53ef\u8be5\u9879\u76ee\u7684\u53d1\u5c55\u65b9\u5411\u4e0e\u6295\u8d44\u4ef7\u503c\u3002\u4e59\u65b9\u660e\u786e\u8868\u8fbe\u5982\u4e0b\u6295\u8d44\u610f\u5411\uff1a"),
         fname="\u4eff\u5b8b", fsize=12, sb=0, sa=6)

    intent_items = [
        ("\u6295\u8d44\u610f\u5411\u8868\u8fbe",
         "\u4e59\u65b9\u6709\u610f\u5411\u7532\u65b9\u56e2\u961f\u7814\u53d1\u7684\u201c" + SHORT_NAME +
         "\u201d\u9879\u76ee\u8fdb\u884c\u6295\u8d44\u5408\u4f5c\uff0c\u5177\u4f53\u6295\u8d44\u65b9\u5f0f\u3001\u91d1\u989d\u53ca\u80a1\u6743\u5360\u6bd4\u53e6\u884c\u534f\u5546\u786e\u5b9a\uff1b"),
        ("\u5c3d\u8c03\u67e5\u610f\u5411",
         "\u4e59\u65b9\u540c\u610f\u5728\u672c\u610f\u5411\u4e66\u7b7e\u7f72\u540e\uff0c\u5c31\u9879\u76ee\u8d22\u52a1\u3001\u6280\u672f\u53ca\u5e02\u573a\u60c5\u51b5\u5f00\u5c55\u5c3d\u8c03\u67e5\uff08Due Diligence\uff09\uff0c\u5c3d\u8c03\u67e5\u67d0\u4ee5\u8fdb\u884c\u6b63\u5f0f\u6295\u8d44\u8c08\u5224\uff1b"),
        ("\u9879\u76ee\u652f\u6301",
         "\u4e59\u65b9\u5c06\u5229\u7528\u81ea\u8eab\u8d44\u6e90\u7f51\u7edc\u4e3a\u7532\u65b9\u63d0\u4f9b\u884c\u4e1a\u8d44\u6e90\u5bf9\u63a5\u3001\u5e02\u573a\u5f00\u62d3\u53ca\u6218\u7565\u54a8\u8be2\u7b49\u589e\u503c\u670d\u52a1\uff0c\u5e2e\u52a9\u9879\u76ee\u5feb\u901f\u6210\u957f\uff1b"),
        ("\u4fdd\u5bc6\u627f\u8bfa",
         "\u4e59\u65b9\u627f\u8bfa\u5bf9\u5728\u5c3d\u8c03\u67e5\u53ca\u534f\u5546\u8fc7\u7a0b\u4e2d\u83b7\u53d6\u7684\u7532\u65b9\u5546\u4e1a\u79d8\u5bc6\u4e25\u683c\u4fdd\u5bc6\uff0c\u672a\u7ecf\u7532\u65b9\u4e66\u9762\u540c\u610f\u4e0d\u5f97\u5411\u4efb\u4f55\u7b2c\u4e09\u65b9\u6cc4\u9732\u3002"),
    ]
    for i, (title, desc) in enumerate(intent_items, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Pt(24)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{i}. \u3010{title}\u3011  ")
        rf(r1, name="\u9ed1\u4f53", size=12, bold=True)
        r2 = p.add_run(desc)
        rf(r2, name="\u4eff\u5b8b", size=12)

    # ════════════════════════════════
    # 意向投资金额（填写区）
    # ════════════════════════════════
    para(doc, "\u4e94\u3001\u610f\u5411\u6295\u8d44\u91d1\u989d\u53ca\u65b9\u5f0f\uff08\u4e59\u65b9\u586b\u5199\uff09",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    info_table(doc, [
        ("\u610f\u5411\u6295\u8d44\u91d1\u989d",
         "\u4eba\u6c11\u5e01______\u4e07\u5143\u6574\uff08\u5927\u5199\uff1a__________________\uff09"),
        ("\u6295\u8d44\u65b9\u5f0f",
         "\u25a1 \u80a1\u6743\u6295\u8d44\u3000\u25a1 \u53ef\u8f6c\u503a\u3000\u25a1 \u6218\u7565\u5408\u4f5c\u3000\u25a1 \u5176\u4ed6\uff1a______"),
        ("\u9884\u671f\u4f30\u503c",
         "\u9879\u76ee\u6295\u8d44\u524d\u4f30\u503c\uff08Pre-money\uff09\uff1a\u4eba\u6c11\u5e01______\u4e07\u5143"),
        ("\u9884\u671f\u6295\u8d44\u5c45\u9996\u65f6\u95f4",
         "______\u5e74____\u6708\u524d\u5b8c\u6210\u6b63\u5f0f\u6295\u8d44\u6c7d\u7b7e\u7f72"),
    ])

    blank(doc)

    # ════════════════════════════════
    # 声明与效力
    # ════════════════════════════════
    para(doc, "\u516d\u3001\u58f0\u660e\u4e0e\u610f\u5411\u4e66\u6548\u529b",
         fname="\u9ed1\u4f53", fsize=14, bold=True, sb=4, sa=6, indent=False)

    para(doc,
         ("\u672c\u610f\u5411\u4e66\u4ec5\u4ee3\u8868\u4e59\u65b9\u5bf9\u6295\u8d44\u5408\u4f5c\u7684\u4e3b\u89c2\u610f\u613f\uff0c\u4e0d\u6784\u6210\u5177\u6cd5\u5f8b\u7ea6\u675f\u529b\u7684\u6295\u8d44\u534f\u8bae\uff1b"
          "\u6b63\u5f0f\u6295\u8d44\u5c06\u4ee5\u53cc\u65b9\u53e6\u884c\u7b7e\u8ba2\u7684\u300a\u6295\u8d44\u534f\u8bae\u4e66\u300b\u4e3a\u51c6\u3002"
          "\u672c\u610f\u5411\u4e66\u4e00\u5f0f\u4e24\u4efd\uff0c\u7532\u4e59\u53cc\u65b9\u5404\u6267\u4e00\u4efd\uff0c\u81ea\u53cc\u65b9\u7b7e\u5b57\u4e4b\u65e5\u8d77\u751f\u6548\u3002"),
         fname="\u4eff\u5b8b", fsize=12, sb=0, sa=6)

    # ════════════════════════════════
    # 签字区
    # ════════════════════════════════
    blank(doc, 2)

    sign_tbl = doc.add_table(rows=7, cols=2)
    sign_tbl.style = "Table Grid"
    for row in sign_tbl.rows:
        for cell in row.cells:
            remove_borders(cell)

    sign_data = [
        ("\u7532  \u65b9\uff08\u76d6\u7ae0\uff09", "\u4e59  \u65b9\uff08\u76d6\u7ae0\uff09"),
        (TEAM_NAME, "______________________________"),
        ("", ""),
        ("\u6388\u6743\u4ee3\u8868\u7b7e\u5b57\uff1a_______________",
         "\u6388\u6743\u4ee3\u8868\u7b7e\u5b57\uff1a_______________"),
        ("", ""),
        ("\u65e5\u671f\uff1a______\u5e74____\u6708____\u65e5",
         "\u65e5\u671f\uff1a______\u5e74____\u6708____\u65e5"),
        ("", ""),
    ]
    for row_idx, (left, right) in enumerate(sign_data):
        cells = sign_tbl.rows[row_idx].cells
        for col_idx, text in enumerate([left, right]):
            p = cells[col_idx].paragraphs[0]
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER
                           if row_idx in (0, 1) else WD_ALIGN_PARAGRAPH.LEFT)
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(5)
            r = p.add_run(text)
            bold = row_idx in (0, 1)
            rf(r, name="\u9ed1\u4f53" if bold else "\u4eff\u5b8b",
               size=12, bold=bold)

    doc.save(OUTPUT_PATH)
    print(f"\u2705 \u6587\u6863\u5df2\u751f\u6210\uff1a{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
