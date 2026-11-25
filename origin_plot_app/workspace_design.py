"""Compact adaptive desktop header and a light scientific workbench design."""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QMenu, QPushButton, QWidget

STYLE = '''
#header { background: white; border-bottom: 1px solid #dce4ef; }
#header QLabel#brand { color: #10264a; font-size: 12pt; font-weight: 700; }
#header QPushButton#navtab { color: #526277; background: transparent; border: 0; border-radius: 0; padding: 9px 10px; font-weight: 600; }
#header QPushButton#navtab:checked { color: #125bd5; border-bottom: 3px solid #1766df; background: #f4f8ff; }
#header QPushButton#navtab:hover { color: #125bd5; background: #eef5ff; }
#header QPushButton#menu { color: #263951; background: white; border: 1px solid #d7e1ed; padding: 5px 9px; }
#header QLineEdit { color: #263951; background: #f5f8fc; border: 1px solid #d7e1ed; }
QWidget#startPage, QWidget#workbookPage { background: #f3f6fb; }
QLabel#pageTitle { font-size: 23pt; font-weight: 700; color: #10264a; }
QLabel#sectionTitle { font-size: 14pt; font-weight: 700; color: #182d4b; padding-bottom: 3px; }
QLabel#detectionBadge { background: #eaf2ff; border: 1px solid #d4e5ff; color: #1456bb; font-weight: 600; border-radius: 7px; padding: 9px; }
QPushButton#dropZone { border: 1px dashed #9eb7d8; background: #f7faff; color: #1b5db6; border-radius: 9px; }
QTreeWidget { background: white; border: 0; outline: none; }
QTreeWidget::item { padding: 9px 3px; border-radius: 6px; }
QTreeWidget::item:selected { background: #eaf2ff; color: #123e81; }
QTreeWidget::item:hover { background: #f3f7fd; }
#startPage QListWidget { background: white; }
#startPage QListWidget::item { border: 1px solid #dce5f1; border-radius: 8px; padding: 9px; }
#startPage QListWidget::item:selected { background: #edf5ff; border: 1px solid #2878e8; color: #12366a; }
#startPage QListWidget::item:disabled { color: #7d8a9d; background: #f7f9fc; }
QTableView, QTableWidget { background: white; alternate-background-color: #f6f9fd; gridline-color: #e5ebf3; border: 1px solid #dce5ef; selection-background-color: #dceaff; selection-color: #12366a; }
QHeaderView::section { background: #ecf2fa; border: 0; border-right: 1px solid #dce5ef; border-bottom: 1px solid #dce5ef; color: #243d5e; padding: 7px; font-weight: 600; }
QScrollArea { background: transparent; border: 0; }
QSplitter::handle { background: transparent; width: 9px; }
QSplitter::handle:hover { background: #dceaff; }
'''


class AdaptiveHeader(QObject):
    def __init__(self,w,brand,search,quick):
        super().__init__(w); self.w=w; self.brand=brand; self.search=search; self.quick=quick
        w.installEventFilter(self); self.update()
    def update(self):
        width=QWidget.width(self.w); self.brand.setVisible(width>=1270)
        self.search.setVisible(width>=1450)
        for q in self.quick: q.setVisible(width>=1120)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Resize: self.update()
        return False


