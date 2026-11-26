"""Graphs as pictures in a PowerPoint presentation or a Word document.

    write_pptx(path, pictures)    one slide per picture, the picture as large as the slide allows, centred
    write_docx(path, pictures)    one centred picture per paragraph, at most the width of the text of an A4 page

A picture is (png bytes, width in inches, height in inches, name). Nothing but the Python standard library is used:
the two empty Office files in the folder 'opstudio/office' (made once with tools/build_office_templates.py) are copied, and the
picture, its size and the number of slides / paragraphs are written into the copy."""
import os, re, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# The two empty files are kept inside 'opstudio', a folder the app's updater installs whole. In a folder of their own
# ('office', 5.57.2 - 5.58.0) an updated app did not get them, and Send to PowerPoint / Word could not write anything.
TEMPLATES = os.path.join(HERE, "opstudio", "office")


def template(name):
    """The path of an empty Office file of the app - with a plain message when the installation does not have it."""
    p = os.path.join(TEMPLATES, name)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"the app's file '{name}' is missing from this installation ({p}). Update the app once more (Help > Check for updates and install), or run Setup again")
    return p
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
    tpl = template("blank.pptx")
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
    tpl = template("blank.docx")
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


# ----------------------------------------------------------------------------------------------- straight into the open program (Windows)
def _office(name):
    """The running PowerPoint or Word (or a new one), through Windows automation - the way the app talks to Origin."""
    import pythoncom, win32com.client
    try: pythoncom.CoInitialize()
    except Exception: pass
    try: app = win32com.client.GetActiveObject(name)
    except Exception: app = win32com.client.Dispatch(name)
    try: app.Visible = True
    except Exception: pass
    return app


def send_live(kind, files):
    """Put pictures straight into PowerPoint or Word, as you would by hand. files: [(png path, width in, height in, name)].

    PowerPoint: the presentation you have open (a new one if none is) gets one new slide per picture at its end, the
    picture as large as the slide allows; the last new slide is shown. Word: the pictures are inserted where the cursor
    stands in the document you have open (a new document if none is), each in its own centred paragraph, no wider than
    the text. Nothing is saved: the presentation or document stays yours to save.
    Returns a sentence saying where the pictures went. Raises when the program is not installed or refuses - the caller
    then writes a file instead."""
    if not files: raise ValueError("no picture to send")
    if kind == "pptx":
        app = _office("PowerPoint.Application"); new = app.Presentations.Count == 0
        pres = app.Presentations.Add() if new else app.ActivePresentation
        sw, sh = float(pres.PageSetup.SlideWidth), float(pres.PageSetup.SlideHeight); m = 0.35 * 72.0; slide = None
        for png, w, h, name in files:
            slide = pres.Slides.Add(pres.Slides.Count + 1, 12)                       # 12 = a blank slide
            pw, ph = _fit(w * 72.0, h * 72.0, sw - 2 * m, sh - 2 * m)
            pic = slide.Shapes.AddPicture(os.path.abspath(png), False, True, (sw - pw) / 2.0, (sh - ph) / 2.0, pw, ph)
            try: pic.AlternativeText = str(name)
            except Exception: pass
        try: app.ActiveWindow.View.GotoSlide(slide.SlideIndex); app.Activate()
        except Exception: pass
        return f"{len(files)} new slide(s) at the end of " + ("a new presentation" if new else f"the open presentation '{pres.Name}'")
    app = _office("Word.Application"); new = app.Documents.Count == 0
    doc = app.Documents.Add() if new else app.ActiveDocument
    try: text_w = float(doc.PageSetup.PageWidth) - float(doc.PageSetup.LeftMargin) - float(doc.PageSetup.RightMargin)
    except Exception: text_w = TEXT_W * 72.0
    sel = app.Selection
    for png, w, h, name in files:
        shape = sel.InlineShapes.AddPicture(os.path.abspath(png), False, True)
        try:
            shape.LockAspectRatio = True; want = min(w * 72.0, text_w)
            if abs(float(shape.Width) - want) > 1.0: shape.Width = want
            shape.AlternativeText = str(name)
        except Exception: pass
        try: sel.ParagraphFormat.Alignment = 1                                       # centred
        except Exception: pass
        sel.TypeParagraph()
    try: app.Activate()
    except Exception: pass
    return f"{len(files)} picture(s) at the cursor of " + ("a new document" if new else f"the open document '{doc.Name}'")
