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
import shutil
import stat
import struct
import tempfile
import time
import unicodedata
import uuid
import zipfile
import zlib

SCHEMA = 'origin-plot-studio.project/2'

# ---------------------------------------------------------------------------------------------- limits of an import
# A portable project comes from somebody else's computer: everything in it is checked before anything is kept.
# The limits are generous on purpose (measurement files are large) and every one can be raised for a legitimate
# project with an environment variable, set before the app starts. A message that refuses a project names the limit
# and the variable.
MB = 1024 * 1024
IMPORT_MAX_TOTAL_MB = 2048          # all files of one project together (the 2 GiB cap)        OPS_IMPORT_MAX_TOTAL_MB
IMPORT_MAX_FILE_MB = 1024           # one input file, counted while it is unpacked             OPS_IMPORT_MAX_FILE_MB
IMPORT_MAX_ENTRIES = 5000           # entries in the archive                                   OPS_IMPORT_MAX_ENTRIES
IMPORT_MAX_MANIFEST_MB = 16         # project.json (names, folders, saved graph settings)      OPS_IMPORT_MAX_MANIFEST_MB
IMPORT_MAX_RATIO = 200              # unpacked size / packed size of one entry ...             OPS_IMPORT_MAX_RATIO
IMPORT_RATIO_FLOOR_MB = 8           # ... looked at only for entries larger than this (small files pack very well)
IMPORT_MAX_JSON_DEPTH = 64          # lists / objects inside each other in project.json
IMPORT_MAX_STRING = 1_000_000       # characters of one text value in project.json
IMPORT_MAX_KEY = 2000               # characters of one name (key) in project.json
IMPORT_MAX_NAME = 400               # characters of an entry name in the archive
IMPORT_MAX_COMPONENT = 200          # characters of one part of it (a file name)
IMPORT_MAX_FOLDERS = 5000           # virtual folders of a project
_CHUNK = 1024 * 1024
_ENV = {'total_mb': 'OPS_IMPORT_MAX_TOTAL_MB', 'file_mb': 'OPS_IMPORT_MAX_FILE_MB', 'entries': 'OPS_IMPORT_MAX_ENTRIES',
        'manifest_mb': 'OPS_IMPORT_MAX_MANIFEST_MB', 'ratio': 'OPS_IMPORT_MAX_RATIO'}

# What a project may carry. Everything else in project.json is dropped and named in the result of the import: a project
# is data and graph settings - never credentials, the place updates come from or the keys they are checked with, the
# outbound policy, the security profile, or the path of a program (Origin, Python).
PROJECT_KEYS = ('schema', 'id', 'name', 'files', 'folders', 'locations', 'state', 'file_settings', 'created', 'modified')
STATE_KEYS = ('session', 'templates', 'current_graph', 'groups', 'group_formats', 'selected', 'page')
FOLDER_KEYS = ('id', 'name', 'parent')
_FORBIDDEN_KEY = re.compile(
    r'(?:^|_)(?:api_?keys?|credentials?|passwords?|passwd|secrets?|tokens?|authorization|bearer)(?:_|$)'
    r'|^update_(?:source|token|url|repo|channel|server|keys?)$|^trusted_|^signing_|^public_keys?$|^update_keys?$'
    r'|^outbound|^security_profile$|^privacy_level$|^local_only$'
    r'|^(?:origin|python|program|app)_(?:exe|path|dir|folder|executable|home)$|^executable$|^exe_path$|_exe$'
    r'|^ai_(?:link|url|endpoint|base|destination|provider|key)$|^endpoint$|^base_url$|^proxy$|^private_dir$', re.I)
