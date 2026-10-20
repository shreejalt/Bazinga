# Third-party software and assets

Tessera's own code is MIT-licensed (see `LICENSE`). It installs, loads or links to the following, each under its own
licence. Nothing below is copied into this repository; versions are pinned in `requirements.txt` and `tessera/vendor.py`.

| Component | Used for | Licence |
|---|---|---|
| [Python-Markdown](https://github.com/Python-Markdown/markdown) | Markdown → HTML at build time | BSD-3-Clause |
| [PyYAML](https://github.com/yaml/pyyaml) | front matter and configuration | MIT |
| [Jinja2](https://github.com/pallets/jinja) | page templates | BSD-3-Clause |
| [latex2mathml](https://github.com/roniemartinez/latex2mathml) | LaTeX → MathML at build time | MIT |
| [Pygments](https://github.com/pygments/pygments) | code highlighting at build time | BSD-2-Clause |
| [NumPy](https://numpy.org) (optional, for figures that declare it) | figure maths | BSD-3-Clause |
| [Pyodide](https://github.com/pyodide/pyodide) (loaded from jsDelivr in the reader's browser) | re-running figures and Ask in the browser | MPL-2.0 |
| [CodeMirror 6](https://codemirror.net) (loaded from esm.sh, Studio only) | the Studio's editor | MIT |
| [STIX Two Math / Text](https://github.com/stipub/stixfonts), [Source Serif 4](https://github.com/adobe-fonts/source-serif), [Inter](https://github.com/rsms/inter), [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) (Google Fonts) | typography | SIL Open Font License 1.1 |