def install_header(w,controller):
    layout=w.topbar_layout; widgets=[]
    while layout.count():
        item=layout.takeAt(0)
        if item.widget(): widgets.append(item.widget()); item.widget().hide()
    brand=next((x for x in widgets if x.objectName()=='brand'),QLabel('Origin Plot Studio',objectName='brand'))
    logo=next((x for x in widgets if isinstance(x,QLabel) and x is not brand),None)
    if logo: layout.addWidget(logo); logo.show()
    layout.addWidget(brand); brand.show(); layout.addSpacing(8)
    layout.addWidget(w.file_btn); w.file_btn.show()
    for quick in w.quick: layout.addWidget(quick); quick.show()
    if w.quick: w.quick[0].setToolTip('Save project (Ctrl+S): files, folders, data edits and graph settings')
    layout.addSpacing(9)
    for index in [6,7,0,1]:
        button=w.header_nav.button(index)
        if button is None:
            button=QPushButton('Workbook',objectName='navtab'); button.setCheckable(True)
            button.clicked.connect(lambda _=False:w.go(7)); w.header_nav.addButton(button,7)
        button.setCursor(Qt.PointingHandCursor); layout.addWidget(button); button.show()
    layout.addStretch(1)
    if hasattr(w,'cmd'):
        w.cmd.setMaximumWidth(200); w.cmd.setMinimumWidth(130); w.cmd.setStyleSheet('')
        w.cmd.setPlaceholderText('Search commands…'); w.cmd.setToolTip('Search commands (Ctrl+Q)')
        layout.addWidget(w.cmd)
        from PySide6.QtGui import QColor,QPalette
        palette=w.cmd.palette(); palette.setColor(QPalette.PlaceholderText,QColor('#75869b')); w.cmd.setPalette(palette)
    # Graph search belongs beside the graph list, rather than beside command search.
    if getattr(w,'graphs_dock',None) is not None:
        container=w.graphs_dock.widget(); lay=container.layout()
        if lay: lay.insertWidget(0,w.search); w.search.show()
    assistant=QPushButton('Assistant',objectName='menu'); assistant.setCheckable(True)
    assistant.setChecked(w.dock.isVisible()); assistant.setToolTip('Show or hide the Assistant panel')
    assistant.clicked.connect(lambda on:w.dock.setVisible(on)); w.dock.visibilityChanged.connect(assistant.setChecked)
    layout.addWidget(assistant); w.assistant_toggle=assistant
    settings=w.header_nav.button(4)
    if settings: settings.setObjectName('menu'); layout.addWidget(settings); settings.show()
    overflow=QPushButton('•••',objectName='menu'); overflow.setFixedWidth(42); menu=QMenu(overflow)
    for title,source in [('View',w.panels_btn),('Tools',w.tools_btn),('Help',w.help_btn)]:
        submenu=menu.addMenu(title)
        for action in source.menu().actions(): submenu.addAction(action)
    def show_command_search():
        if w.cmd.isVisible(): w.cmd.refresh(); w.cmd.setFocus(); w.cmd.selectAll(); return
        text,ok=QInputDialog.getItem(w,'Search commands','Command:',sorted(w.commands()),editable=True)
        if ok and text.strip(): w.run_command(text)
    for action in w.actions():
        if action.shortcut().toString()=='Ctrl+Q':
            action.triggered.disconnect(); action.triggered.connect(show_command_search)
    menu.addSeparator(); menu.addAction('Search commands (Ctrl+Q)',show_command_search)
    menu.addAction('Save project',lambda:w.save()); menu.addAction('Undo',lambda:w.undo_any()); menu.addAction('Redo',lambda:w.redo_any())
    overflow.setMenu(menu); overflow.setToolTip('View, Tools, Help and additional commands'); layout.addWidget(overflow)
    hidden_assistant = w.header_nav.button(3)
    if hidden_assistant is not None: w.header_nav.removeButton(hidden_assistant)
    ordered = [(index,w.header_nav.button(index)) for index in (6,7,0,1,4)]
    for index,button in ordered:
        if button is not None: w.header_nav.removeButton(button)
    for index,button in ordered:
        if button is not None: w.header_nav.addButton(button,index)
    w._adaptive_header=AdaptiveHeader(w,brand,getattr(w,'cmd',overflow),w.quick)
    w.pages.currentChanged.connect(lambda index:(w.header_nav.button(7).setChecked(True) if index==7 else None))
    # File > New project now means the same named project as Start Here.
    sh=w.pages.widget(6)
    for action in w.file_btn.menu().actions():
        if action.text().split('\t')[0].strip().startswith('Add data files'):
            action.triggered.disconnect(); action.triggered.connect(sh.add_files)
        if action.text().split('\t')[0].strip() == 'Save': action.setText('Save project\tCtrl+S')
        if action.text().split('\t')[0].strip()=='New project':
            action.triggered.disconnect(); action.triggered.connect(sh.new_project)
    w._assistant_toggle=assistant
