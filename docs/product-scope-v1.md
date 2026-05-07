# Product Scope v1.0 (MVP)

## Roles
- `admin`: full access to settings, uploads, users, and audit.
- `lead`: read access to dashboards, calls, and call cards.
- `manager`: read access to own calls and own score details.

## Screens
- `auth/login`: email/password login.
- `dashboard`: KPI summary, trends, distributions, and filters.
- `calls/list`: calls table with filter panel.
- `calls/card`: transcript + score breakdown.
- `uploads/list`: upload history and processing statuses.
- `uploads/new`: manual CSV/audio upload.
- `settings/score-template`: scoring template builder (sections/questions/answers/weights).
- `settings/users`: user roles management (admin only).
- `audit/logs`: template and settings change history.

## Access matrix
- `admin`: all screens.
- `lead`: dashboard, calls/list, calls/card, uploads/list.
- `manager`: calls/list, calls/card (own only).

## Explicitly out of scope for v1
- CRM or telephony integrations.
- Automated scheduled imports.
- Multi-tenant organizations.
- Advanced AI coaching recommendations.