_RESERVED = frozenset(['CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$', 'CLOCK$'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
                      + [f'{d}{c}' for d in ('COM', 'LPT') for c in '\u00b9\u00b2\u00b3'])
_NETWORK_PATH = re.compile(r'^(?:[\\/]{2}[^\\/]|[\\/]{2}[?.][\\/])')            # \\server\share, //server/share, \\?\ and \\.\ device paths


class ProjectImportError(ValueError):
    """The project archive was refused. The text says why in plain words; nothing of it was kept."""


class ImportCancelled(ProjectImportError):
    """The import was stopped on request; nothing of it was kept."""


class ImportResult(str):
    """The id (slug) of the imported project - a plain text for every caller that expects one - that also says what
    the import did:  .dropped  (settings in the archive that a project may not carry and that were left out),
    .ignored  (entries of the archive that the project does not list),  .files,  .bytes,  .name."""
    def __new__(cls, slug, *, dropped=(), ignored=(), files=0, size=0, name=''):
        o = super().__new__(cls, slug)
        o.dropped = list(dropped); o.ignored = list(ignored); o.files = int(files); o.bytes = int(size); o.name = name
        return o

    def summary(self):
        lines = [f"Project '{self.name}' imported: {self.files} file(s), {_size_text(self.bytes)}."]
        if self.dropped: lines.append('Left out (a project cannot carry these): ' + '; '.join(self.dropped[:12]) + (' ...' if len(self.dropped) > 12 else ''))
        if self.ignored: lines.append(f'{len(self.ignored)} entr{"y" if len(self.ignored) == 1 else "ies"} of the archive not listed by the project were not unpacked.')
        return '\n'.join(lines)


LAST_IMPORT = {}                    # what the last import_project() reported (see ImportResult), for a window that wants to show it


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
                rel = 'inputs/' + hashlib.sha256(f.encode()).hexdigest()[:12] + '/' + _archive_name(Path(f).name)
                z.write(f, rel); mapping[f] = rel
            project = _remap(project, mapping)
            project = _exportable(project)             # only what a project may carry: no credentials, no program settings
            z.writestr('project.json', json.dumps(project, ensure_ascii=False, indent=2, default=_json_default))
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return str(target)


def import_limits(overrides=None):
    """The limits of an import, in bytes / counts: the constants at the top of this file, each one replaced by its
    environment variable when that holds a positive number (OPS_IMPORT_MAX_FILE_MB=4096 for a 4 GiB file), then by
    overrides (the same names: total_mb, file_mb, entries, manifest_mb, ratio)."""
    lim = {'total_mb': IMPORT_MAX_TOTAL_MB, 'file_mb': IMPORT_MAX_FILE_MB, 'entries': IMPORT_MAX_ENTRIES,
           'manifest_mb': IMPORT_MAX_MANIFEST_MB, 'ratio': IMPORT_MAX_RATIO}
    for key, env in _ENV.items():
        try:
            v = float(str(os.environ.get(env, '')).strip())
            if v > 0 and v == v and v != float('inf'): lim[key] = v
        except ValueError: pass
    for key, v in (overrides or {}).items():
        if key in lim and isinstance(v, (int, float)) and v > 0: lim[key] = v
    return {'total': int(lim['total_mb'] * MB), 'file': int(lim['file_mb'] * MB), 'entries': int(lim['entries']),
            'manifest': int(lim['manifest_mb'] * MB), 'ratio': float(lim['ratio']), 'ratio_floor': IMPORT_RATIO_FLOOR_MB * MB}


def _size_text(n):
    n = float(n)
    for unit, size in (('GiB', 1024 ** 3), ('MB', MB), ('kB', 1024)):
        if n >= size: return f'{n / size:.3g} {unit}'
    return f'{int(n)} bytes'


def _raise_hint(env):
    return (f' If this is a legitimate large project, close the app, set the environment variable {env} to a larger number'
            ' and import again.')


def unsafe_name_reason(name):
    """Why an entry name of an archive is not accepted, or '' when it is. The same rules on every system, because a
    project made on one computer is opened on another: no absolute path, no drive letter or network path, no '..',
    no backslash (it is a separator on Windows and a letter elsewhere), no ':' (drive or alternate data stream), no
    name Windows keeps for devices (CON, NUL, COM1 ... with or without an extension), no trailing dot or space
    (Windows drops them, so two names become one), no control characters and none of < > " | ? *."""
    if not isinstance(name, str) or not name: return 'an empty name'
    if len(name) > IMPORT_MAX_NAME: return f'a name longer than {IMPORT_MAX_NAME} characters'
    if any(ord(c) < 32 or ord(c) == 127 for c in name): return 'a control character in a name'
    if '\\' in name: return 'a backslash in a name'
    if name.startswith('/'): return 'an absolute path'
    if re.match(r'^[A-Za-z]:', name): return 'a drive letter'
    parts = name[:-1].split('/') if name.endswith('/') else name.split('/')
    for part in parts:
        if part == '': return 'an empty part in a path'
        if part in ('.', '..'): return "a '.' or '..' part in a path"
        if ':' in part: return "a ':' in a name (a drive or an alternate data stream)"
        if any(c in part for c in '<>"|?*'): return 'a character Windows does not allow in a name'
        if part != part.rstrip('. '): return 'a name that ends with a dot or a space'
        if len(part) > IMPORT_MAX_COMPONENT: return f'a file name longer than {IMPORT_MAX_COMPONENT} characters'
        if part.split('.')[0].rstrip(' ').upper() in _RESERVED: return 'a name Windows keeps for a device (CON, NUL, COM1 ...)'
    return ''


def _fold(name):
    """The name as a file system that ignores case (and the way accents are stored) sees it."""
    return unicodedata.normalize('NFC', name).casefold().rstrip('/')


def _archive_name(name):
    """The file name an input gets inside an exported project: the name itself when every system accepts it, else the
    same name with the offending characters replaced - so a project exported here can be imported everywhere."""
    if not unsafe_name_reason('inputs/' + name): return name
    safe = re.sub(r'[\x00-\x1f\x7f\\/:<>"|?*]', '_', name).rstrip('. ')[:IMPORT_MAX_COMPONENT] or 'input'
    if safe.split('.')[0].rstrip(' ').upper() in _RESERVED: safe = '_' + safe
    return safe if not unsafe_name_reason('inputs/' + safe) else 'input'


_SETTING_NAME = re.compile(r'[A-Za-z0-9 _\-$]{1,64}')


def _key_norm(key):
    return re.sub(r'[^a-z0-9$]+', '_', str(key).lower()).strip('_')


def _strip_forbidden(obj, where, dropped):
    """Remove, anywhere inside obj, the settings a project may not carry (see _FORBIDDEN_KEY) and network paths in
    text values. Works on a copy-free walk with its own stack, so deep data cannot exhaust the interpreter."""
    stack = [(obj, where)]
    while stack:
        node, at = stack.pop()
        if isinstance(node, dict):
            for k in list(node):
                if isinstance(k, str) and _SETTING_NAME.fullmatch(k) and _FORBIDDEN_KEY.search(_key_norm(k)):      # a name of a file or a graph is not a setting
                    del node[k]; dropped.append(f"{at}.{k[:60]} (a security or program setting)"); continue
                v = node[k]
                if isinstance(v, str) and _NETWORK_PATH.match(v): node[k] = ''; dropped.append(f"{at}.{str(k)[:60]} (a network path)")
                elif isinstance(v, (dict, list)): stack.append((v, f"{at}.{str(k)[:60]}"))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str) and _NETWORK_PATH.match(v): node[i] = ''; dropped.append(f"{at}[{i}] (a network path)")
                elif isinstance(v, (dict, list)): stack.append((v, f"{at}[{i}]"))
    return obj


