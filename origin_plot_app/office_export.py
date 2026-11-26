"""Graphs as pictures in a PowerPoint presentation or a Word document.

    write_pptx(path, pictures)    one slide per picture, the picture as large as the slide allows, centred
    write_docx(path, pictures)    one centred picture per paragraph, at most the width of the text of an A4 page

A picture is (png bytes, width in inches, height in inches, name). Nothing but the Python standard library is used:
the two empty Office files in the folder 'office' (made once with tools/build_office_templates.py) are copied, and the
picture, its size and the number of slides / paragraphs are written into the copy."""
import os, re, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
EMU = 914400                       # Office's unit: 914400 to the inch
SLIDE = (13.333, 7.5)              # inches (16:9)
TEXT_W, TEXT_H = 6.3, 9.3          # the text area of the A4 page of blank.docx (2.5 cm margins), a little less in height

_XML = lambda t: str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fit(w, h, max_w, max_h):
    k = min(max_w / max(w, 1e-9), max_h / max(h, 1e-9)); return w * k, h * k


def _copy(template, path, changed, added):
    """The template zip written to 'path' with some parts replaced and others added."""
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, changed.get(item.filename, zin.read(item.filename)))
        for name, data in added.items(): zout.writestr(name, data)
    return path


def write_pptx(path, pictures, margin=0.35):
    """One slide per picture. The picture keeps its proportions and fills the slide up to a small margin."""
    if not pictures: raise ValueError("no picture to put on a slide")
    tpl = os.path.join(HERE, "office", "blank.pptx")
    with zipfile.ZipFile(tpl) as z:
        slide = z.read("ppt/slides/slide1.xml").decode("utf-8"); srel = z.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        pres = z.read("ppt/presentation.xml").decode("utf-8"); prel = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8"); ct = z.read("[Content_Types].xml").decode("utf-8")
    first = re.search(r'<p:sldId id="(\d+)" r:id="(rId\d+)"/>', pres); sid0 = int(first.group(1)); used = [int(n) for n in re.findall(r'Id="rId(\d+)"', prel)]
    changed, added, ids = {}, {}, []
    for k, (png, w, h, name) in enumerate(pictures, 1):
        pw, ph = _fit(w, h, SLIDE[0] - 2 * margin, SLIDE[1] - 2 * margin); x = (SLIDE[0] - pw) / 2; y = (SLIDE[1] - ph) / 2
        xml = re.sub(r'<a:off x="\d+" y="\d+"/><a:ext cx="\d+" cy="\d+"/>', f'<a:off x="{int(x * EMU)}" y="{int(y * EMU)}"/><a:ext cx="{int(pw * EMU)}" cy="{int(ph * EMU)}"/>', slide, count=1)
        xml = re.sub(r'name="Picture 1" descr="[^"]*"', f'name="Graph {k}" descr="{_XML(name)}"', xml, count=1)
        rel = srel.replace("../media/image1.png", f"../media/image{k}.png")
        (changed if k == 1 else added)[f"ppt/slides/slide{k}.xml"] = xml.encode("utf-8"); (changed if k == 1 else added)[f"ppt/slides/_rels/slide{k}.xml.rels"] = rel.encode("utf-8")
        (changed if k == 1 else added)[f"ppt/media/image{k}.png"] = png
        if k == 1: ids.append(first.group(0)); continue
        rid = max(used) + 1; used.append(rid); ids.append(f'<p:sldId id="{sid0 + k - 1}" r:id="rId{rid}"/>')
        prel = prel.replace("</Relationships>", f'<Relationship Id="rId{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{k}.xml"/></Relationships>')
        ct = ct.replace("</Types>", f'<Override PartName="/ppt/slides/slide{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>')
    pres = pres.replace(first.group(0), "".join(ids))
    changed.update({"ppt/presentation.xml": pres.encode("utf-8"), "ppt/_rels/presentation.xml.rels": prel.encode("utf-8"), "[Content_Types].xml": ct.encode("utf-8")})
    return _copy(tpl, path, changed, added)


def write_docx(path, pictures, max_w=TEXT_W, max_h=TEXT_H):
    """One picture per paragraph, centred. A picture wider than the text of the page is made as wide as the text; a
    smaller one keeps its own size (the size of the figure), so a figure made for a journal column stays that wide."""
    if not pictures: raise ValueError("no picture to put in the document")
    tpl = os.path.join(HERE, "office", "blank.docx")
    with zipfile.ZipFile(tpl) as z:
        doc = z.read("word/document.xml").decode("utf-8"); rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
    para = re.search(r"<w:p>(?:(?!</w:p>).)*<w:drawing>.*?</w:drawing>.*?</w:p>", doc, re.S).group(0); rid0 = re.search(r'r:embed="(rId\d+)"', para).group(1)
    used = [int(n) for n in re.findall(r'Id="rId(\d+)"', rels)]; changed, added, paras = {}, {}, []
    for k, (png, w, h, name) in enumerate(pictures, 1):
        pw, ph = (w, h) if (w <= max_w and h <= max_h) else _fit(w, h, max_w, max_h); cx, cy = int(pw * EMU), int(ph * EMU)
        if k == 1: rid = rid0
        else:
            n = max(used) + 1; used.append(n); rid = f"rId{n}"
            rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{k}.png"/></Relationships>')
        q = re.sub(r'cx="\d+" cy="\d+"', f'cx="{cx}" cy="{cy}"', para).replace(f'r:embed="{rid0}"', f'r:embed="{rid}"')
        q = re.sub(r'<wp:docPr id="\d+" name="[^"]*"/>', f'<wp:docPr id="{k}" name="Graph {k}" descr="{_XML(name)}"/>', q, count=1)
        q = re.sub(r'<pic:cNvPr id="\d+" name="[^"]*"/>', f'<pic:cNvPr id="{k}" name="{_XML(name)}"/>', q, count=1)
        paras.append(q); (changed if k == 1 else added)[f"word/media/image{k}.png"] = png
    changed.update({"word/document.xml": doc.replace(para, "".join(paras)).encode("utf-8"), "word/_rels/document.xml.rels": rels.encode("utf-8")})
    return _copy(tpl, path, changed, added)


def figure_png(fig, dpi):
    """(png bytes, width in, height in) of a figure as it is drawn, at 'dpi' dots per inch."""
    import io
    buf = io.BytesIO(); w, h = fig.get_size_inches(); fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return buf.getvalue(), float(w), float(h)
