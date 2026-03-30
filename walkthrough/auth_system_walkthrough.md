# Aurora Blings — Authentication System Walkthrough

## App File Structure

```
backend/apps/accounts/
├── __init__.py
├── apps.py           ← AppConfig + signal registration
├── managers.py       ← CustomUserManager (email-based, no username)
├── models.py         ← User · Address · LoginAttempt
├── selectors.py      ← Read-only ORM queries (no mutation)
├── services.py       ← All auth business logic
├── serializers.py    ← Input/output shapes, no business logic
├── permissions.py    ← IsAdminUser · IsStaffOrAdmin · IsOwnerOrAdmin
├── views.py          ← Thin API views (validate → service → respond)
├── urls.py           ← URL patterns
├── tasks.py          ← Celery async email tasks
└── signals.py        ← Post-save audit logging
```

---

## API Endpoints

| Method | URL | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Public | Create account |
| `POST` | `/api/v1/auth/login/` | Public | Get tokens |
| `POST` | `/api/v1/auth/logout/` | JWT | Blacklist refresh token |
| `POST` | `/api/v1/auth/token/refresh/` | Public | Rotate access token |
| `POST` | `/api/v1/auth/password/reset/` | Public | Request reset email |
| `POST` | `/api/v1/auth/password/reset/confirm/` | Public | Set new password via token |
| `POST` | `/api/v1/auth/password/change/` | JWT | Change password (logged in) |
| `GET/PATCH` | `/api/v1/auth/profile/` | JWT | View / update own profile |
| `GET/POST` | `/api/v1/auth/addresses/` | JWT | List / create addresses |
| `GET/PATCH/DELETE` | `/api/v1/auth/addresses/{id}/` | JWT + Owner | Address detail |

---

## User Model Fields

```python
class User(AbstractBaseUser, PermissionsMixin):
    id                    # UUID4 primary key
    email                 # unique, login identifier
    first_name, last_name
    phone
    role                  # admin | staff | customer
    is_active, is_staff, is_email_verified
    failed_login_attempts # brute-force counter
    last_failed_login     # timestamp
    locked_until          # account unlock time
    password_reset_token  # SHA-256 hash only
    password_reset_expires
    date_joined, updated_at
```

---

## JWT Token Flow

```
POST /api/v1/auth/login/
Body: { "email": "...", "password": "..." }

Response:
{
  "success": true,
  "data": {
    "access":  "<30-min JWT>",
    "refresh": "<7-day JWT>",
    "user": { "id": "...", "email": "...", "role": "customer" }
  }
}
```

All subsequent requests:
```
Authorization: Bearer <access_token>
```

Refresh:
```
POST /api/v1/auth/token/refresh/
Body: { "refresh": "<token>" }
```

Logout blacklists the refresh token permanently:
```
POST /api/v1/auth/logout/
Body: { "refresh": "<token>" }
```

---

## Login Security

### Brute-Force Lockout

| Threshold | Behaviour |
|---|---|
| 1–4 failed attempts | Error with remaining attempts count |
| 5 failed attempts | Account locked for **30 minutes** |
| During lockout | `403 PermissionDenied` with unlock time |
| Successful login | Counter resets to 0 |

### Rate Limiting (django-ratelimit)

All auth endpoints (login, register, password reset): **10 requests / minute per IP**.

```python
@method_decorator(ratelimit(key="ip", rate="10/m", block=True))
def post(self, request): ...
```

### LoginAttempt Audit Log

Every attempt (success + failure) is stored:
```python
LoginAttempt(
    email=email,
    ip_address="1.2.3.4",
    user_agent="Mozilla/...",
    successful=False,
    failure_reason="wrong_password",
    attempted_at=<timestamp>
)
```

---

## Password Reset Flow

```
1. POST /password/reset/      { "email": "..." }
   → Generates random token (urlsafe 32 bytes)
   → Stores SHA-256 hash in DB (2-hour expiry)
   → Queues send_password_reset_email Celery task
   → Response: always 200 (prevents email enumeration)

2. User clicks link: https://aurorablings.com/auth/reset-password?token=<raw_token>

3. POST /password/reset/confirm/   { "token": "...", "new_password": "..." }
   → Hashes token, looks up user
   → Validates password strength
   → Sets new password, clears token + lockout state
```

> **Security**: Only the SHA-256 hash is stored in the DB. The raw token only exists in the email link. Even if DB is compromised, tokens cannot be used.

---

## Role-Based Permissions

```python
from apps.accounts.permissions import IsAdminUser, IsStaffOrAdmin, IsOwnerOrAdmin

class AdminOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

class StaffDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

class UserOwnResourceView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    # Object must have a .user FK attribute
```

---

## Services / Selectors Pattern

```python
# ✅ Correct: views never touch ORM directly
from apps.accounts import services, selectors

class ProfileView(APIView):
    def get(self, request):
        user = selectors.get_user_by_id(request.user.id)  # selector: read
        return success_response(data=UserProfileSerializer(user).data)

    def post(self, request):
        user = services.register_user(**validated_data)    # service: write
        return success_response(data=...)
```

---

## Migrations & Setup Commands

```bash
# After setting up the virtual env and installing requirements:

# 1. Create initial migration for custom user model
python manage.py makemigrations accounts

# 2. Apply all migrations
python manage.py migrate

# 3. Create a superuser
python manage.py createsuperuser
# (uses email + password — no username prompt)

# 4. Start Celery worker for email tasks
celery -A config worker --loglevel=info
```

---

## Security Checklist

- [x] Passwords hashed via Django's `set_password()` (PBKDF2-SHA256)
- [x] Reset tokens stored as SHA-256 hash only
- [x] Reset responses always 200 (prevent enumeration)
- [x] Account lockout after 5 failed attempts (30 min)
- [x] JWT access tokens expire in 30 minutes
- [x] Refresh tokens rotate on use + blacklisted on logout
- [x] All auth endpoints rate-limited at 10 req/min per IP
- [x] Every auth event logged with structlog (request_id included)
- [x] LoginAttempt audit trail with IP + user agent
- [ ] TODO: Email verification flow (token via email after register)
- [ ] TODO: 2FA / TOTP (pluggable via django-otp)
