# Sphinx Configuration for Cerberus Python API Documentation
# Automated documentation generation

import os
import sys
sys.path.insert(0, os.path.abspath('../../backend'))

project = 'Cerberus CTF Platform'
copyright = '2024, Cerberus Team'
author = 'Cerberus Team'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.coverage',
    'sphinx.ext.githubpages',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_logo = '_static/cerberus-logo.png'

html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
}

autodoc_default_options = {
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'show-inheritance': True,
}

autodoc_mock_imports = [
    'databases',
    'redis',
    'prometheus_client',
    'structlog',
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True

# Coverage settings
coverage_show_missing_items = True

# Mermaid diagram support
extensions.append('sphinx.ext.graphviz')
graphviz_dot = 'dot'
graphviz_html_output_format = 'svg'
