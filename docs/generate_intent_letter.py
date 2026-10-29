# -*- coding: utf-8 -*-
"""
生成"智教领航"项目合作意向书（简洁正式版，供院长签字）
依赖：pip install python-docx
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUTPUT_PATH = "合作意向书（通用模板）.docx"

PROJECT_NAME = "\u667a\u6559\u9886\u822a\uff1a\u57fa\u4e8eAI\u7684\u5e08\u8303\u751f\u8bd5\u8bb2\u5168\u6d41\u7a0b\u667a\u80fd\u8d4b\u80fd\u7cfb\u7edf"
SHORT_NAME = "\u667a\u6559\u9886\u822a"


def rf(run, name="仿宋", size=12, bold=False, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def para(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         fname="仿宋", fsize=12, bold=False,
         sb=0, sa=6, indent=True, indent_size=None):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(sb)
    pf.space_after = Pt(sa)
    if indent:
        pf.first_line_indent = Pt(indent_size or fsize * 2)
    else:
        pf.first_line_indent = Pt(0)
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


def main():
    doc = Document()

    for section in doc.sections:
        section.top_margin = Cm(3.5)
        section.bottom_margin = Cm(3.0)
        section.left_margin = Cm(3.2)
        section.right_margin = Cm(3.0)

    # ─── 顶部机构名称（红头风格）
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = Pt(0)
    r = p.add_run("_______________________________________")
    rf(r, name="方正小标宋简体", size=22, bold=True, color=(196, 0, 0))

    # 红线分隔（用下划线段落模拟）
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_before = Pt(2)
    p2.paragraph_format.space_after = Pt(12)
    p2.paragraph_format.first_line_indent = Pt(0)
    # 用边框线模拟
    pPr = p2._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "C40000")
    pBdr.append(bottom)
    pPr.append(pBdr)

    # ─── 标题
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(18)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.first_line_indent = Pt(0)
    r_title = p_title.add_run("合  作  意  向  书")
    rf(r_title, name="黑体", size=22, bold=True)

    # ─── 正文称谓
    para(doc,
         "\u667a\u6559\u9886\u822a\u6559\u80b2\u79d1\u6280\u56e2\u961f\uff1a",
         fname="仿宋", fsize=16, bold=False, sb=6, sa=6, indent=False)

    # ─── 正文段落1：项目简介
    para(doc,
         "\u8d35\u56e2\u961f\u7814\u53d1\u7684\u201c" + PROJECT_NAME +
         "\u201d\uff08\u4ee5\u4e0b\u7b80\u79f0\u201c" + SHORT_NAME +
         "\u201d\u7cfb\u7edf\uff09\uff0c\u662f\u4e00\u6b3e\u9762\u5411\u9ad8\u6821\u5e08\u8303\u5b66\u9662\u7684\u591a\u6a21\u6001AI\u8bd5\u8bb2\u8bad\u7ec3\u5e73\u53f0\u3002\u8be5\u7cfb\u7edf\u96c6\u6210\u901a\u4e49\u5343\u95ee\u5927\u6a21\u578b\uff08\u6587\u672c\u3001\u97f3\u9891\u3001\u89c6\u89c9\u4e09\u79cd\u6a21\u6001\uff09\uff0c\u80fd\u591f\u5b9e\u73b0\u8bf4\u6559\u6848\u667a\u80fd\u5206\u6790\u3001\u8bd5\u8bb2\u89c6\u9891\u591a\u6a21\u6001\u8bc4\u4f30\u3001AI\u5bf9\u8bdd\u5f0f\u5907\u8bfe\u3001AI\u8f85\u52a9\u6279\u6539\u548c\u5b66\u751f\u6210\u957f\u753b\u50cf\u4e94\u5927\u6838\u5fc3\u529f\u80fd\uff0c\u5df2\u5b8c\u6210\u5168\u90e8\u5f00\u53d1\u5e76\u90e8\u7f72\u4e0a\u7ebf\u8fd0\u884c\u3002",
         fname="仿宋", fsize=16, sb=0, sa=8)

    # ─── 正文段落2：合作意向声明
    para(doc,
         "我单位（机构）为______________________________，长期关注师范教育领域的创新发展。面对师范生规模迅速扩大、指导教师资源有限、试讲训练缺乏标准化评价手段等现实困境，我单位认为该系统具备明显的应用价值与合作前景。为此，我单位明确表达如下合作意向：",
         fname="仿宋", fsize=16, sb=0, sa=8)

    # ─── 合作意向条款（分点）
    items = [
        "我单位同意并支持将“" + SHORT_NAME +
        "”系统引入相关教学实践训练环节，开展试运营合作；",
        "我单位将协助提供必要的用户群体、师范教育领域专业建议及教学应用场景支持，帮助该系统在真实环境下开展功能验证与应用优化；",
        "我单位将对该团队参加各级学科竞赛及成果推广提供力所能及的支持与保障；",
        "我单位将对该系统进行全面推广应用，并在推广过程中提供必要的技术支持与服务；",
    ]
    for i, item in enumerate(items, 1):
        p_item = doc.add_paragraph()
        p_item.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_item.paragraph_format.first_line_indent = Pt(16 * 2)
        p_item.paragraph_format.space_before = Pt(2)
        p_item.paragraph_format.space_after = Pt(2)
        r_num = p_item.add_run(f"{i}. ")
        rf(r_num, name="仿宋", size=16, bold=True)
        r_text = p_item.add_run(item)
        rf(r_text, name="仿宋", size=16)

    blank(doc)

    # ─── 结尾语
    para(doc,
         "\u5e76\u795d\u8d35\u56e2\u961f\u5728\u7b2c\u4e09\u5c4a\u4e2d\u56fd\u5927\u5b66\u751f\u8ba1\u7b97\u673a\u8bbe\u8ba1\u5927\u8d5bAI\u5e94\u7528\u8d5b\u9053\u53d6\u5f97\u4f18\u5f02\u6210\u7ee9\uff01",
         fname="仿宋", fsize=16, sb=0, sa=24, indent=True)

    # ─── 签字区
    blank(doc, 2)

    sign_tbl = doc.add_table(rows=5, cols=2)
    for row in sign_tbl.rows:
        for cell in row.cells:
            remove_borders(cell)

    sign_rows = [
        ("", "合作单位（盖章）："),
        ("", ""),
        ("", "单位名称：______________________________"),
        ("", "负责人签字：_______________"),
        ("", "日期：______年____月____日"),
    ]
    for row_idx, (left, right) in enumerate(sign_rows):
        cells = sign_tbl.rows[row_idx].cells
        # left cell empty
        p_l = cells[0].paragraphs[0]
        p_l.paragraph_format.first_line_indent = Pt(0)

        p_r = cells[1].paragraphs[0]
        p_r.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_r.paragraph_format.first_line_indent = Pt(0)
        p_r.paragraph_format.space_before = Pt(6)
        p_r.paragraph_format.space_after = Pt(6)
        r_r = p_r.add_run(right)
        bold = row_idx == 0
        rf(r_r, name="仿宋", size=16, bold=bold)

    doc.save(OUTPUT_PATH)
    print(f"\u2705 \u6587\u6863\u5df2\u751f\u6210\uff1a{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
