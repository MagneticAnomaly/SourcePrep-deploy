# Walker parity fixture

Phase 133 (Rust Walker/Hasher Cutover). Each file targets one of the six
divergence surfaces or the Phase 125c forward-look. Do NOT add files
without updating `tests/test_walker_parity.py` — every file here is
load-bearing for at least one assertion.

| File | Surface | Expected behavior (default exclude set) |
|---|---|---|
| `deep/nested/path/leaf.py` | #1 glob engine — recursive `**/*.py` | included |
| `.github/workflows/ci.yml` | #2 hidden dirs | included (no default exclude for `.github/`) |
| `package-lock.json` | #3 glob anchor | excluded (`**/*.lock`-style default) |
| `sub/with_gitignore/.gitignore` | #6 nested gitignore | scaffolding for the next two |
| `sub/with_gitignore/secret.tmp` | #6 nested gitignore | excluded (per the nested .gitignore) |
| `sub/with_gitignore/visible.py` | #6 nested gitignore | included |
| `CLAUDE.md` | Phase 125c — source-indexing exclude | excluded by default; included when caller drops the AI-rule excludes |
| `.cursor/rules/sample.mdc` | Phase 125c — source-indexing exclude | excluded by default; included when caller drops the AI-rule excludes |
| `src/main.py` | control | included |
| `README.md` (this file) | control + fixture documentation | included |
