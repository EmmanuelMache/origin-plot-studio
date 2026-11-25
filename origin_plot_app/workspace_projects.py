"""Named projects with virtual folders, independent working state and portable archives.

Original source files are never changed. Version-one file-list projects migrate on
read. An .opsproject archive includes copies of inputs and saved graph settings.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time
import uuid
import zipfile

SCHEMA = 'origin-plot-studio.project/2'


def _load():
    import workspace_qt as WQ
    projects = copy.deepcopy(WQ.load_cfg().get('projects') or {})
    for slug, p in projects.items():
        p.setdefault('id', slug); p.setdefault('folders', [])
        p.setdefault('locations', {}); p.setdefault('state', {})
        p.setdefault('file_settings', {}); p.setdefault('schema', SCHEMA)
    return projects


def _save(projects):
    import workspace_qt as WQ
    if WQ.save_cfg({'projects': projects}) is False:
        raise OSError('Project settings could not be saved. Check that the settings folder is writable.')


def list_projects():
    return sorted(_load().items(), key=lambda kv: kv[1].get('modified', 0), reverse=True)


def get(slug):
    return _load().get(slug)


def _update(slug, fn):
    allp = _load()
    if slug not in allp: return False
    fn(allp[slug]); allp[slug]['modified'] = time.time(); _save(allp)
    return True


def create(name, files=None):
    projects = _load(); slug = _slug(name, projects); now = time.time()
    projects[slug] = {'schema': SCHEMA, 'id': slug, 'name': str(name or '').strip() or 'Untitled project',
                      'files': list(dict.fromkeys(os.path.abspath(f) for f in files or [])),
                      'folders': [], 'locations': {}, 'state': {}, 'file_settings': {}, 'created': now, 'modified': now}
    _save(projects)
    return slug


def rename(slug, new_name):
    return bool(str(new_name or '').strip()) and _update(slug, lambda p: p.update(name=new_name.strip()))


def add_files(slug, files, folder=None):
    paths = list(dict.fromkeys(os.path.abspath(f) for f in files))
    def change(p):
        p['files'] = list(dict.fromkeys(p['files'] + paths))
        if folder is not None:
            if folder and not any(f['id'] == folder for f in p['folders']): raise ValueError('Folder does not exist')
            for f in paths: p['locations'][f] = folder
    return _update(slug, change)


def remove_file(slug, path):
    def change(p):
        p['files'] = [f for f in p['files'] if f != path]
        p['locations'].pop(path, None); p['file_settings'].pop(path, None)
        state = p.get('state') or {}
        if state.get('session'):
            state['session']['files'] = [f for f in state['session'].get('files', []) if f != path]
            state['session']['graphs'] = [g for g in state['session'].get('graphs', []) if g.get('file') != path]
        state['templates'] = [g for g in state.get('templates', []) if path not in g.get('files', [])]
    return _update(slug, change)


def delete(slug):
    projects = _load()
    if slug not in projects: return False
    del projects[slug]; _save(projects); return True


def missing_files(slug):
    return [f for f in (get(slug) or {}).get('files', []) if not os.path.isfile(f)]


def add_folder(slug, name, parent=''):
    name = str(name).strip()
    if not name: raise ValueError('Enter a folder name')
    fid = uuid.uuid4().hex
    def change(p):
        if parent and not any(f['id'] == parent for f in p['folders']): raise ValueError('Parent folder does not exist')
        if any(f['name'].casefold() == name.casefold() and f.get('parent', '') == parent for f in p['folders']):
            raise ValueError('A folder with this name already exists here')
        p['folders'].append({'id': fid, 'name': name, 'parent': parent})
    if not _update(slug, change): raise ValueError('Select a project first')
    return fid


def descendants(project, folder):
    result = {folder}
    while True:
        more = {f['id'] for f in project['folders'] if f.get('parent', '') in result}
        if more <= result: return result
        result |= more


def folder_files(slug, folder):
    p = get(slug)
    if not p: return []
    ids = descendants(p, folder)
    return [f for f in p['files'] if p['locations'].get(f, '') in ids]


def rename_folder(slug, folder, name):
    name = str(name).strip()
    if not name: raise ValueError('Enter a folder name')
    return _update(slug, lambda p: next(f for f in p['folders'] if f['id'] == folder).update(name=name))


def remove_folder(slug, folder):
    def change(p):
        ids = descendants(p, folder)
        p['folders'] = [f for f in p['folders'] if f['id'] not in ids]
        # Removing the folder keeps its input files at the project root.
        p['locations'] = {k: v for k, v in p['locations'].items() if v not in ids}
    return _update(slug, change)


def move_folder(slug, folder, parent=''):
    def change(p):
        if parent in descendants(p, folder): raise ValueError('A folder cannot be moved into itself or a child')
        if parent and not any(f['id'] == parent for f in p['folders']): raise ValueError('Destination does not exist')
        next(f for f in p['folders'] if f['id'] == folder)['parent'] = parent
    return _update(slug, change)


def reorder(slug, paths):
    def change(p):
        p['files'] = list(dict.fromkeys([x for x in paths if x in p['files']] + p['files']))
    return _update(slug, change)


def reorder_folders(slug, ids):
    def change(p):
        by = {f['id']: f for f in p['folders']}
        order = list(dict.fromkeys([i for i in ids if i in by] + list(by)))
        p['folders'] = [by[i] for i in order]
    return _update(slug, change)


def set_file_settings(slug, path, settings):
    def change(p): p['file_settings'][path] = copy.deepcopy(settings)
    return _update(slug, change)


def save_state(slug, state):
    return _update(slug, lambda p: p.update(state=copy.deepcopy(state)))


def export_project(slug, path):
    project = get(slug)
    if not project: raise ValueError('Project does not exist')
    missing = missing_files(slug)
    if missing: raise ValueError('Locate or remove missing inputs before exporting: ' + ', '.join(os.path.basename(f) for f in missing))
    project = copy.deepcopy(project); mapping = {}
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.ops-', suffix='.tmp', dir=target.parent); os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in project['files']:
                rel = 'inputs/' + hashlib.sha256(f.encode()).hexdigest()[:12] + '/' + Path(f).name
                z.write(f, rel); mapping[f] = rel
            project = _remap(project, mapping)
            z.writestr('project.json', json.dumps(project, ensure_ascii=False, indent=2, default=_json_default))
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return str(target)


def import_project(path):
    import workspace_qt as WQ
    # Validate the whole archive before creating or replacing any project.
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 2 * 1024 ** 3: raise ValueError('Project is larger than 2 GiB')
        p = json.loads(z.read('project.json'))
        if p.get('schema') != SCHEMA: raise ValueError('Unsupported project format')
        for f in p.get('files', []):
            rel = PurePosixPath(f)
            if rel.is_absolute() or '..' in rel.parts or not f.startswith('inputs/') or '\\' in f:
                raise ValueError('Unsafe project input path')
            z.getinfo(f)
        # Project data lives beside the user's settings, never inside the installation.
        cfg = WQ.cfg_path()
        root = cfg.parent / 'project_data' / uuid.uuid4().hex
        root.mkdir(parents=True, exist_ok=True)
        mapping = {}
        for f in p.get('files', []):
            dest = root.joinpath(*PurePosixPath(f).parts); dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(f) as src, open(dest, 'wb') as out:
                import shutil
                shutil.copyfileobj(src, out)
            mapping[f] = str(dest)
    p = _remap(p, mapping); projects = _load()
    used = {v['name'] for v in projects.values()}
    if p['name'] in used:
        original = p['name']; p['name'] = original + ' (imported)'; n = 2
        while p['name'] in used: p['name'] = original + f' (imported {n})'; n += 1
    slug = _slug(p['name'], projects)
    old = p.get('id'); p['id'] = slug; p['modified'] = time.time()
    for g in (p.get('state', {}).get('session') or {}).get('graphs', []):
        if g.get('project_id') == old: g['project_id'] = slug
        g['project'] = p['name']
    for combo in p.get('state', {}).get('templates', []):
        if combo.get('project_id') in (old, None): combo['project_id'] = slug
    projects[slug] = p; _save(projects); return slug


def _remap(obj, mapping):
    if isinstance(obj, dict): return {mapping.get(k, k): _remap(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list): return [_remap(v, mapping) for v in obj]
    if isinstance(obj, tuple): return [_remap(v, mapping) for v in obj]
    if isinstance(obj, str):
        if obj in mapping: return mapping[obj]
        # Graph identifiers contain a source path followed by |table.
        return next((new + obj[len(old):] for old, new in mapping.items() if obj.startswith(old + '|')), obj)
    return obj


def _json_default(obj):
    if hasattr(obj, 'isoformat'): return obj.isoformat()
    if hasattr(obj, 'tolist'): return obj.tolist()
    if hasattr(obj, 'item'): return obj.item()
    raise TypeError(type(obj).__name__)


def _slug(name, existing):
    base = re.sub(r'[^a-z0-9]+', '-', str(name or '').strip().lower()).strip('-') or 'project'
    slug = base; i = 2
    while slug in existing: slug = f'{base}-{i}'; i += 1
    return slug
