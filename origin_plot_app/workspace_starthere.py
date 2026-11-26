"""Project-first opening screen: Projects / Inspect data / Choose a graph.

Recommendations always come from the live Analysis catalogue. Selection, column
mapping and graph creation are delegated to the shared workbench controller.
"""
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame,
 QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
 QMessageBox, QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem,
 QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import workspace_projects as WP

DATA_FILTER = ('Data files (*.xlsx *.xlsm *.xls *.csv *.tsv *.txt *.dat *.xy *.xye *.asc '
               '*.xrdml *.brml *.uxd *.ras *.spa *.ngb-ds3 *.ngb-ss3);;All files (*)')
DATA_EXTS = {'.xlsx','.xlsm','.xls','.csv','.tsv','.txt','.dat','.xy','.xye','.asc',
             '.xrdml','.brml','.uxd','.ras','.spa','.ngb-ds3','.ngb-ss3'}


class ProjectTree(QTreeWidget):
    def __init__(self, page):
        super().__init__(); self.page = page
        self.setHeaderHidden(True); self.setColumnCount(1)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove); self.setDefaultDropAction(Qt.MoveAction)
        self.setIndentation(18); self.setUniformRowHeights(False)
    def drawBranches(self, painter, rect, index):
        # The space in front of a row (its indent) is painted by the style on its own: for the highlighted row that gave
        # a separate little box with corner marks beside the highlight. Here it is one bar: the same colour, then only
        # the open / close arrow of a project or folder.
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor
        from PySide6.QtGui import QPolygonF, QPen
        from PySide6.QtCore import QPointF
        if self.selectionModel().isSelected(index): painter.fillRect(rect, QColor('#eaf2ff'))
        item = self.itemFromIndex(index)
        if item is not None and item.childCount():
            cx = rect.right() - self.indentation() / 2 + 1; cy = rect.center().y() + .5; r = 4.0
            tri = [QPointF(cx - r, cy - r / 2), QPointF(cx + r, cy - r / 2), QPointF(cx, cy + r / 2 + 1)] if item.isExpanded() else [QPointF(cx - r / 2, cy - r), QPointF(cx - r / 2, cy + r), QPointF(cx + r / 2 + 1, cy)]
            painter.save(); painter.setRenderHint(painter.RenderHint.Antialiasing); painter.setPen(Qt.NoPen); painter.setBrush(QColor('#5b6b82'))
            painter.drawPolygon(QPolygonF(tri)); painter.restore()

    # A click anywhere on a row ticks it, a second click unticks it - as in the file lists of Analysis. The small box
    # still works by itself; the arrow in front of a project or folder only opens and closes it.
    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        self._pressed = (item, item.checkState(0), event.position().toPoint()) if item is not None else None
        super().mousePressEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        pressed = getattr(self, '_pressed', None); self._pressed = None
        pos = event.position().toPoint(); item = self.itemAt(pos)
        if (event.button() != Qt.LeftButton or pressed is None or item is None or item is not pressed[0]
                or event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
                or (pos - pressed[2]).manhattanLength() > 6                  # that was a drag (moving it into a folder), not a click
                or pos.x() < self.visualItemRect(item).left()                # the arrow in front of the row
                or item.checkState(0) != pressed[1]): return                 # the box itself was clicked: it has already changed
        item.setCheckState(0, Qt.Unchecked if item.checkState(0) == Qt.Checked else Qt.Checked)
    def dropEvent(self, event):
        target = self.itemAt(event.position().toPoint())
        data = target.data(0, Qt.UserRole) if target else None
        if self.page.move_selected(data): event.accept()
        else: event.ignore()