def _exportable(project):
    """The project as it goes into an exported archive: the keys a project has, without anything that looks like a
    credential or a program setting, and with credentials inside text values removed."""
    out = {k: v for k, v in project.items() if k in PROJECT_KEYS}
    _strip_forbidden(out, 'project', [])
    try:
        import outbound_policy
        stack = [out]
        while stack:
            node = stack.pop()
            items = node.items() if isinstance(node, dict) else enumerate(node)
            for k, v in list(items):
                if isinstance(v, str):
                    if outbound_policy.has_secret(v): node[k] = outbound_policy.redact(v)
                elif isinstance(v, (dict, list)): stack.append(v)
    except ImportError: pass
    return out


def _cancelled(cancel):
    if cancel is None: return False
    if callable(cancel): return bool(cancel())
    is_set = getattr(cancel, 'is_set', None)
    return bool(is_set()) if callable(is_set) else bool(cancel)


def _stop_if(cancel):
    if _cancelled(cancel): raise ImportCancelled('The import was cancelled. Nothing was imported.')


def _peek_archive(path, lim):
    """Look at the end of the file (the table of contents of a zip) BEFORE zipfile loads it: how many entries it claims
    and how large the table is. An archive that claims far too much is refused without being read into memory."""
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        back = min(size, 65536 + 22 + 20); f.seek(size - back); tail = f.read(back)
        at = tail.rfind(b'PK\x05\x06')
        if at < 0 or len(tail) - at < 22: raise ProjectImportError(_DAMAGED)
        entries, cd_size = struct.unpack('<H', tail[at + 10:at + 12])[0], struct.unpack('<I', tail[at + 12:at + 16])[0]
        if entries == 0xFFFF or cd_size == 0xFFFFFFFF:                          # the large (zip64) form keeps the real numbers elsewhere
            loc = tail.rfind(b'PK\x06\x07', 0, at)
            if loc >= 0 and at - loc >= 20:
                where = struct.unpack('<Q', tail[loc + 8:loc + 16])[0]
                if 0 <= where <= size - 56:
                    f.seek(where); rec = f.read(56)
                    if rec[:4] == b'PK\x06\x06': entries, cd_size = struct.unpack('<Q', rec[32:40])[0], struct.unpack('<Q', rec[40:48])[0]
    if entries > lim['entries'] or cd_size > lim['entries'] * 2048 + 65536:
        raise ProjectImportError(f"The project archive lists too many entries ({entries}; the limit is {lim['entries']})." + _raise_hint('OPS_IMPORT_MAX_ENTRIES'))
    return size


