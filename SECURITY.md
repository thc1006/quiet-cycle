# Security and privacy

The library processes the data supplied by the caller. It does not fetch, encrypt,
persist, or transmit records unless the caller explicitly uses file output or the
optional HTTP adapter. That is a boundary, not a promise of end-to-end privacy.
Your application owns consent, access control, storage encryption, deletion,
backups, request limits, audit policy, and any regulatory obligations.

Use pseudonymous identifiers. Source identifiers and exported records can still be
sensitive. Never attach patient records, access tokens, backups, or medical notes to
public issues. Reproduce problems with synthetic input. CLI/HTTP input errors are
redacted; direct Pydantic errors and debugging tools can include supplied values.

The HTTP adapter binds locally in examples and has no built-in authentication.
Do not expose it directly to the internet. Custom plugins execute with the host
process's privileges. Do not load untrusted Python code or deserialize pickle files.
No remote resources are followed by the FHIR adapter.

For this unpublished handoff, report suspected problems privately to the repository
owner. Before making a public repository, configure a private security-reporting
channel and replace this paragraph with its actual route. No mailbox is invented here.

AI-assisted implementation is not independent review. The test report distinguishes
executed checks from configured or unavailable checks. No professional security,
clinical, or legal certification is implied.

## Fitted artifacts (0.3)

Model JSON contains fitted statistics, calibration scores and hashed subject audit
tokens. It is not anonymous or differentially private. Protect the model and the
fit request as sensitive derived data, including backups and CI attachments. The
built-in SHA256 is integrity/audit metadata, not an authenticity signature; use a
trusted distribution channel or host-level signature policy.

The learned HTTP route binds a model at startup. It never accepts model code,
pickles or remote artifact URLs from a request. Training is not exposed over HTTP.
Exact matrix calculations have budgets but are CPU/memory work: run authorized
training in controlled jobs rather than as arbitrary public requests. Do not share
training records with development agents unless separately authorized.
