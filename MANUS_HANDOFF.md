# Manus handoff — ProjectFlow MVP

## Mission
Deploy the provided source, not recreate it. Preserve code and report every required change. This is an MVP only, not production-ready.

1. Read `README.md` and inspect `app.py` and `static/index.html`.
2. Run locally, test health endpoint, create initial admin, and execute complete sample workflow.
3. Before any public release, implement CSRF protection, setup lockout, account provisioning, login rate limits, authorization for documents, schema migrations, error handling, and backup/restore testing.
4. Provision persistent storage and HTTPS; never put `.env` or credentials in the repository.
5. Configure DNS and reverse proxy. Confirm container persists across restarts.
6. Set up off-server encrypted backups for database and uploads; test restoration.
7. If asked to connect Google Drive or Gmail, use user-authorized OAuth with least privilege; implement integration as a separate feature. Do NOT claim connected by default.
8. For real finance usage, implement full 3-way matching, approvals, multi-line POs, audit protections, project milestone certification, and automated tests before production.
9. Return deployment URL, admin onboarding procedure, backup location, exact costs, and known risks.

## Critical caveat
The current app is a functional prototype for workflow evaluation, not a compliant accounting system. Do not enter actual client financial data before security and accounting controls are validated.
