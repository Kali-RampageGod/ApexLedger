# ApexLedger

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20.svg)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-red.svg)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![Auth](https://img.shields.io/badge/Auth-JWT%20%28HttpOnly%20Cookie%29-black.svg)](https://django-rest-framework-simplejwt.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A digital banking backend built on an immutable double-entry ledger.**

ApexLedger is a REST API built with Django REST Framework and PostgreSQL. It has no stored balance column. Every rupee movement is an append-only ledger entry, and balances are computed from those entries at query time. Transfers run inside atomic database transactions with row-level locks, so concurrent requests cannot overdraw an account.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Core Design Principles](#core-design-principles)
- [Data Model](#data-model)
- [Authentication and Security](#authentication-and-security)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Usage Walkthrough](#usage-walkthrough)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Immutable double-entry ledger**: every deposit and transfer is a permanent record, and entries are never edited or deleted.
- **Zero static balances**: balances are aggregated from ledger rows on every read, so they cannot drift out of sync.
- **Multi-pocket wallets**: each user can hold up to three accounts (`PRIMARY`, `SAVINGS`, `RESERVE`).
- **Atomic, race-safe transfers**: `transaction.atomic()` plus `select_for_update()` serialises concurrent debits on the same account.
- **Exact money arithmetic**: amounts use `DecimalField(max_digits=12, decimal_places=2)`, never floats.
- **Cookie-based JWT authentication**: access tokens live in HttpOnly cookies, out of reach of client-side JavaScript.
- **Tenant isolation**: every query is scoped to the authenticated user, so cross-user access returns `404` or `403`.
- **Audit trail**: `PROTECT` foreign keys keep history intact even when an account is deactivated.
- **Filtering support** through `django-filter` and structured logging through `loguru`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.0.6, Django REST Framework 3.15.1 |
| Authentication | djangorestframework-simplejwt 5.3.1, PyJWT |
| Database | PostgreSQL via psycopg2-binary |
| Filtering | django-filter 24.2 |
| Logging | loguru 0.7.2 |
| Configuration | python-dotenv |

---

## Architecture

```text
            ┌──────────────────────────────────────────┐
            │        Client (Postman / Web UI)         │
            └────────────────────┬─────────────────────┘
                                 │  HTTPS (JSON)
                                 │  HttpOnly cookie: access_token
                                 ▼
            ┌──────────────────────────────────────────┐
            │          Django REST Framework           │
            │     CustomCookieJWTAuthentication        │
            └────────────────────┬─────────────────────┘
                                 │
                                 │  transaction.atomic()
                                 │  select_for_update() on source account
                                 ▼
            ┌──────────────────────────────────────────┐
            │              PostgreSQL                  │
            │  authentication_user                     │
            │  accounts_assetaccount   (pockets)       │
            │  accounts_ledgertransaction (ledger)     │
            └──────────────────────────────────────────┘
```

Identity (`authentication`) and money movement (`accounts`) live in separate Django apps. This keeps authentication concerns apart from transaction logic.

---

## Core Design Principles

### 1. Double-entry bookkeeping with dynamic aggregation

A mutable `balance` column invites write races, phantom reads and silent divergence. ApexLedger stores only immutable ledger rows and derives the balance:

$$\text{Balance}(p) = \sum_{tx \in \mathcal{C}} \text{amount}(tx) - \sum_{tx \in \mathcal{D}} \text{amount}(tx)$$

- $\mathcal{C}$ is every transaction where `destination_account = p` (credits).
- $\mathcal{D}$ is every transaction where `source_account = p` (debits).

### 2. Atomic transfers with pessimistic locking

Each transfer runs inside `django.db.transaction.atomic`:

1. The source account row is locked with `select_for_update()`.
2. Its current balance is aggregated from the ledger.
3. If funds are insufficient, the request is rejected and nothing is written.
4. Otherwise a single ledger entry is committed.

Concurrent transfers from the same account queue behind the lock. If any step fails, the whole block rolls back.

### 3. Tri-pocket allocation limit

A user may hold at most **three** active asset accounts. The limit is checked before any insert, and exceeding it returns `400 Bad Request`.

---

## Data Model

```text
 ┌──────────────────────────┐          ┌─────────────────────────────────┐
 │  authentication.User     │ 1      N │  accounts.AssetAccount          │
 ├──────────────────────────┤──────────├─────────────────────────────────┤
 │ PK id (BigInt)           │          │ PK id (UUID4)                   │
 │    email (unique)        │          │ FK user_id                      │
 │    first_name            │          │    account_number (Char 16)     │
 │    last_name             │          │    account_type (Enum)          │
 │    is_active             │          │    currency (Char 3, INR)       │
 │    date_joined           │          │    is_active                    │
 └──────────────────────────┘          └───────────────┬─────────────────┘
                                                       │ 1  (source / destination)
                                                       ▼ N
                                       ┌─────────────────────────────────┐
                                       │  accounts.LedgerTransaction     │
                                       ├─────────────────────────────────┤
                                       │ PK id (UUID4)                   │
                                       │ FK source_account_id (nullable) │
                                       │ FK dest_account_id (nullable)   │
                                       │    tx_type (Enum)               │
                                       │    amount (Decimal 12,2)        │
                                       │    description (Text)           │
                                       │    timestamp (DateTime)         │
                                       └─────────────────────────────────┘
```

**Invariants**

- `account_number` is a 16-digit string generated with Python's `secrets` module, with a uniqueness check.
- `amount` is always `Decimal`, which avoids binary floating-point errors.
- Ledger foreign keys use `on_delete=models.PROTECT`, so history survives account deactivation.
- Deposits have no source account, so `source_account` is null for them.

---

## Authentication and Security

| Concern | Approach |
|---|---|
| Session model | Stateless JWT delivered in an HttpOnly cookie |
| XSS | The token is not readable through `document.cookie` |
| CSRF | `SameSite=Lax`, with `Secure` enabled in production |
| Request auth | `CustomCookieJWTAuthentication` reads `access_token` from cookies, validates the signature and attaches `request.user` |
| Data isolation | Every view filters by the requesting user |

Isolation pattern used across views:

```python
def get_queryset(self):
    return AssetAccount.objects.filter(user=self.request.user, is_active=True)
```

---

## API Reference

Base path: `/api/`. Endpoints marked **Cookie** require a prior login.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| POST | `/api/auth/register/` | Public | Create a user and provision the initial `PRIMARY` account |
| POST | `/api/auth/login/` | Public | Authenticate and set the `access_token` cookie |
| GET | `/api/ledger/pockets/` | Cookie | List the user's accounts with computed balances |
| POST | `/api/ledger/pockets/` | Cookie | Create an additional pocket (maximum 3) |
| POST | `/api/ledger/transfer/` | Cookie | Move funds between two accounts |
| GET | `/api/ledger/history/` | Cookie | Transaction history (audit trail) |

### Register

`POST /api/auth/register/`

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "Jane",
  "last_name": "Doe",
  "account_type": "PRIMARY"
}
```

Response `201 Created`:

```json
{
  "id": 1,
  "email": "user@example.com",
  "message": "User registered successfully with initial primary account provisioned."
}
```

### Login

`POST /api/auth/login/`

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

Response `200 OK`, with `Set-Cookie: access_token=...; HttpOnly; Path=/; SameSite=Lax`.

### List pockets

`GET /api/ledger/pockets/` returns `200 OK`:

```json
[
  {
    "id": "f5a7c25a-92ba-4568-b8cb-e8f33f021eaa",
    "account_number": "6926494499175453",
    "account_type": "PRIMARY",
    "currency": "INR",
    "balance": "10000.00",
    "created_at": "2026-07-07T08:53:23.710703Z"
  }
]
```

### Create a pocket

`POST /api/ledger/pockets/`

```json
{
  "account_type": "SAVINGS"
}
```

Returns `201 Created`, or `400 Bad Request` if the user already holds three accounts.

### Transfer funds

`POST /api/ledger/transfer/`

```json
{
  "source_account_number": "6926494499175453",
  "destination_account_number": "5977299413206982",
  "amount": "2500.00",
  "description": "Transfer to Emergency Savings"
}
```

Response `200 OK`:

```json
{
  "status": "SUCCESS",
  "transaction_id": "8c41ec35-430b-4028-9104-e0e641774e14",
  "amount": "2500.00",
  "timestamp": "2026-07-07T14:55:00.123456Z"
}
```

### Transaction history

`GET /api/ledger/history/` returns `200 OK`:

```json
[
  {
    "id": "8c41ec35-430b-4028-9104-e0e641774e14",
    "transaction_type": "TRANSFER",
    "source_account": "6926494499175453",
    "destination_account": "5977299413206982",
    "amount": "2500.00",
    "description": "Transfer to Emergency Savings",
    "timestamp": "2026-07-07T14:55:00.123456Z"
  }
]
```

---

## Project Structure

```text
ApexLedger/
├── .gitignore
├── requirements.txt
└── Core_project/
    ├── manage.py
    ├── Core_project/
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── authentication/
    │   ├── migrations/
    │   ├── authenticate.py
    │   ├── models.py
    │   ├── serializers.py
    │   ├── urls.py
    │   └── views.py
    └── accounts/
        ├── migrations/
        ├── models.py
        ├── serializers.py
        ├── urls.py
        └── views.py
```

---

## Getting Started

### Prerequisites

- Python 3.12 or newer
- PostgreSQL 15 or newer, running locally
- `git` and `pip`

### 1. Clone the repository

```bash
git clone https://github.com/Kali-RampageGod/ApexLedger.git
cd ApexLedger
```

### 2. Create and activate a virtual environment

Linux or macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE fintech_ledger;"
```

### 5. Configure environment variables

Create a `.env` file next to `manage.py` (inside `Core_project/`):

```env
SECRET_KEY=replace-with-a-long-random-string
DEBUG=True
DB_NAME=fintech_ledger
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

### 6. Apply migrations

```bash
cd Core_project
python manage.py makemigrations authentication accounts
python manage.py migrate
```

### 7. Start the development server

```bash
python manage.py runserver
```

The API is now available at `http://127.0.0.1:8000/api/`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key. Use a unique random value outside development. |
| `DEBUG` | Yes | `True` for development, `False` in production. |
| `DB_NAME` | Yes | PostgreSQL database name. |
| `DB_USER` | Yes | PostgreSQL user. |
| `DB_PASSWORD` | Yes | PostgreSQL password. |
| `DB_HOST` | Yes | Database host, for example `127.0.0.1`. |
| `DB_PORT` | Yes | Database port, usually `5432`. |

Never commit your `.env` file. It is already covered by `.gitignore`.

---

## Usage Walkthrough

Every step below works from a terminal with `curl`.

**1. Register**

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePassword123!","first_name":"Jane","last_name":"Doe","account_type":"PRIMARY"}'
```

**2. Log in and store the cookie**

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email":"user@example.com","password":"SecurePassword123!"}'
```

**3. Create a savings pocket**

```bash
curl -X POST http://127.0.0.1:8000/api/ledger/pockets/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"account_type":"SAVINGS"}'
```

**4. List pockets and balances**

```bash
curl http://127.0.0.1:8000/api/ledger/pockets/ -b cookies.txt
```

**5. Transfer funds between pockets**

```bash
curl -X POST http://127.0.0.1:8000/api/ledger/transfer/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"source_account_number":"<source>","destination_account_number":"<destination>","amount":"2500.00","description":"Move to savings"}'
```

**6. View history**

```bash
curl http://127.0.0.1:8000/api/ledger/history/ -b cookies.txt
```

### Seeding development funds

A new account starts at zero. To give it a starting balance, open a Django shell with `python manage.py shell` and run:

```python
from decimal import Decimal
from django.contrib.auth import get_user_model
from accounts.models import AssetAccount, LedgerTransaction

user = get_user_model().objects.get(email="user@example.com")
account = AssetAccount.objects.get(user=user, account_type="PRIMARY")
LedgerTransaction.objects.create(
    tx_type="DEPOSIT",
    destination_account=account,
    amount=Decimal("10000.00"),
    description="Development seed deposit",
)
```

---

## Running Tests

From the `Core_project/` directory:

```bash
python manage.py test
```

---

## Roadmap

- [ ] Asynchronous email receipts and audit jobs through Celery with a Redis broker
- [ ] Read-through cache for aggregated balances, invalidated on new ledger commits
- [ ] Throttling with DRF `ScopedRateThrottle` (auth endpoints and transfers)
- [ ] Idempotency keys for transfer requests
- [ ] Interactive API docs (OpenAPI / Swagger)
- [ ] Dockerfile and `docker-compose.yml` for one-command setup
- [ ] CI pipeline running tests on every push
- [ ] Metrics and monitoring (Prometheus, Grafana)

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Commit your changes with a clear message.
4. Push the branch and open a pull request.

Please include tests for any change that touches ledger or transfer logic.

---

## License

Released under the [MIT License](https://opensource.org/licenses/MIT). Add a `LICENSE` file to the repo root so GitHub detects it.

---

## Author

**Kali-RampageGod**: [GitHub](https://github.com/Kali-RampageGod)