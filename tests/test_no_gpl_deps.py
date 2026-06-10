"""Regression guard: GPL-licensed graph libraries must not be installed.

SourcePrep ships under a permissive license (target: Apache 2.0). The
``igraph`` (GPL-2.0) and ``leidenalg`` (GPL-3.0-or-later) libraries
were removed in the Phase 144 GPL dependency replacement. This test
fails if either reappears in the environment so the contamination
cannot return unnoticed.

If you have a legitimate need for community detection, use
``networkx.algorithms.community.louvain_communities`` instead.
"""
import importlib

import pytest


@pytest.mark.parametrize("modname", ["igraph", "leidenalg"])
def test_gpl_dep_not_installed(modname: str) -> None:
    with pytest.raises(ImportError):
        importlib.import_module(modname)
