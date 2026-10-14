# ProjectFlow — portable functional MVP

A small FastAPI + SQLAlchemy + responsive vanilla-JS application based on the supplied Procure-to-Pay and Sale-to-Receipt proposal. This is **not a production-ready financial ERP**.

## Features implemented
- Initial admin account setup and password-based login; role checks for write endpoints (other roles require provisioning)
- Projects and single-line purchase orders
- Partial deliveries and partial certification with balance checks
- Supplier invoices capped at certified PO line value (simplified invoice control, **not** a 3-way match)
- Client invoices (without milestone certification yet)
- Partial supplier payments and client receipts with outstanding balances
- Local PDF/image evidence upload/download
- Audit event log and responsive dashboard
- Portable SQLite database and Docker deployment

## Not implemented
- True 3-way match; finance approval/recommendation workflow; multi-line PO; project milestone application and external client certification; Google Drive/Gmail/SharePoint integrations; automatic PDF creation; email reminders; currency conversion; self-service user administration; background jobs; recurring invoices; production backup automation; full financial-grade auditing, concurrency, security, and tests.
- Sequential PO numbering: this MVP uses unique UUID-derived PO numbers instead.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export SESSION_SECRET=$(python -c 'import secrets;print(secrets.token_hex(32))')
export COOKIE_SECURE=0
uvicorn app:app --reload
```
Open http://localhost:8000. Create the initial admin account (minimum 12-character password). API docs at `/docs`.

## Docker / Manus deployment
1. Copy `.env.example` to `.env`, generate a strong `SESSION_SECRET` (never commit it).
2. Set up HTTPS reverse proxy (Caddy or Nginx). `COOKIE_SECURE=1` requires HTTPS.
3. Run `docker compose up -d --build`.
4. Reverse proxy to `127.0.0.1:8000`; ensure persistent `./data` volume is backed up.
5. Visit site and create initial admin before giving public access.
6. Test login, create project/PO, partial delivery, certification, invoice and payment.

**Security warning:** This MVP needs CSRF hardening, account provisioning, rate limiting, stronger authorization, secure document policy, recovery, migrations, and deployment review before exposure to the internet or use with real financial information. Initial setup must not be left publicly available before admin provisioning. SQLite is intended for low-volume testing; migrate to PostgreSQL for serious multi-user operations.

## Data
Default SQLite file: `data/projectflow.db`; uploaded evidence: `data/uploads/`. Back up both together. No external services are connected.