_DAMAGED = ('This file is not a complete project archive: it is damaged or was cut off (for example by an interrupted '
            'download or copy). Nothing was imported. Ask for the project file again.')


def _read_limited(z, info, limit, what, env, cancel=None):
    """The bytes of one entry, read in pieces and counted: more than limit is refused whatever the archive claims."""
    out = bytearray()
    with z.open(info) as src:
        while True:
            _stop_if(cancel)
            chunk = src.read(_CHUNK)
            if not chunk: break
            out += chunk
            if len(out) > limit: raise ProjectImportError(f'{what} is larger than {_size_text(limit)}, the limit for it.' + _raise_hint(env))
    return bytes(out)


def _parse_manifest(raw, lim):
    """project.json as data: plain JSON only (nothing in it is ever executed), no name twice in one object, bounded
    nesting, bounded text lengths."""
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise ProjectImportError('project.json names the same setting twice; the project file is not valid.')
            d[k] = v
        return d
    try: text = raw.decode('utf-8-sig')
    except UnicodeDecodeError: raise ProjectImportError('project.json is not text (UTF-8); the project file is not valid.') from None
    try: p = json.loads(text, object_pairs_hook=pairs)
    except RecursionError: raise ProjectImportError(f'project.json is nested too deeply (more than {IMPORT_MAX_JSON_DEPTH} levels); the project file is not valid.') from None
    except ProjectImportError: raise
    except ValueError: raise ProjectImportError('project.json cannot be read; the project file is damaged or not a project.') from None
    if not isinstance(p, dict): raise ProjectImportError('Unsupported project format')
    stack = [(p, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > IMPORT_MAX_JSON_DEPTH: raise ProjectImportError(f'project.json is nested too deeply (more than {IMPORT_MAX_JSON_DEPTH} levels); the project file is not valid.')
        for k, v in (node.items() if isinstance(node, dict) else enumerate(node)):
            if isinstance(k, str) and len(k) > IMPORT_MAX_KEY: raise ProjectImportError('project.json holds a name that is too long; the project file is not valid.')
            if isinstance(v, str):
                if len(v) > IMPORT_MAX_STRING: raise ProjectImportError('project.json holds a text that is too long; the project file is not valid.')
            elif isinstance(v, (dict, list)): stack.append((v, depth + 1))
    return p


def _text(value, limit, fallback=''):
    if not isinstance(value, str): return fallback
    return re.sub(r'[\x00-\x1f\x7f]', ' ', value).strip()[:limit] or fallback


def _source_of(key):
    """The input a graph name ('input|table') belongs to."""
    return key.split('|', 1)[0] if isinstance(key, str) else None


def _clean_manifest(p, dropped):
    """The project of an archive reduced to what a project may carry, with every reference checked against the list
    of its own inputs. Paths are still the ones inside the archive ('inputs/...') here. Raises for a project that is
    not valid at all; leaves out (and names in dropped) what merely does not belong."""
    if p.get('schema') != SCHEMA: raise ProjectImportError('Unsupported project format')
    files = p.get('files', [])
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files): raise ProjectImportError('Unsupported project format')
    known = set(files)
    for k in p:
        if k not in PROJECT_KEYS:
            dropped.append(f"{str(k)[:60]} ({'a security or program setting' if _FORBIDDEN_KEY.search(_key_norm(k)) else 'not a project setting'})")
    out = {'schema': SCHEMA, 'name': _text(p.get('name'), 200, 'Untitled project'), 'files': list(files)}
    if isinstance(p.get('id'), str): out['id'] = _text(p['id'], 200)
    for k in ('created', 'modified'):
        if isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool) and p[k] == p[k]: out[k] = p[k]
    # folders: id / name / parent, nothing else
    folders = []; raw = p.get('folders', [])
    if not isinstance(raw, list): raw = []; dropped.append('folders (not a list)')
    if len(raw) > IMPORT_MAX_FOLDERS: raise ProjectImportError(f'The project has more than {IMPORT_MAX_FOLDERS} folders; the project file is not valid.')
    seen = set()
    for f in raw:
        if not isinstance(f, dict) or not isinstance(f.get('id'), str) or not f['id'] or len(f['id']) > 64 or f['id'] in seen or not isinstance(f.get('name'), str):
            dropped.append('a folder that is not valid'); continue
        extra = [k for k in f if k not in FOLDER_KEYS]
        if extra: dropped.append(f"folder setting {str(extra[0])[:60]} (not a project setting)")
        seen.add(f['id']); folders.append({'id': f['id'], 'name': _text(f['name'], 200, 'Folder'), 'parent': f.get('parent') if isinstance(f.get('parent'), str) else ''})
    for f in folders:
        if f['parent'] and f['parent'] not in seen: f['parent'] = ''
    out['folders'] = folders
    locs = p.get('locations', {}); out['locations'] = {}
    if isinstance(locs, dict):
        for k, v in locs.items():
            if k in known and (v in ('', None) or (isinstance(v, str) and v in seen)): out['locations'][k] = v
            else: dropped.append('a folder assignment of a file the project does not hold')
    fs = p.get('file_settings', {}); out['file_settings'] = {}
    if isinstance(fs, dict):
        for k, v in fs.items():
            if k in known and isinstance(v, dict): out['file_settings'][k] = v
            else: dropped.append('settings of a file the project does not hold')
    _strip_forbidden(out['file_settings'], 'file_settings', dropped)
    out['state'] = _clean_state(p.get('state', {}), known, dropped)
    return out


