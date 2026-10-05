# Security Scope

This release is a single-user local research prototype. It does not provide authentication, tenant isolation, execution quotas, or a hardened public API.

- Keep default loopback port bindings. Do not expose the service directly to the internet.
- Never commit `.env`, tokens, customer scenarios, the `runs/` database, or confidential reports.
- `VITE_` values are public build-time configuration, not secret storage.
- Basemap providers observe requested tile locations. Use an approved internal service for confidential planning.
- Back up data before upgrades and validate restoration separately.
- Do not post credentials or private datasets in public issues. Use private security reporting when available.

Production authentication, authorization, rate limiting, dependency review, penetration testing, and monitoring remain deployment requirements.
