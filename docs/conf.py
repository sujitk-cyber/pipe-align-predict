"""Sphinx configuration for ILI Pipeline documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "ILI Pipeline Alignment"
author = "pipe-align-predict"
release = "1.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False

templates_path = ["_templates"]
exclude_patterns = ["_build"]

html_theme = "alabaster"
html_static_path = ["_static"]