def _clean_state(state, known, dropped):
    """The saved working state of a project (graphs, their settings, what was selected): known parts only, and every
    file it names must be one of the project's own inputs - a project cannot point the app at other files or places."""
    if not isinstance(state, dict): return {}
    out = {}
    for k, v in state.items():
        if k not in STATE_KEYS:
            dropped.append(f"state.{str(k)[:60]} ({'a security or program setting' if _FORBIDDEN_KEY.search(_key_norm(k)) else 'not a project setting'})")
    def mine(path): return isinstance(path, str) and path in known
    def keys_mine(keys): return isinstance(keys, list) and all(isinstance(k, str) and (k.startswith('Combined|') or _source_of(k) in known) for k in keys)
    lost = [0]
    def keep(seq, ok):
        good = [x for x in seq if ok(x)]; lost[0] += len(seq) - len(good); return good
    s = state.get('session')
    if isinstance(s, dict):
        s = dict(s)
        for k in ('files', 'info_files'):
            if k in s: s[k] = keep(s[k], mine) if isinstance(s[k], list) else []
        if 'sources' in s:
            src = s['sources'] if isinstance(s['sources'], dict) else {}
            s['sources'] = {k: v for k, v in src.items() if mine(k)}; lost[0] += len(src) - len(s['sources'])
        if 'graphs' in s: s['graphs'] = keep(s['graphs'], lambda g: isinstance(g, dict) and mine(g.get('file')) and isinstance(g.get('table'), str)) if isinstance(s['graphs'], list) else []
        if 'figures' in s: s['figures'] = keep(s['figures'], lambda b: isinstance(b, dict) and keys_mine(b.get('keys'))) if isinstance(s['figures'], list) else []
        out['session'] = s
    elif s is not None: dropped.append('state.session (not valid)')
    t = state.get('templates')
    if isinstance(t, list): out['templates'] = keep(t, lambda c: isinstance(c, dict) and isinstance(c.get('files'), list) and all(mine(f) for f in c['files']))
    elif t is not None: dropped.append('state.templates (not valid)')
    g = state.get('groups')
    if isinstance(g, list): out['groups'] = keep(g, lambda e: isinstance(e, list) and len(e) == 2 and isinstance(e[0], str) and keys_mine(e[1]))
    gf = state.get('group_formats')
    if isinstance(gf, list): out['group_formats'] = keep(gf, lambda e: isinstance(e, list) and len(e) == 2 and keys_mine(e[0]) and isinstance(e[1], dict))
    sel = state.get('selected')
    if isinstance(sel, list): out['selected'] = keep(sel, mine)
    cur = state.get('current_graph')
    if cur is None or (isinstance(cur, str) and ('|' not in cur or cur.startswith('Combined|') or _source_of(cur) in known)):
        if 'current_graph' in state: out['current_graph'] = cur
    else: lost[0] += 1
    if isinstance(state.get('page'), int) and not isinstance(state.get('page'), bool) and 0 <= state['page'] < 100: out['page'] = state['page']
    if lost[0]: dropped.append(f'{lost[0]} saved reference(s) to files or graphs that are not part of the project')
    _strip_forbidden(out, 'state', dropped)
    return out


