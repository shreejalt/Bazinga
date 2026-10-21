"""``python -m bazinga.studio`` starts the Studio (the same as ``python -m bazinga studio``)."""
import sys

from .server import main

sys.exit(main())
