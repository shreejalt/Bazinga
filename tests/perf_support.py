"""Speed checks are kept out of the deploy suite (vercel.json, netlify.toml and the Pages workflow all run the tests
before building, and a busy build machine must not fail a deploy on a commit that changed a post).

Run them with ``BAZINGA_PERF_TESTS=1 python -m unittest discover tests``. Without it, every wall-clock assertion is
skipped and the figure test's time budget is switched off (BAZINGA_FIGURE_BUDGET_MS=inf, inherited by the worker
processes the Editor tests start); the correctness checks always run."""
import os
import unittest

PERF = os.environ.get("BAZINGA_PERF_TESTS") == "1"
if not PERF:
    os.environ.setdefault("BAZINGA_FIGURE_BUDGET_MS", "inf")

perf_only = unittest.skipUnless(PERF, "speed check: run with BAZINGA_PERF_TESTS=1")