def _check_entries(z, lim, archive_size, cancel):
    """Every entry of the archive, listed by the project or not: names, kinds, declared sizes. Returns {name: info}."""
    infos = z.infolist()
    if len(infos) > lim['entries']:
        raise ProjectImportError(f"The project archive holds too many entries ({len(infos)}; the limit is {lim['entries']})." + _raise_hint('OPS_IMPORT_MAX_ENTRIES'))
    declared = sum(i.file_size for i in infos)
    if declared > lim['total']:
        raise ProjectImportError(f"Project is larger than {_size_text(lim['total'])}: it holds {_size_text(declared)}, and {_size_text(lim['total'])} is the limit for one project." + _raise_hint('OPS_IMPORT_MAX_TOTAL_MB'))
    if sum(i.compress_size for i in infos) > archive_size:
        raise ProjectImportError('The project archive is not valid: its entries overlap. Nothing was imported.')
    by_name, folded = {}, {}
    for n, info in enumerate(infos):
        if n % 500 == 0: _stop_if(cancel)
        name = info.filename
        why = unsafe_name_reason(name)
        if why: raise ProjectImportError(f'Unsafe project input path: the archive holds {why}. Nothing was imported.')
        mode = info.external_attr >> 16
        if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            kind = 'a link' if stat.S_ISLNK(mode) else 'a device or other special file'
            raise ProjectImportError(f'Unsafe project input path: the archive holds {kind} instead of a plain file. Nothing was imported.')
        if info.flag_bits & 0x1: raise ProjectImportError('The project archive is protected with a password; such archives are not opened. Nothing was imported.')
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ProjectImportError('The project archive uses a kind of compression this app does not open. Nothing was imported.')
        key = _fold(name)
        if key in folded:
            raise ProjectImportError('Unsafe project input path: the archive holds the same name twice' + ('' if folded[key] == name else ' (two names that differ only in capital letters)') + '. Nothing was imported.')
        folded[key] = name; by_name[name] = info
        if not info.is_dir():
            if info.file_size > lim['file']:
                raise ProjectImportError(f"'{PurePosixPath(name).name}' is {_size_text(info.file_size)}; the limit for one file of a project is {_size_text(lim['file'])}." + _raise_hint('OPS_IMPORT_MAX_FILE_MB'))
            if info.file_size > lim['ratio_floor'] and info.file_size > lim['ratio'] * max(info.compress_size, 1):
                raise ProjectImportError(f"'{PurePosixPath(name).name}' unpacks to more than {lim['ratio']:g} times its packed size, which measurement files do not do." + _raise_hint('OPS_IMPORT_MAX_RATIO'))
    return by_name


