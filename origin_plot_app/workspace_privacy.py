"""workspace_privacy.py - Settings > Privacy and connections: what may leave this computer.

The dialog only shows and changes the outbound policy (outbound_policy.py); the policy itself is enforced where a
request is sent. Turning a switch off here is therefore not what blocks a request - the transport asks the policy.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QCheckBox, QGroupBox, QPushButton,
                               QButtonGroup, QFileDialog, QDialogButtonBox, QFrame)
import outbound_policy as OP

LEVEL_TEXT = [
    ("local_only", "Local-only", "Nothing is sent from this app: no update check, no AI assistant, no web search, no diagnostics, no shared learning. "
                                 "Reading files, drawing graphs, projects, personal learning and Origin on this computer work as always."),
    ("minimal", "Minimal AI context", "The AI assistant gets your question and generic information only (kind of data, roles of the columns). "
                                      "Sample names, graph labels and file names are replaced by stand-ins such as 'Sample 1'; folders by '<folder>'. No measurements, no results."),
    ("metadata", "Approved metadata", "Also the real labels and the structure (column names, graph kinds, counts). Still no measurements, results, pictures or documents."),
    ("scientific", "Approved scientific content", "Also measurements, results, pictures and documents you select, sent to the service you chose. Use this only for work you may share with that service."),
]
CHANNEL_TEXT = [
    ("update_check", "Look for a new version (at start and from Help)"), ("update_download", "Download an update when you ask for it"),
    ("ai", "The AI assistant (the service you connect it to)"), ("web_search", "The assistant's free web search"),
    ("diagnostics", "Send diagnostics (off: a diagnostic file is only written for you to review)"), ("learning_sync", "Shared learning with a lab or community service"),
]


class PrivacyDialog(QDialog):
    def __init__(self, ws=None):
        super().__init__(ws); self.ws = ws; self.setWindowTitle("Privacy and connections"); self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        head = QLabel("<b>What may leave this computer</b><br>Your files, projects and graphs stay here in every mode. These choices are kept with your own settings "
                      "(not in a project) and are checked at the moment a request would be sent."); head.setWordWrap(True); lay.addWidget(head)
        box = QGroupBox("Level"); bl = QVBoxLayout(box); self.group = QButtonGroup(self); self.radios = {}
        for key, title, text in LEVEL_TEXT:
            r = QRadioButton(title); r.setChecked(OP.level() == key); self.group.addButton(r); self.radios[key] = r; bl.addWidget(r)
            t = QLabel(text); t.setWordWrap(True); t.setIndent(22); t.setStyleSheet("color:#555;"); bl.addWidget(t)
        lay.addWidget(box)
        cbox = QGroupBox("Connections (used only when the level is not Local-only)"); cl = QVBoxLayout(cbox); self.checks = {}
        for key, text in CHANNEL_TEXT:
            c = QCheckBox(text); c.setChecked(OP.channel_on(key)); self.checks[key] = c; cl.addWidget(c)
        lay.addWidget(cbox)
        try:
            import secure_store
            keys = QLabel("<b>Keys and tokens.</b> " + secure_store.describe() + " A key is never put into a project, an export, a diagnostic file or a shared recipe.")
        except Exception:
            keys = QLabel("")
        keys.setWordWrap(True); lay.addWidget(keys)
        prof = QLabel(("This is a build for other people: updates are installed only when their publisher's signature is verified, and the app cannot rewrite its own code."
                       if OP.profile() == "friends" else "This is the developer's own copy: updates from the source repository are not signed and are marked as not verified."))
        prof.setWordWrap(True); prof.setStyleSheet("color:#555;"); lay.addWidget(prof)
        line = QFrame(); line.setFrameShape(QFrame.HLine); lay.addWidget(line)
        row = QHBoxLayout(); self.b_diag = QPushButton("Create a diagnostic file…"); self.b_diag.setToolTip("A file for a problem report: versions, settings and recent messages with names, folders and keys removed. "
                                                                                                         "It is written to a place you choose and is not sent anywhere.")
        self.b_diag.clicked.connect(self.make_diagnostics); row.addWidget(self.b_diag)
        self.b_learn = QPushButton("Learning history…"); self.b_learn.clicked.connect(self.open_learning); row.addWidget(self.b_learn); row.addStretch(1); lay.addLayout(row)
        self.note = QLabel(""); self.note.setWordWrap(True); lay.addWidget(self.note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

    def chosen_level(self):
        return next((k for k, r in self.radios.items() if r.isChecked()), OP.level())

    def accept(self):
        changed = OP.set_level(self.chosen_level())
        for key, c in self.checks.items(): changed = OP.set_channel(key, c.isChecked()) or changed
        if self.ws is not None and hasattr(self.ws, "set_status"):
            self.ws.set_status("Privacy: " + OP.describe() + ("." if not changed else ". Earlier assistant context was cleared, so nothing collected under the old setting is sent later."))
        if self.ws is not None and hasattr(self.ws, "refresh_privacy_badge"): self.ws.refresh_privacy_badge()
        super().accept()

    def make_diagnostics(self, path=None):
        """Write the sanitized diagnostic file. Nothing is uploaded. Returns the path or None."""
        try: import diagnostics
        except Exception as e:
            self.note.setText(f"The diagnostic file could not be made ({e})."); return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save the diagnostic file", "origin_plot_studio_diagnostics.zip", "Zip (*.zip)")
        if not path: return None
        try:
            out = diagnostics.build_bundle(path)
            self.note.setText(f"Diagnostic file written: {out or path}. Open it and read MANIFEST.txt before you send it to anyone."); return out or path
        except Exception as e:
            self.note.setText(f"The diagnostic file could not be made ({OP.redact(str(e))})."); return None

    def open_learning(self):
        try:
            import workspace_learning as WL
            WL.open_history(self.ws, parent=self)
        except Exception as e:
            self.note.setText(f"Learning history could not be opened ({e}).")


def open_dialog(ws):
    d = PrivacyDialog(ws); d.exec(); return d


def badge_text():
    """A few words for the status bar / header: the present level."""
    return {"local_only": "Local-only", "minimal": "AI: minimal", "metadata": "AI: metadata", "scientific": "AI: scientific content"}[OP.level()]