class StartHerePage(QWidget):
    label = 'Start here'

    def __init__(self, ws):
        super().__init__(); self.ws = ws; self._building = False; self._selection_order = []
        self._current_path = None; self._current_project = None; self._open_queue = []
        self.setObjectName('startPage'); self.setAcceptDrops(True)
        self._inspect_timer = QTimer(self); self._inspect_timer.setSingleShot(True)
        self._inspect_timer.setInterval(100); self._inspect_timer.timeout.connect(self.inspect_current)
        outer = QVBoxLayout(self); outer.setContentsMargins(22, 20, 22, 18); outer.setSpacing(16)
        heading = QHBoxLayout(); title = QVBoxLayout(); title.setSpacing(3)
        title.addWidget(QLabel('Start Here', objectName='pageTitle'))
        title.addWidget(QLabel('Open a project, inspect your data, and create a graph.', objectName='soft'))
        heading.addLayout(title, 1)
        self.p_new = self._button('+  New project', self.new_project, 'primary')
        heading.addWidget(self.p_new)
        heading.addWidget(self._button('Open project…', self.import_project))
        outer.addLayout(heading)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.setChildrenCollapsible(False)
        outer.addWidget(self.splitter, 1)
        self._projects_panel(); self._inspect_panel(); self._recommend_panel()
        self.splitter.setSizes([350, 510, 410]); self.splitter.setStretchFactor(1, 2)
        foot = QHBoxLayout(); self.summary = QLabel('Create a project or add files to begin.', objectName='soft')
        foot.addWidget(self.summary, 1)
        self.b_workspace = self._button('Open Workspace', self.open_workspace); foot.addWidget(self.b_workspace)
        outer.addLayout(foot)
        self.refresh(); self._sync_create()

    def _button(self, text, fn, name=None):
        b = QPushButton(text); b.setCursor(Qt.PointingHandCursor)
        if name: b.setObjectName(name)
        b.clicked.connect(lambda _checked=False: fn()); return b

    def _card(self, title):
        card = QFrame(objectName='card'); card.setMinimumWidth(280)
        lay = QVBoxLayout(card); lay.setContentsMargins(18, 17, 18, 17); lay.setSpacing(12)
        lay.addWidget(QLabel(title, objectName='sectionTitle')); return card, lay

    def _scroll_card(self, card):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumWidth(280); scroll.setWidget(card); self.splitter.addWidget(scroll)

    def _projects_panel(self):
        card, lay = self._card('Projects')
        row = QHBoxLayout(); self.project_search = QLineEdit(placeholderText='Search projects and files…')
        self.project_search.setClearButtonEnabled(True); self.project_search.textChanged.connect(self.filter_projects)
        row.addWidget(self.project_search, 1)
        refresh = self._button('↻', self.refresh_from_disk); refresh.setFixedWidth(38); refresh.setToolTip('Refresh projects and recheck files')
        row.addWidget(refresh); lay.addLayout(row)
        row = QHBoxLayout()
        self.p_add = self._button('Add files', self.add_files); row.addWidget(self.p_add)
        self.p_add_folder = self._button('Add folder…', self.add_disk_folder); row.addWidget(self.p_add_folder)
        more = QPushButton('•••'); more.setFixedWidth(38); menu = QMenu(more)
        for name, fn in [('New empty folder…', self.new_folder), ('File details…', self.show_file_details), ('Rename…', self.rename_selected), ('Move to folder…', self.move_dialog),
                         ('Move up', lambda: self.reorder_selected(-1)), ('Move down', lambda: self.reorder_selected(1)),
                         ('Save project', self.save_project), ('Export project…', self.export_project),
                         ('Close project', self.close_project), ('Remove selected…', self.delete_selected)]:
            menu.addAction(name, fn)
        more.setMenu(menu); more.setToolTip('Rename, arrange, save, export, close or remove'); row.addWidget(more)
        lay.addLayout(row)
        self.projects = ProjectTree(self)
        self.projects.setToolTip('Click a project, folder or file to tick it (click again to untick). The ticked ones are what Open selected, Create graph and Workbook work on; the highlighted file is the one shown in Inspect data. Drag a file onto a folder to move it; right click for more')
        self.projects.setContextMenuPolicy(Qt.CustomContextMenu); self.projects.customContextMenuRequested.connect(self._project_menu)
        self.projects.itemChanged.connect(self._tree_checked)
        self.projects.currentItemChanged.connect(self._tree_current)
        self.projects.itemDoubleClicked.connect(lambda *_: self.open_projects())
        self.projects.setMinimumHeight(150); lay.addWidget(self.projects, 1)
        self.project_hint = QLabel('Create a named project to keep files, folders, analyses and graphs together.', objectName='soft')
        self.project_hint.setWordWrap(True); lay.addWidget(self.project_hint)
        self.selection_label = QLabel('Nothing selected', objectName='soft'); lay.addWidget(self.selection_label)
        self.p_open = self._button('Open selected', self.open_projects, 'primary'); lay.addWidget(self.p_open)
        row = QHBoxLayout()
        row.addWidget(self._button('Save', self.save_project)); row.addWidget(self._button('Close', self.close_project))
        row.addWidget(self._button('Remove', self.delete_selected)); lay.addLayout(row)
        QShortcut(QKeySequence(Qt.Key_Delete), self.projects, activated=self.delete_selected).setContext(Qt.WidgetWithChildrenShortcut)
        self.splitter.addWidget(card)

    def _inspect_panel(self):
        card, lay = self._card('Inspect data')
        lay.setSpacing(8)
        self.breadcrumb = QLabel('No file selected', objectName='soft'); self.breadcrumb.setWordWrap(True); lay.addWidget(self.breadcrumb)
        self.add_btn = self._button('Drop files or a folder here, or  + Add files', self.add_files)
        self.add_btn.setObjectName('dropZone'); self.add_btn.setMinimumHeight(56)
        self.add_btn.setToolTip('Add files – Drop data files or a whole folder here, or click to choose files: CSV, TSV, Excel and supported instrument formats. Original files are kept unchanged')
        lay.addWidget(self.add_btn)
        # This compact list exposes session inputs as well as the project tree.
        self.files = QListWidget(); self.files.setMaximumHeight(82)
        self.files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files.itemSelectionChanged.connect(self._session_selected)
        self.files.setContextMenuPolicy(Qt.CustomContextMenu); self.files.customContextMenuRequested.connect(self._file_menu)
        lay.addWidget(self.files)
        self.detect = QLabel('Add a file to inspect its data.', objectName='detectionBadge'); self.detect.setWordWrap(True); lay.addWidget(self.detect)
        self.evidence = QLabel('', objectName='soft'); self.evidence.setWordWrap(True); lay.addWidget(self.evidence)
        row = QHBoxLayout(); self.type_combo = QComboBox()
        from opstudio.detection import KINDS
        self.type_combo.addItems(['Automatic'] + KINDS); self.type_combo.setToolTip('Confirm or correct the scientific measurement type')
        self.type_combo.activated.connect(self.mapping_changed)
        row.addWidget(QLabel('Data type')); row.addWidget(self.type_combo, 1)
        self.confirm_btn = self._button('Confirm type', self.confirm_type); row.addWidget(self.confirm_btn); lay.addLayout(row)
        self.sheet = QComboBox(); self.sheet.activated.connect(self.mapping_changed)
        lay.addWidget(self.sheet)
        row = QHBoxLayout(); self.x_combo = QComboBox(); self.y_combo = QComboBox()
        self.x_combo.activated.connect(self.mapping_changed); self.y_combo.activated.connect(self.mapping_changed)
        row.addWidget(QLabel('X')); row.addWidget(self.x_combo, 1); row.addWidget(QLabel('Y')); row.addWidget(self.y_combo, 1); lay.addLayout(row)
        self.data_preview = QTableWidget(); self.data_preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_preview.setMaximumHeight(125); self.data_preview.setAlternatingRowColors(True)
        self.data_preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); lay.addWidget(self.data_preview)
        # dpi=100: the app's own figures are 200 dpi (print); on screen that draws this preview at twice its size
        self.fig = Figure(figsize=(5, 2.8), dpi=100, layout='constrained'); self.preview = FigureCanvasQTAgg(self.fig)
        self.preview.setMinimumHeight(175); lay.addWidget(self.preview, 1)
        lay.addWidget(self._button('Edit and arrange in Workbook', self.open_workbook))
        self._scroll_card(card)

    def _recommend_panel(self):
        card, lay = self._card('Choose a graph')
        self.rec_caption = QLabel('Recommendations from Analysis templates appear after data inspection.', objectName='soft')
        self.rec_caption.setWordWrap(True); lay.addWidget(self.rec_caption)
        self.recs = QListWidget(); self.recs.setIconSize(QSize(135, 82)); self.recs.setSpacing(7)
        self.recs.setWordWrap(True); self.recs.setMinimumHeight(200)
        self.recs.currentRowChanged.connect(lambda *_: self._sync_create())
        self.recs.itemDoubleClicked.connect(lambda *_: self.draw_recommended()); lay.addWidget(self.recs, 1)
        self.combine_mode = QComboBox(); self.combine_mode.addItems(['Separate graph for each file', 'Combine selected files in one graph'])
        # a change made here is your own choice for these files: the app does not change it again (its own changes are made with the signals blocked)
        self.combine_mode.currentIndexChanged.connect(lambda *_: (setattr(self, '_mode_user', True), self.inspect_current())); lay.addWidget(self.combine_mode)
        self.combine_mode.setToolTip('One graph per ticked file, or the ticked files together in one graph. Files that look like one series '
                                     '(the same kind of data, names built the same way) are put together by the app; choose here to have them apart')
        self._mode_for = None; self._mode_user = False; self._auto_combined = False; self._rec_paths = []
        self.b_browse = self._button('Browse Analysis templates →', self.browse_templates); lay.addWidget(self.b_browse)
        self.b_auto = self._button('Create graph →', self.draw_recommended, 'primary'); lay.addWidget(self.b_auto)
        lab = QLabel('Opens in Workspace for editing. Send to Origin when ready.', objectName='soft'); lab.setWordWrap(True); lay.addWidget(lab)
        self.splitter.addWidget(card)
        # Compatibility aliases for integrations that inspected the previous page.
        self.rec_list = self.recs; self.rec_lay = self.recs.layout()

    def _walk(self):
        def walk(item):
            yield item
            for n in range(item.childCount()): yield from walk(item.child(n))
        for n in range(self.projects.topLevelItemCount()): yield from walk(self.projects.topLevelItem(n))

    def refresh_projects(self):
        current = self.projects.currentItem()
        cur = current.data(0, Qt.UserRole) if current else None
        checked = {tuple(i.data(0, Qt.UserRole)) for i in self._walk() if i.checkState(0) == Qt.Checked}
        expanded = {tuple(i.data(0, Qt.UserRole)) for i in self._walk() if i.isExpanded()}
        self._building = True; self.projects.clear(); current_item = None
        loose = self.loose_files()                             # files of the session that are in no project: listed here like the rest, so a file you add is where you look for it
        if loose:
            root = QTreeWidgetItem([f"Files not in a project\n{len(loose)} file{'s' if len(loose) != 1 else ''} · this session"])
            root.setToolTip(0, "Files you added without a project. They work like any other; 'New project' (or dragging them onto a project) keeps them, their edits and their graphs together")
            self.projects.addTopLevelItem(root); self._setup_node(root, ('session', '', ''), checked)
            root.setFlags(root.flags() & ~Qt.ItemIsDragEnabled)
            for f in loose:
                item = QTreeWidgetItem(root, [os.path.basename(f) + ('  · missing' if not os.path.isfile(f) else '')])
                item.setToolTip(0, f + '\nNot in a project'); self._setup_node(item, ('file', '', f), checked)
            root.setExpanded(not expanded or ('session', '', '') in expanded)
        for slug, p in WP.list_projects():
            modified = datetime.fromtimestamp(p.get('modified', 0)).strftime('%d %b %Y, %H:%M')
            count = len(p['files']); missing = len(WP.missing_files(slug))
            state = 'Unsaved' if slug in getattr(getattr(self.ws,'workbench',None),'_changed',set()) else 'Saved'
            root = QTreeWidgetItem([f"{p['name']}\n{count} file{'s' if count != 1 else ''} · {state} · {modified}" + (f' · {missing} missing' if missing else '')])
            root.setToolTip(0, f"{p['name']}\nLast saved: {modified}\n{count} input files")
            self.projects.addTopLevelItem(root); nodes = {'': root}
            folders = list(p['folders'])
            while folders:
                remaining = []
                for folder in folders:
                    parent = nodes.get(folder.get('parent', ''))
                    if parent is None: remaining.append(folder); continue
                    item = QTreeWidgetItem(parent, ['📁  ' + folder['name']]); nodes[folder['id']] = item
                    self._setup_node(item, ('folder', slug, folder['id']), checked)
                if len(remaining) == len(folders): break
                folders = remaining
            self._setup_node(root, ('project', slug, ''), checked)
            for f in p['files']:
                parent = nodes.get(p['locations'].get(f, ''), root)
                item = QTreeWidgetItem(parent, [os.path.basename(f) + ('  · missing' if not os.path.isfile(f) else '')])
                details = [f, 'Format: ' + Path(f).suffix.lstrip('.').upper(), 'Project: ' + p['name']]
                ctrl = getattr(self.ws, 'workbench', None)
                if ctrl and (slug, f) in ctrl.working:
                    try:
                        table = ctrl.table_for(f, slug)
                        from opstudio.detection import detect
                        result = detect(table, getattr(table, 'measurement_type', None))
                        details += ['Detected type: ' + result.kind, f'{len(table.df):,} rows · {len(table.cols)} columns', 'Status: Ready']
                    except Exception as e: details.append('Status: ' + str(e))
                elif not os.path.isfile(f): details.append('Status: Missing — locate or remove this input')
                else: details.append('Status: Select to inspect')
                item.setToolTip(0, '\n'.join(details)); self._setup_node(item, ('file', slug, f), checked)
            for item in [root] + [n for k, n in nodes.items() if k]:
                item.setExpanded(not expanded or tuple(item.data(0, Qt.UserRole)) in expanded)
        for item in self._walk():
            if item.data(0, Qt.UserRole) == cur: current_item = item; break
        if current_item: self.projects.setCurrentItem(current_item)
        self.project_hint.setVisible(self.projects.topLevelItemCount() == 0)     # the explanation is for the empty list; with projects it only takes their room on a small screen
        self._building = False; self._sync_project_buttons(); self.filter_projects(self.project_search.text())

    def loose_files(self):
        """The files of the session (Workspace / Analysis) that belong to no open project."""
        tp = getattr(self.ws, 'templates_page', None); ctrl = getattr(self.ws, 'workbench', None)
        if tp is None or not hasattr(tp, 'files'): return []
        paths = [tp.files.item(i).data(Qt.UserRole) for i in range(tp.files.count())]
        owned = {getattr(i, 'path', '') for i in getattr(self.ws, 'singles', []) if getattr(i, 'project_id', None)}
        in_open = set()
        if ctrl:
            for slug in ctrl.open_projects | ({ctrl.active_project} if ctrl.active_project else set()):
                in_open |= set((WP.get(slug) or {}).get('files', []))
        return [p for p in paths if p not in owned and p not in in_open]

    def _setup_node(self, item, value, checked):
        item.setData(0, Qt.UserRole, value)
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
        if value[0] != 'file': flags |= Qt.ItemIsDropEnabled
        item.setFlags(flags); item.setCheckState(0, Qt.Checked if tuple(value) in checked else Qt.Unchecked)

    def _tree_checked(self, item, col):
        if self._building: return
        value = tuple(item.data(0, Qt.UserRole)); on = item.checkState(0) == Qt.Checked
        if on and value not in self._selection_order: self._selection_order.append(value)
        if not on: self._selection_order = [v for v in self._selection_order if v != value]
        self._sync_project_buttons(); self._inspect_timer.start()

    def _tree_current(self, item, previous):
        if self._building or item is None: return
        kind, slug, value = item.data(0, Qt.UserRole)
        self._current_project = slug or None
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.active_project = slug or None
        if kind == 'file': self._current_path = value
        else:
            paths = self.loose_files() if kind == 'session' else WP.folder_files(slug, value) if kind == 'folder' else (WP.get(slug) or {}).get('files', [])
            self._current_path = next((p for p in paths if os.path.isfile(p)), None)
        self._sync_project_buttons(); self._inspect_timer.start()

    def selected_entries(self):
        checked = [tuple(i.data(0, Qt.UserRole)) for i in self._walk() if i.checkState(0) == Qt.Checked]
        ordered = [v for v in self._selection_order if v in checked]
        ordered += [v for v in checked if v not in ordered]
        if not ordered:
            ordered = [tuple(i.data(0, Qt.UserRole)) for i in self.projects.selectedItems()]
        return ordered

    def selected_inputs(self):
        result = []
        for kind, slug, value in self.selected_entries():
            p = WP.get(slug) or {}
            paths = [value] if kind == 'file' else self.loose_files() if kind == 'session' else WP.folder_files(slug, value) if kind == 'folder' else p.get('files', [])
            for path in paths:
                pair = (slug or None, path)                      # a file in no project: no project id, as its graphs have none
                if pair not in result: result.append(pair)
        return result

    def _ticked_projects(self):
        return list(dict.fromkeys(v[1] for v in self.selected_entries() if v[1]))

    def _sync_project_buttons(self):
        if not hasattr(self, 'p_open'): return
        inputs = self.selected_inputs(); n = len(inputs); projects = self._ticked_projects()
        self.p_open.setEnabled(n > 0); self.p_open.setToolTip('Open selected files and folders' if n else 'Select a project, folder or file first')
        self.p_add.setEnabled(True)
        self.p_add.setToolTip('Add files – Add data files to the selected project (or folder). With no project selected they are simply added to the session')
        self.selection_label.setText(f"{len(projects)} project(s) · {n} file(s) selected" if n else 'Select projects, folders or files')
        if hasattr(self, 'summary'):
            self.summary.setText(f'{len(projects)} project(s) · {n} selected input(s)' if n else 'Create a project or select files to begin.')

    def filter_projects(self, text):
        query = text.casefold().strip()
        def show(item):
            children = [show(item.child(i)) for i in range(item.childCount())]
            own = not query or query in item.text(0).casefold()
            item.setHidden(not (own or any(children)))
            if own:
                for i in range(item.childCount()): item.child(i).setHidden(False)
            return own or any(children)
        for i in range(self.projects.topLevelItemCount()): show(self.projects.topLevelItem(i))

    def new_project(self):
        name, ok = QInputDialog.getText(self, 'New project', 'Project name:')
        if not ok or not name.strip(): return None
        slug = WP.create(name); self._current_project = slug
        if hasattr(self.ws, 'workbench'): self.ws.workbench.active_project = slug
        self.refresh_projects(); self._select_node(('project', slug, ''))
        self.ws.set_status(f"Project '{name.strip()}' created. Add files or create folders."); return slug

    def _select_node(self, value):
        for i in self._walk():
            if tuple(i.data(0, Qt.UserRole)) == tuple(value):
                self.projects.setCurrentItem(i); i.setSelected(True); self.projects.scrollToItem(i); return i

    def _destination(self):
        item = self.projects.currentItem(); value = item.data(0, Qt.UserRole) if item else None
        slug = value[1] if value else self._current_project
        if not slug or not WP.get(slug): slug = self.new_project()
        folder = value[2] if value and value[0] == 'folder' and value[1] == slug else ''
        return slug, folder

    def add_files(self, paths=None):
        # Into the project (or folder) selected on the left. With no project selected the files are simply added to the
        # session, as the app has always done: a project is offered ('New project'), never required to look at a file.
        item = self.projects.currentItem(); value = item.data(0, Qt.UserRole) if item else None
        slug = value[1] if value else self._current_project
        if slug and not WP.get(slug): slug = None
        folder = value[2] if slug and value and value[0] == 'folder' and value[1] == slug else ''
        if paths is None: paths, _ = QFileDialog.getOpenFileNames(self, 'Add data files', '', DATA_FILTER)
        paths = list(dict.fromkeys(os.path.abspath(p) for p in paths or [] if os.path.isfile(p)))
        if not paths: return
        if not slug:
            self._current_project = None; self._current_path = paths[0]
            self.ws.templates_page.add_files(paths, on_done=lambda items: self._import_done(None, paths, items))
            self._show_loose(paths)                                # they are listed at once, under 'Files not in a project'
            self.ws.set_status(f'Importing {len(paths)} file(s)… (not in a project: New project keeps files, edits and graphs together)'); return
        WP.add_files(slug, paths, folder); self._current_project = slug; self._current_path = paths[0]
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.active_project = slug
        self.refresh_projects()
        for p in paths:
            node = self._select_node(('file', slug, p))
            if node: node.setCheckState(0, Qt.Checked)
        self.ws.templates_page.add_files(paths, project=(WP.get(slug) or {})['name'],
            on_done=lambda items: self._import_done(slug, paths, items))
        self.ws.set_status(f'Importing {len(paths)} file(s)…')

    def add_to_project(self): self.add_files()

    def _show_loose(self, paths):
        """Files just added without a project: listed, ticked, and the first of them highlighted (it is the one on show)."""
        self.refresh_projects()
        for p in paths:
            node = self._select_node(('file', '', p))
            if node: node.setCheckState(0, Qt.Checked)
        first = self._select_node(('file', '', paths[0]))
        if first is not None:
            self.projects.clearSelection(); first.setSelected(True)

    def add_disk_folder(self, directory=None):
        """'Add folder…' (or a folder dropped on the page): every data file in a folder of the disk, its sub-folders
        included, comes in under a folder of the same name, with its sub-folders as folders inside it. Into the
        project (or folder) selected on the left; with no project selected, a project named after the folder is made
        for it. The files stay where they are on the disk and are only read."""
        if directory is None: directory = QFileDialog.getExistingDirectory(self, 'Add a folder of data files', '')
        if not directory or not os.path.isdir(directory): return None
        root = Path(os.path.abspath(directory))
        def wanted(f):
            rel = f.relative_to(root).parts
            return f.is_file() and f.suffix.lower() in DATA_EXTS and not f.name.startswith(('~$', '.')) and not any(part.startswith('.') for part in rel[:-1])
        try: files = sorted((f for f in root.rglob('*') if wanted(f)), key=lambda f: (len(f.relative_to(root).parts), str(f).lower()))
        except OSError as e: self.ws.set_status(f'This folder could not be read: {e}'); return None
        if not files:
            self.ws.set_status(f"No data files in '{root.name}' (Excel, CSV, text and instrument files are read; sub-folders are looked in too)."); return None
        if len(files) > 150 and QMessageBox.question(self, 'Add folder', f"'{root.name}' holds {len(files)} data files. Add all of them? They are read in the background.") != QMessageBox.Yes: return None
        item = self.projects.currentItem(); value = item.data(0, Qt.UserRole) if item else None
        slug = value[1] if value else self._current_project
        if slug and not WP.get(slug): slug = None
        parent = value[2] if slug and value and value[0] == 'folder' and value[1] == slug else ''
        made_project = not slug
        if made_project: slug = WP.create(root.name)
        def folder_id(name, parent_id):                             # the folder of this name here: the one there is, or a new one
            existing = next((f['id'] for f in WP.get(slug)['folders'] if f['name'].casefold() == name.casefold() and f.get('parent', '') == parent_id), None)
            return existing or WP.add_folder(slug, name, parent_id)
        ids = {(): parent if made_project else folder_id(root.name, parent)}      # a project made for the folder already carries its name: its files go straight into it
        by_folder = {}
        for f in files:
            parts = f.relative_to(root).parts[:-1]
            for depth in range(1, len(parts) + 1):
                if parts[:depth] not in ids: ids[parts[:depth]] = folder_id(parts[depth - 1], ids[parts[:depth - 1]])
            by_folder.setdefault(parts, []).append(str(f))
        paths = []
        for parts, group in by_folder.items(): WP.add_files(slug, group, ids[parts]); paths += group
        self._current_project = slug; self._current_path = paths[0]
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.active_project = slug
        self.refresh_projects()
        node = self._select_node(('project', slug, '') if made_project else ('folder', slug, ids[()]))
        if node: node.setCheckState(0, Qt.Checked); node.setExpanded(True)
        self.ws.templates_page.add_files(paths, project=(WP.get(slug) or {})['name'], on_done=lambda items: self._import_done(slug, paths, items))
        self.ws.set_status(f"Importing {len(paths)} file(s) from '{root.name}'" + (f" into a new project '{WP.get(slug)['name']}'" if made_project else '') + '…')
        return slug

    def _import_done(self, slug, paths, items):
        if slug and hasattr(self.ws, "workbench"):
            self.ws.workbench.open_projects.add(slug)
            self.ws.workbench._changed.add(slug)
        for it in items:
            if slug: it.project_id = slug
        present = {os.path.abspath(str(getattr(it, 'path', ''))) for it in self.ws.singles}
        bad = [p for p in paths if p not in present]
        self.ws.set_status(f"Imported {len(paths)-len(bad)} of {len(paths)} file(s)." +
                           (' Could not plot: ' + ', '.join(os.path.basename(p) for p in bad) + '. Inspect the file or see Details.' if bad else ''))
        self.refresh(); self.inspect_current()
        if not slug: self._show_loose([p for p in paths if p in self.loose_files()] or paths)
        if items and items[0] in self.ws.items:
            self.ws._tick_only(items); self.ws.list.setCurrentRow(self.ws.items.index(items[0]))

    def open_projects(self):
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: return ctrl.open_inputs(self.selected_inputs(), then_workspace=True)       # the graphs are in Workspace: go there when they are read
        self.ws.set_status('The project controller is unavailable. See Details.')

    def open_workspace(self):
        """'Open Workspace': with projects, folders or files selected here, they are opened first (if they are not yet),
        then Workspace is shown with the first of them in front. Nothing selected: just Workspace."""
        ctrl = getattr(self.ws, 'workbench', None); inputs = self.selected_inputs() if ctrl else []
        if not inputs: return self.ws.go(0)
        have = {(getattr(i, 'project_id', None), getattr(i, 'path', '')) for i in self.ws.singles}
        if any(pair not in have for pair in inputs) and not ctrl._opening and self.ws.thread is None:
            return ctrl.open_inputs(inputs, then_workspace=True)
        self.ws.go(0)
        first = next((i for i in self.ws.items if (getattr(i, 'project_id', None), getattr(i, 'path', '')) == inputs[0]), None)
        if first is not None: self.ws.list.setCurrentRow(self.ws.items.index(first))

    def new_folder(self):
        slug, parent = self._destination()
        if not slug: return
        name, ok = QInputDialog.getText(self, 'New folder', 'Folder name:')
        if not ok: return
        try: fid = WP.add_folder(slug, name, parent)
        except ValueError as e: self.ws.set_status(str(e)); return
        self.refresh_projects(); self._select_node(('folder', slug, fid))

    def rename_selected(self):
        item = self.projects.currentItem()
        if item is None: return
        kind, slug, value = item.data(0, Qt.UserRole)
        if kind == 'file': self.ws.set_status('Source filenames are preserved. Rename folders or the project to organise work.'); return
        if kind == 'session': self.ws.set_status("These files are in no project. 'New project' gives them one you can name."); return
        old = WP.get(slug)['name'] if kind == 'project' else next(f['name'] for f in WP.get(slug)['folders'] if f['id'] == value)
        name, ok = QInputDialog.getText(self, 'Rename', 'New name:', text=old)
        if not ok or not name.strip(): return
        if kind == 'project': self._rename_project(slug, name)
        else: WP.rename_folder(slug, value, name); self.refresh_projects()

    def _rename_project(self, slug, name=None):
        if name is None:
            name, ok = QInputDialog.getText(self, 'Rename project', 'New name:', text=WP.get(slug)['name'])
            if not ok: return
        if not name.strip(): return
        old = WP.get(slug)['name']; WP.rename(slug, name)
        for it in self.ws.singles:
            if getattr(it, 'project_id', None) == slug or (getattr(it, 'project_id', None) is None and getattr(it, 'project', None) == old): it.project = name
        self.ws.refresh_list(); self.refresh_projects()

    def move_selected(self, target):
        if not target: return False
        kind, slug, value = target
        if kind == 'file': return False
        parent = value if kind == 'folder' else ''
        items = [tuple(i.data(0, Qt.UserRole)) for i in self.projects.selectedItems()]
        if not items: return False
        try:
            if kind == 'session': raise ValueError('Drop files onto a project or one of its folders')
            for k, s, v in items:
                if k == 'file' and not s:                         # a file that is in no project, dragged onto a project: it joins it, with the graphs it already has
                    WP.add_files(slug, [v], parent); ctrl = getattr(self.ws, 'workbench', None); name = (WP.get(slug) or {}).get('name')
                    for it in self.ws.singles:
                        if getattr(it, 'path', '') == v and not getattr(it, 'project_id', None): it.project_id = slug; it.project = name
                    if ctrl: ctrl.open_projects.add(slug); ctrl._changed.add(slug)
                    self.ws.refresh_list(); continue
                if s != slug: raise ValueError('Move within one project; add a file to another project using Add files')
                if k == 'file': WP.add_files(s, [v], parent)
                elif k == 'folder': WP.move_folder(s, v, parent)
                else: raise ValueError('Select files or folders to move')
        except ValueError as e: self.ws.set_status(str(e)); return False
        self.refresh_projects(); return True

    def move_dialog(self):
        slug = self._current_project
        if not slug: return
        p = WP.get(slug); choices = [('Project root', '')] + [(f['name'], f['id']) for f in p['folders']]
        labels = [f'{n} [{i[:6]}]' if i else n for n, i in choices]
        name, ok = QInputDialog.getItem(self, 'Move selected', 'Destination folder:', labels, editable=False)
        if ok: self.move_selected(('folder', slug, choices[labels.index(name)][1]))

    def reorder_selected(self, delta):
        item = self.projects.currentItem()
        if not item: return
        kind, slug, value = item.data(0, Qt.UserRole); p = WP.get(slug)
        if not p: return                                          # files in no project keep the order they were added in
        keys = list(p['files']) if kind == 'file' else [f['id'] for f in p['folders']] if kind == 'folder' else []
        if value not in keys: return
        idx = keys.index(value); new = idx + delta
        if 0 <= new < len(keys):
            keys[idx], keys[new] = keys[new], keys[idx]
            (WP.reorder if kind == 'file' else WP.reorder_folders)(slug, keys)
            self.refresh_projects(); self._select_node((kind, slug, value))

    def delete_selected(self):
        entries = self.selected_entries()
        if not entries: self.ws.set_status('Select a project, folder or file first.'); return
        if QMessageBox.question(self, 'Remove selected', 'Remove selected items from the project browser?\nOriginal files stay on disk. Removing a folder moves its files to the project root.') != QMessageBox.Yes: return
        deleted = set()
        for kind, slug, value in entries:
            if slug in deleted: continue
            if kind == 'project':
                if hasattr(self.ws, 'workbench'): self.ws.workbench.close_project(slug, save=True)
                WP.delete(slug); deleted.add(slug)
            elif kind == 'folder': WP.remove_folder(slug, value)
            else:
                ctrl = getattr(self.ws, 'workbench', None)
                for path in (self.loose_files() if kind == 'session' else [value]):
                    if slug: WP.remove_file(slug, path)
                    if ctrl: ctrl.remove_input(slug or None, path)
        self.refresh()

    def _delete_project(self, slug, name):
        if QMessageBox.question(self, 'Delete project', f"Delete '{name}'? Original files stay on disk.") == QMessageBox.Yes:
            if hasattr(self.ws, 'workbench'): self.ws.workbench.close_project(slug, save=True)
            WP.delete(slug); self.refresh()

    def _forget_missing(self, slug):
        for p in WP.missing_files(slug): WP.remove_file(slug, p)
        self.refresh_projects()

    def save_project(self):
        if hasattr(self.ws, 'workbench'): self.ws.workbench.save_project(self._current_project)
        self.refresh_projects()

    def close_project(self):
        if hasattr(self.ws, 'workbench'): self.ws.workbench.close_project(self._current_project, save=True)
        self.refresh()

    def _close_project_graphs(self, name):
        slug = next((s for s, p in WP.list_projects() if p['name'] == name), None)
        if slug and hasattr(self.ws, 'workbench'): self.ws.workbench.close_project(slug, save=True)

    def export_project(self):
        if not self._current_project: self.ws.set_status('Select a project to export.'); return
        self.save_project(); p = WP.get(self._current_project)
        path, _ = QFileDialog.getSaveFileName(self, 'Export portable project', p['name'] + '.opsproject', 'Origin Plot Studio project (*.opsproject)')
        if not path: return
        if not path.lower().endswith('.opsproject'): path += '.opsproject'
        try: WP.export_project(self._current_project, path); self.ws.set_status(f'Project exported: {path}')
        except Exception as e: self.ws.set_status(f'Export failed: {e}')

    def import_project(self, path=None):
        if path is None: path, _ = QFileDialog.getOpenFileName(self, 'Open project', '', 'Origin Plot Studio project (*.opsproject);;Saved session (*.json)')
        if not path: return
        try:
            if path.lower().endswith('.json'): self.ws.open_session(path); self.refresh(); return
            slug = WP.import_project(path); self.refresh_projects(); self._select_node(('project', slug, ''))
            self.ws.set_status('Project imported. Select files or Open selected to resume.'); return slug
        except Exception as e: self.ws.set_status(f'Project could not be opened: {e}')

    def _project_menu(self, pos):
        item = self.projects.itemAt(pos)
        if not item: return
        self.projects.setCurrentItem(item); menu = QMenu(self)
        for name, fn in [('Open selected', self.open_projects), ('Add files…', self.add_files), ('Add folder…', self.add_disk_folder), ('New empty folder…', self.new_folder),
                         ('Rename…', self.rename_selected), ('Move to folder…', self.move_dialog), ('Move up', lambda: self.reorder_selected(-1)),
                         ('Move down', lambda: self.reorder_selected(1)), ('Save project', self.save_project), ('Export project…', self.export_project),
                         ('Close project', self.close_project), ('Remove selected…', self.delete_selected)]: menu.addAction(name, fn)
        menu.exec(self.projects.mapToGlobal(pos))

    def _session_selected(self):
        if self._building: return
        items = self.files.selectedItems()
        if items: self._current_path = items[-1].data(Qt.UserRole)
        self._inspect_timer.start()

    def selected_paths(self):
        inputs = self.selected_inputs()
        paths = [p for _, p in inputs if os.path.isfile(p)]
        if not paths: paths = [i.data(Qt.UserRole) for i in self.files.selectedItems()]
        if not paths and self._current_path: paths = [self._current_path]
        return list(dict.fromkeys(paths))

    def remove_selected_files(self):
        paths = [i.data(Qt.UserRole) for i in self.files.selectedItems()]
        if not paths: self.ws.set_status('Click a file or select several files to remove.'); return
        if QMessageBox.question(self, 'Remove files', 'Remove selected files from this project? Original files stay on disk.') != QMessageBox.Yes: return
        for p in paths:
            if self._current_project: WP.remove_file(self._current_project, p)
            if hasattr(self.ws, 'workbench'): self.ws.workbench.remove_input(self._current_project, p)
        self._current_path = None; self.refresh()

    def _file_menu(self, pos):
        if self.files.itemAt(pos):
            m = QMenu(self); m.addAction('Remove selected from project', self.remove_selected_files); m.exec(self.files.mapToGlobal(pos))

    def refresh(self):
        if not hasattr(self, 'files'): return
        self.refresh_projects(); selected = {i.data(Qt.UserRole) for i in self.files.selectedItems()}
        tp = getattr(self.ws, 'templates_page', None); paths = []
        if tp is not None and hasattr(tp, 'files'):
            paths = [tp.files.item(i).data(Qt.UserRole) for i in range(tp.files.count())]
        self._building = True; self.files.clear()
        for p in paths:
            item = QListWidgetItem(os.path.basename(p)); item.setData(Qt.UserRole, p); item.setToolTip(p)
            self.files.addItem(item); item.setSelected(p in selected)
        self._building = False
        self.files.setVisible(False)                           # the files of the session are in the tree on the left ('Files not in a project'); this list is kept for what reads it
        if not self._current_path or not os.path.isfile(self._current_path): self._current_path = next(iter(paths), None)
        self._inspect_timer.start()

    def inspect_current(self):
        ctrl = getattr(self.ws, 'workbench', None); tp = getattr(self.ws, 'templates_page', None)
        path = self._current_path
        if not path or tp is None or not hasattr(tp, 'table_of'):
            self.detect.setText('Add a file to inspect its data.'); self.evidence.clear(); self.recs.clear(); self.data_preview.clear()
            self.data_preview.setRowCount(0); self.fig.clear(); self.preview.draw_idle(); self.confirm_btn.hide(); self.sheet.hide(); self._sync_create(); return
        if ctrl and self._current_project: ctrl.active_project = self._current_project
        if ctrl is not None and os.path.isfile(path) and not ctrl.ready(path):
            # A large file that is not read yet: reading it here would stop the window for as long as that takes (a big
            # workbook: many seconds). It is read in the background and shown as soon as it is there.
            self.breadcrumb.setText(os.path.basename(path)); self.detect.setText('Reading this file…')
            self.evidence.setText('Its data, its type and the graphs that fit appear here when it has been read.')
            self.recs.clear(); self.confirm_btn.hide(); self._sync_create()
            QTimer.singleShot(300, self._inspect_timer.start); return
        try:
            table, sheet, sheets, cols, mapping = tp.table_of(path)
            from opstudio.detection import detect
            result = detect(table, getattr(table, 'measurement_type', None)); self._detected = result
        except Exception as e:
            self.detect.setText('Could not read this file'); self.evidence.setText(str(e)); self.recs.clear()
            self.breadcrumb.setText(os.path.basename(path)); self.data_preview.clear(); self.data_preview.setRowCount(0); self.data_preview.setColumnCount(0)
            self.fig.clear(); self.preview.draw_idle(); self.confirm_btn.hide()      # nothing of the file looked at before stays on show beside this message
            self._sync_create(); return
        self._building = True
        self.breadcrumb.setText(((WP.get(self._current_project) or {}).get('name', 'Session')) + ' / ' + os.path.basename(path))
        self.detect.setText(f'{result.kind} · ' + ('Confirmed by you' if result.confirmed else result.confidence.capitalize() + ' confidence' if result.confidence != 'generic' else 'Review measurement type'))
        self.evidence.setText('\n'.join(result.evidence)); self.confirm_btn.setVisible(result.needs_confirmation)
        self.sheet.blockSignals(True); self.sheet.clear(); self.sheet.addItems([s or 'Data' for s in sheets]); self.sheet.setCurrentIndex(sheets.index(sheet)); self.sheet.blockSignals(False)
        self.sheet.setVisible(len(sheets) > 1)
        self.type_combo.setCurrentText(getattr(table, 'measurement_type', None) or 'Automatic')
        for box, val in [(self.x_combo, table.x), (self.y_combo, table.ys[0] if table.ys else None)]:
            box.blockSignals(True); box.clear(); box.addItems(table.numeric)
            if val: box.setCurrentText(val)
            box.blockSignals(False)
        df = table.df.head(5); self.data_preview.setColumnCount(len(df.columns)); self.data_preview.setRowCount(len(df))
        self.data_preview.setHorizontalHeaderLabels([str(c) for c in df.columns])
        self.files.setVisible(False)                           # the files of the session are in the tree on the left ('Files not in a project'); this list is kept for what reads it
        for r in range(len(df)):
            for c in range(len(df.columns)):
                v = df.iloc[r, c]
                try: text = f'{float(v):.6g}'
                except (TypeError, ValueError): text = str(v)
                self.data_preview.setItem(r, c, QTableWidgetItem(text))
        self.fig.clear(); ax = self.fig.add_subplot(111)
        if table.x and table.ys:
            step = max(1, len(table.df)//5000)
            ax.plot(table.arr(table.x)[::step], table.arr(table.ys[0])[::step], color='#1766d8', lw=1)
            ax.set_xlabel(table.x, fontsize=9); ax.set_ylabel(table.ys[0], fontsize=9); ax.tick_params(labelsize=8)
            ax.spines[['top','right']].set_visible(False)
        self.preview.draw_idle(); self._building = False
        self.refresh_recommendations()

    def mapping_changed(self, *_):
        if self._building or not self._current_path: return
        ctrl = getattr(self.ws, 'workbench', None)
        if not ctrl: return
        x, y = self.x_combo.currentText(), self.y_combo.currentText()
        if x and x == y: self.ws.set_status('Choose different X and Y columns.'); return
        ctrl.set_mapping(self._current_path, x, y, self.sheet.currentIndex(), self.type_combo.currentText())
        self.inspect_current()

    def confirm_type(self):
        if not hasattr(self, '_detected'): return
        self.type_combo.setCurrentText(self._detected.kind); self.mapping_changed()

    def series_of(self, paths, focus):
        """The ticked files that belong together with the one being looked at: the same kind of measurement (recognised,
        not guessed) and names built the same way. Returns (their paths in ticked order, why) - ([], '') when there is no
        such set of two or more."""
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl is None or len(paths) < 2 or focus not in paths: return [], ''
        import related
        from opstudio.detection import detect
        kinds = {}
        for p in paths:
            try:
                if not ctrl.ready(p): continue
                t = ctrl.table_for(p); d = detect(t, getattr(t, 'measurement_type', None))
                if not d.needs_confirmation: kinds[p] = d.kind
            except Exception: continue
        if focus not in kinds: return [], ''
        same = [p for p in paths if kinds.get(p) == kinds[focus]]
        if len(same) < 2: return [], ''
        for g in related.groups(same):                                      # not always all of them: the set the file being looked at belongs to
            if focus in g: return g, related.series(g)['why']
        return [], ''

    def refresh_recommendations(self):
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl is None: return
        paths = self.selected_paths(); current_tid = self.recs.currentItem().data(Qt.UserRole) if self.recs.currentItem() else None
        self.recs.clear()
        try:
            focus = self._current_path if self._current_path in paths else (paths[0] if paths else None)
            group, why = self.series_of(paths, focus)
            if tuple(paths) != self._mode_for: self._mode_for = tuple(paths); self._mode_user = False      # other files ticked: the app decides again
            if not self._mode_user:                                    # files of one series go into one graph, unless you chose otherwise for them
                want = 1 if group else (0 if self._auto_combined else self.combine_mode.currentIndex())
                if want != self.combine_mode.currentIndex():
                    self.combine_mode.blockSignals(True); self.combine_mode.setCurrentIndex(want); self.combine_mode.blockSignals(False)
                self._auto_combined = bool(group)
            together = self.combine_mode.currentIndex() == 1
            use = group if (together and group) else paths; self._rec_paths = list(use)
            shown = (together, tuple(use) if together else ())
            if shown != getattr(self, '_rec_shown', None): self._rec_shown = shown; current_tid = None      # other graphs are offered now (one of a series, or one per file): the recommended one is highlighted, not the one picked before
            rows = ctrl.recommendations(use, together=together, focus=focus, series=bool(together and group))
            for row in rows[:16]:
                title = row['name'] + ('\nRecommended' if row.get('recommended') else '') + '\n' + row['reason']
                item = QListWidgetItem(title); item.setData(Qt.UserRole, row['id']); item.setToolTip(row['use'] + '\n' + row['reason'])
                if row.get('preview') and os.path.isfile(row['preview']): item.setIcon(QIcon(row['preview']))
                item.setSizeHint(QSize(310, 112))
                if not row['compatible']: item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self.recs.addItem(item)
                if row['id'] == current_tid: self.recs.setCurrentItem(item)
            name = os.path.basename(focus) if focus else ''
            left_out = len(paths) - len(use)
            self.rec_caption.setText(f'From Analysis templates · {len(paths)} file(s) selected. ' + (
                (f'{len(use)} of them look like one series ({why}): graphs that show them together come first.' + ((' The other one is left out of it.' if left_out == 1 else f' The other {left_out} are left out of it.') if left_out else '')
                 + " Choose 'Separate graph for each file' below for one graph each.") if (together and group) else 'Combined output.' if together else
                (f'Templates that fit {name}; a graph is made for each selected file the template fits.' if len(paths) > 1 else 'Separate output for each file.')))
            if not rows: self.rec_caption.setText('No matching templates. Confirm the data type and column mapping, or browse Analysis.')
        except Exception as e: self.rec_caption.setText(f'Recommendations unavailable: {e}')
        if self.recs.currentRow() < 0:
            for i in range(self.recs.count()):
                if self.recs.item(i).flags() & Qt.ItemIsEnabled: self.recs.setCurrentRow(i); break
        self._sync_create()

    def _sync_create(self):
        if not hasattr(self, 'b_auto'): return
        item = self.recs.currentItem()
        good = bool(item and item.flags() & Qt.ItemIsEnabled and self.selected_paths())
        self.b_auto.setEnabled(good); self.b_auto.setToolTip('Create the selected Analysis template from your data' if good else 'Select compatible data and confirm its measurement type first')

    def draw_recommended(self):
        item = self.recs.currentItem()
        if not item or not item.flags() & Qt.ItemIsEnabled: self.ws.set_status('Select a compatible graph template first.'); return
        ctrl = getattr(self.ws, 'workbench', None)
        together = self.combine_mode.currentIndex() == 1; paths = self.selected_paths()
        if together and self._rec_paths and set(self._rec_paths) <= set(paths): paths = list(self._rec_paths)      # the series the graphs were offered for
        if ctrl: return ctrl.create_graphs(paths, item.data(Qt.UserRole), together)

    def browse_templates(self):
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.select_inputs(self.selected_paths())
        tp = self.ws.templates_page
        tp.together.setChecked(self.combine_mode.currentIndex() == 1)
        tp.find.clear(); tp.field.setCurrentIndex(0); tp.source.setCurrentIndex(0); tp.state.setCurrentIndex(0)
        tp.fits.setChecked(True); tp.filter_templates(); self.ws.go(5)

    def open_workbook(self):
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.select_inputs(self.selected_paths()); ctrl.workbook.set_paths(self.selected_paths()); self.ws.go(7)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() == '.opsproject': self.import_project(str(p)); continue
            if p.is_dir(): self.add_disk_folder(str(p))             # a folder: comes in as a folder, its sub-folders inside it
            elif p.is_file(): paths.append(str(p))
        if paths: self.add_files(paths)
        event.acceptProposedAction()

    def show_file_details(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dialog=QDialog(self);dialog.setWindowTitle('Project file details');dialog.resize(1000,480)
        layout=QVBoxLayout(dialog);table=QTableWidget();layout.addWidget(table)
        headers=['File','Format','Data type','Rows','Sheets','Status','Project']
        table.setColumnCount(len(headers));table.setHorizontalHeaderLabels(headers)
        inputs=self.selected_inputs()
        if not inputs and self._current_project:inputs=[(self._current_project,p) for p in (WP.get(self._current_project) or {}).get('files',[])]
        table.setRowCount(len(inputs));table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ctrl=getattr(self.ws,'workbench',None)
        from opstudio.detection import detect
        for index,(slug,path) in enumerate(inputs):
            kind='—';rows='—';sheets='—';status='Missing' if not os.path.isfile(path) else 'Not inspected'
            try:
                if ctrl and os.path.isfile(path):
                    t,_pick,names,_cols,_prefs=ctrl._table(path,slug)
                    kind=detect(t,getattr(t,'measurement_type',None)).kind
                    rows=f'{len(t.df):,}';sheets=str(len(names));status='Ready'
            except Exception as e:status='Could not read: '+str(e)
            values=[os.path.basename(path),Path(path).suffix.lstrip('.').upper(),kind,rows,sheets,status,(WP.get(slug) or {}).get('name','Session')]
            for col,text in enumerate(values):
                item=QTableWidgetItem(text);item.setToolTip(path+'\n'+status);table.setItem(index,col,item)
        table.resizeColumnsToContents();table.horizontalHeader().setStretchLastSection(True)
        buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        dialog.exec()

    def refresh_from_disk(self):
        ctrl = getattr(self.ws, 'workbench', None)
        if ctrl: ctrl.refresh_sources()
        self.refresh()
        self.ws.set_status('Projects refreshed. Missing files are marked; working-copy edits are retained.')

    def showEvent(self, event):
        super().showEvent(event); self.refresh()
        if not getattr(self, '_sized', False):
            self._sized = True
            QTimer.singleShot(0, lambda: self.splitter.setSizes([int(self.width()*.27),int(self.width()*.43),int(self.width()*.30)]))
