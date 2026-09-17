# Release procedure

This repository has not been published to PyPI or an owned public repository.
Check name ownership, contributor attribution, a private reporting channel, and
actual repository URLs before publication. Do not upload under a guessed owner.

1. Update version, model/contract identifiers when needed, and the changelog.
2. Install the development extras in a clean environment. Run unit/property/
   reference tests, schema drift checks, mypy, Ruff, and installed-artifact tests.
3. Build with `python -m build`; inspect both wheel and sdist. The wheel must include
   py.typed and schemas but no tests, frontend, secrets, or health data.
4. Install the wheel into a new environment outside the checkout and execute the
   public examples and CLI. Test API extras separately. Check Python/OS matrix CI.
5. Review README metadata and generated OpenAPI. Replace only real repository/
   documentation URLs; do not invent a DOI or validation badge.
6. Publish only after maintainer approval. Prefer PyPI Trusted Publishing with
   repository/environment identity controls over long-lived API tokens. Configure
   it at PyPI and GitHub; copying a workflow does not authorize publication.
7. Archive hashes, dependency versions, test evidence, and the signed release tag.

No automated publish workflow is enabled in this handoff. CI builds and checks
artifacts only. `scripts/build_local.py` invokes the standard setuptools PEP 517
backend directly for an already provisioned environment; it is not dependency
isolation and should not replace the clean release build.

The library supports a dependency range for consumers. Research deployments should
resolve and record an exact environment. `evidence/environment.json` describes this
handoff's tested environment, not a universal cross-platform lock file.
