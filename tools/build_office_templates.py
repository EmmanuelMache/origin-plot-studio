"""Make the two empty Office files the app fills with pictures of graphs (Export > Send to PowerPoint / Word).

    origin_plot_app/opstudio/office/blank.pptx   a 16:9 presentation with one empty slide that holds one picture
    origin_plot_app/opstudio/office/blank.docx   an A4 document with one centred paragraph that holds one picture

They are written with python-pptx and python-docx (both MIT) so that PowerPoint and Word open them as their own files.
The app itself needs neither package: office_export.py copies these files and replaces the picture, its size and the
number of slides / paragraphs. Run again only to change the page or slide format:  python tools/build_office_templates.py"""
import os, io, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "origin_plot_app", "opstudio", "office")


def tiny_png():
    import struct, zlib
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b"")


def main():
    from pptx import Presentation
    from pptx.util import Inches
    from docx import Document
    from docx.shared import Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    os.makedirs(OUT, exist_ok=True)
    prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6]); s.shapes.add_picture(io.BytesIO(tiny_png()), Inches(1), Inches(1), Inches(4), Inches(3))
    prs.part._element.find("{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz").attrib.pop("type", None)      # the size is 16:9, not the 4:3 the attribute of the start file says
    prs.save(os.path.join(OUT, "blank.pptx"))
    doc = Document(); sec = doc.sections[0]; sec.page_width = Cm(21.0); sec.page_height = Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.5); sec.top_margin = sec.bottom_margin = Cm(2.5)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(io.BytesIO(tiny_png()), width=Cm(10), height=Cm(7.5))
    doc.save(os.path.join(OUT, "blank.docx"))
    for f in ("blank.pptx", "blank.docx"): print(f, os.path.getsize(os.path.join(OUT, f)), "bytes")


if __name__ == "__main__":
    sys.exit(main())
