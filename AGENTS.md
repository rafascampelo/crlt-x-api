# Ctrl X — Backend Codex Instructions

## Mission
Build a patient-first physical health monitoring API, using Python/FastAPI, SQLAlchemy 2, Alembic, MySQL 8.4 and pytest. Work in small, reviewable increments.

## Architecture
- Keep `api/v1` (HTTP), `schemas` (validation), `services` (business rules), `repositories` (persistence), `models` (ORM), `core` (security/config) separate.
- Use UUIDs as public resource identifiers. CPF is optional/protected identity data, never a primary key or exposed in logs.
- Every schema change requires an Alembic migration. Never use `create_all()` as production migration strategy.
- Use UTC-aware timestamps; convert in UI. Use explicit DB transactions.
- Use `/api/v1` for application endpoints; keep `/health` for liveness.
- Use environment variables via pydantic-settings; never commit `.env` or secrets.

## Privacy and authorization (non-negotiable)
- Health data is sensitive under LGPD. Use fake data in local tests and seed scripts.
- Enforce authorization on EVERY backend read/write by patient identity and active professional link; never trust frontend visibility or client-supplied patient IDs.
- Only one active professional link per patient; enforce atomically at DB/service level to avoid races.
- Keep historical professional links and authorship after revocation; revoke future access.
- Patient can edit their diary, not professional prescriptions; professional cannot edit patient diary.
- Document permissions are explicit, not automatically unrestricted by a professional link.
- Store uploads outside public/static folders; randomized storage keys; validate MIME, extension, file signatures and size; block traversal; no public URLs.
- OCR is untrusted extracted text requiring human review. Never turn OCR text into diagnoses or prescriptions automatically.
- Avoid logging PII, tokens, document text, medical records. Add audit events for sensitive access and changes.
- Use Argon2 password hashing and short-lived authenticated sessions/tokens; add tests for IDOR and revoked access.

## Quality gates
- Add pytest tests for happy path, validation, ownership, unauthorized and revoked cases.
- Run `python -m pytest` and `python -m ruff check .` before claiming a task done.
- Return changed files, commands executed, results, and remaining risks.
- Do not introduce cloud deployment, AI diagnosis, extra frameworks or unrelated features without approval.

## P0: Native digital clinical records
- Authorized active professional can create a structured clinical record for a linked patient without uploading a file. This is distinct from documents and OCR.
- Model `clinical_records` with patient_id, professional_id, status (draft/finalized), complaint, anamnesis, physical_assessment, body_region, pain_intensity (nullable 0–10), functional_limitations, therapeutic_goals, care_plan, notes, created_at, updated_at, finalized_at. Adapt fields via schemas, not free-form HTML.
- Only the authoring professional with an active link may edit drafts. Finalized records are immutable; corrections use append-only amendments with author, timestamp and reason. Never hard-delete finalized records.
- Preserve record and author when link is revoked; block professional's subsequent access unless reauthorized. Patient may read their own records.
- Emit finalized records as timeline events sourced from clinical_records, not duplicated history rows. Log create, view, edit, finalize and amendment actions without storing clinical contents in audit logs.
- Test patient isolation, unauthorized professionals, revoked links, draft/finalized transitions, validation and immutability.

Native clinical records are first-class structured entities in the patient's longitudinal health record, not PDFs, uploaded documents, or OCR results. Clinical records, pain diary entries, exercise prescriptions and progress tracking must be independently persisted but linked through patient identity and appropriate relational references. Dashboard, timeline and calendar are views over these existing entities, not duplicated data. Design the schema to support future relationships between assessments, prescriptions and patient outcomes without implementing speculative features now.