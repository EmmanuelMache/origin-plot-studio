"""Graph = Template (layout + data roles) x Style (look) x Data (the user's file mapped to roles).
The contracts are opstudio.template/1 and opstudio.style/1 (see templates/*.json and styles/*.json)."""
from . import core
from .core import REGISTRY, render, save, load_style, template_json, STYLE_DIRS
from . import templates_materials, templates_general      # noqa: F401  (they register the templates)
from . import data, api                                  # noqa: F401
from .api import draw, Unfit, recommend, styles, all_templates, info
