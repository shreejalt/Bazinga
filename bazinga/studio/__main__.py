"""``python -m bazinga.studio`` starts the Editor (the same as ``python -m bazinga editor``)."""
import sys

from .server import main

sys.exit(main())