def _sweep_staging(data_root):
    """Remove what an import left behind when the app was closed in the middle of it (older than a day; only folders this
    module made itself)."""
    try:
        for d in data_root.iterdir():
            if re.fullmatch(r'\.staging-[0-9a-f]{32}', d.name) and d.is_dir() and not d.is_symlink() and time.time() - d.stat().st_mtime > 86400:
                shutil.rmtree(d, ignore_errors=True)
    except OSError: pass


def import_project(path, *, cancel=None, progress=None, limits=None):
    """Import a portable project (.opsproject). Returns the id of the new project (an ImportResult: a text that also
    says what was left out).

    The archive is somebody else's data: it is read, never run, and never changed. Everything is checked first; the
    inputs are then unpacked into a fresh staging folder inside the app's own data folder, under names this function
    makes itself (only the file name comes from the archive, after it passed unsafe_name_reason); the folder is moved
    into place only when all of it is there. When anything fails, or cancel says stop, the staging folder is removed
    and the projects that exist are exactly as before.

    cancel    a function that returns True, or an object with is_set() (threading.Event): stop as soon as possible
    progress  a function(done_bytes, total_bytes), called while files are unpacked
    limits    {'file_mb': ..., 'total_mb': ..., 'entries': ..., 'manifest_mb': ..., 'ratio': ...} instead of the
              defaults / environment variables (see import_limits)
    Raises ProjectImportError (a ValueError) with a plain-language reason; ImportCancelled when stopped."""
    import workspace_qt as WQ
    lim = import_limits(limits); dropped = []; src = Path(path)
    if not src.is_file(): raise ProjectImportError('The project file was not found.')
    # Project data lives beside the user's settings, never inside the installation.
    data_root = WQ.cfg_path().parent / 'project_data'
    new_id = uuid.uuid4().hex; staging = data_root / ('.staging-' + new_id); root = data_root / new_id
    moved = False
    try:
        _stop_if(cancel)
        archive_size = _peek_archive(src, lim)
        # Validate the whole archive before creating or replacing any project.
        with zipfile.ZipFile(src) as z:
            by_name = _check_entries(z, lim, archive_size, cancel)
            if 'project.json' not in by_name: raise ProjectImportError('This archive is not a project: it has no project.json. Nothing was imported.')
            raw = _read_limited(z, by_name['project.json'], lim['manifest'], 'project.json (the description of the project)', 'OPS_IMPORT_MAX_MANIFEST_MB', cancel)
            p = _parse_manifest(raw, lim)
            if p.get('schema') != SCHEMA: raise ProjectImportError('Unsupported project format')
            files = p.get('files', [])
            if not isinstance(files, list) or len(files) > lim['entries']: raise ProjectImportError('Unsupported project format')
            listed = set()
            for f in files:
                if not isinstance(f, str): raise ProjectImportError('Unsafe project input path')
                rel = PurePosixPath(f)
                if rel.is_absolute() or '..' in rel.parts or not f.startswith('inputs/') or '\\' in f or unsafe_name_reason(f) or f.endswith('/'):
                    raise ProjectImportError('Unsafe project input path')
                if _fold(f) in listed: raise ProjectImportError('Unsafe project input path: the project lists the same input twice. Nothing was imported.')
                listed.add(_fold(f))
                if f not in by_name or by_name[f].is_dir(): raise ProjectImportError(f"The project archive is incomplete: '{rel.name}' is listed but not in it. Nothing was imported.")
            p = _clean_manifest(p, dropped)
            wanted = set(files); ignored = [n for n in by_name if n != 'project.json' and not n.endswith('/') and n not in wanted]
            total = sum(by_name[f].file_size for f in files)
            _sweep_staging(data_root)
            staging.mkdir(parents=True, exist_ok=False)
            mapping = {}; done = len(raw)
            for n, f in enumerate(files):
                _stop_if(cancel)
                info = by_name[f]; name = PurePosixPath(f).name
                # A path made here: <staging>/inputs/<number>/<file name>. Only the file name is taken from the archive.
                sub = Path('inputs') / f'{n + 1:04d}'; dest = staging / sub / name
                if os.path.commonpath([os.path.realpath(dest), os.path.realpath(staging)]) != os.path.realpath(staging): raise ProjectImportError('Unsafe project input path')
                dest.parent.mkdir(parents=True, exist_ok=False)
                written = 0
                with z.open(info) as srcf, open(dest, 'xb') as out:
                    while True:
                        _stop_if(cancel)
                        chunk = srcf.read(_CHUNK)
                        if not chunk: break
                        written += len(chunk); done += len(chunk)
                        # Counted as it comes out of the archive: what the archive says about its sizes is not relied on.
                        if written > lim['file']:
                            raise ProjectImportError(f"'{name}' is larger than {_size_text(lim['file'])}, the limit for one file of a project." + _raise_hint('OPS_IMPORT_MAX_FILE_MB'))
                        if done > lim['total']:
                            raise ProjectImportError(f"Project is larger than {_size_text(lim['total'])}, the limit for one project." + _raise_hint('OPS_IMPORT_MAX_TOTAL_MB'))
                        if written > lim['ratio_floor'] and written > lim['ratio'] * max(info.compress_size, 1):
                            raise ProjectImportError(f"'{name}' unpacks to more than {lim['ratio']:g} times its packed size, which measurement files do not do." + _raise_hint('OPS_IMPORT_MAX_RATIO'))
                        out.write(chunk)
                        if progress:
                            try: progress(done, total)
                            except Exception: pass
                mapping[f] = str(root / sub / name)
        _stop_if(cancel)
        os.replace(staging, root); moved = True                     # all of it is there: one rename puts it in place
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
        projects[slug] = p; _save(projects)
        result = ImportResult(slug, dropped=list(dict.fromkeys(dropped)), ignored=ignored, files=len(files), size=total, name=p['name'])
        LAST_IMPORT.clear(); LAST_IMPORT.update(slug=slug, name=p['name'], dropped=result.dropped, ignored=result.ignored, files=result.files, bytes=result.bytes)
        return result
    except BaseException as e:
        # Whatever went wrong: the staging folder goes, a folder already moved into place goes too (its project was
        # not saved), and the projects that existed are as they were.
        shutil.rmtree(staging, ignore_errors=True)
        if moved: shutil.rmtree(root, ignore_errors=True)
        if isinstance(e, (zipfile.BadZipFile, zlib.error, EOFError, struct.error, NotImplementedError)) or (isinstance(e, RuntimeError) and not isinstance(e, RecursionError) and 'password' in str(e).lower()):
            raise ProjectImportError(_DAMAGED) from None
        if isinstance(e, MemoryError):
            raise ProjectImportError('The project is too large for the memory of this computer. Nothing was imported.') from None
        if isinstance(e, OSError) and not moved:
            raise ProjectImportError(f'The project could not be unpacked ({e.strerror or type(e).__name__}): is the disk full or the settings folder not writable? Nothing was imported.') from None
        raise


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
