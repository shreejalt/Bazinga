"""``python -m tessera.studio`` starts the Studio (the same as ``python -m tessera studio``)."""
import sys

from .server import main

sys.exit(main())
