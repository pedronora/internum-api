# AGENTS.md - Internum API Project Guidelines

## Project Overview
**Internum API** - Backend for 1º Registro de Imóveis de Cascavel (PR)
- Framework: **FastAPI** (async) + **Python 3.13+**
- Database: **PostgreSQL** + **SQLAlchemy 2.0** (async) + **Alembic**
- Auth: **JWT** (access/refresh tokens in HttpOnly cookies)
- Validation: **Pydantic v2**
- Lint/Format: **Ruff** (line-length=79, preview=true, single quotes)
- Tests: **pytest** + **pytest-asyncio** + **factory-boy** + **testcontainers**
- Dependency Management: **Poetry**

---

## Architecture Patterns

### 1. Module Structure
Each domain module under `internum/modules/{module}/` follows:
```
{module}/
├── __init__.py
├── models.py        # SQLAlchemy models (dataclasses via table_registry)
├── schemas.py       # Pydantic models (request/response)
├── routers.py       # FastAPI endpoints
├── enums.py         # StrEnum definitions
├── services.py      # Business logic (optional, for complex modules)
├── jobs.py          # APScheduler jobs (optional)
└── templates.py     # Email/HTML templates (optional)
```

### 2. Model Conventions
- **Base**: `@table_registry.mapped_as_dataclass` + `AuditMixin`
- **Imports**: Use `TYPE_CHECKING` for forward references (`User`, etc.)
- **FKs**: Explicit `ForeignKey('table.column', ondelete='CASCADE/SET NULL')`
- **Enums**: `SqlEnum(EnumClass, name='enum_name')` with explicit names
- **Relationships**: Always specify `foreign_keys` when ambiguous
- **Dataclass fields**: `init=False` for PK, timestamps, relationships
- **Defaults**: Use `default=` in `mapped_column`, not Python defaults
- **Nullable optional fields**: `Mapped[Optional[T]]` + `nullable=True, default=None`

### 3. AuditMixin (all models inherit)
```python
created_at: DateTime(timezone=True), server_default=func.timezone('UTC', func.now())
updated_at: DateTime(timezone=True), onupdate=func.timezone('UTC', func.now())
deleted_at: DateTime(timezone=True), nullable=True
created_by_id, updated_by_id, deleted_by_id: FK(User, ondelete='SET NULL')
```

### 4. Schema Conventions
- **Base schemas**: `{Entity}Base`, `{Entity}Create`, `{Entity}Update`, `{Entity}Read`, `{Entity}ListItem`
- **Config**: `from_attributes = True` for ORM compatibility
- **Validation**: `field_validator` + `model_validator(mode='after')`
- **Lists**: `Field(min_length=1, max_length=N)` for bounded collections
- **Enums**: Import from module's `enums.py`

### 5. Router Conventions
- **Prefix**: `/api/v1/{module}` (set in `api/main.py`)
- **Tags**: `['ModuleName']`
- **Dependencies**: Use `Annotated[Type, Depends(...)]` for all Depends
- **Session**: `Session = Annotated[AsyncSession, Depends(get_session)]`
- **Permissions**: Import from `core.permissions` (`CurrentUser`, `VerifyAdminCoord`, etc.)
- **Error handling**: `HTTPException` with `HTTPStatus` enum
- **Naming**: `{verb}_{entity}` (`create_user`, `get_vacation_request`)

### 6. Permission System (`core/permissions.py`)
```python
CurrentUser          # authenticated user (get_current_user)
VerifySelfAdmin      # user_id == current_user.id OR role == 'admin'
VerifySelfAdminCoord # user_id == current_user.id OR role in ['admin', 'coord']
VerifyAdminCoord     # role in ['admin', 'coord']
VerifyAdmin          # role == 'admin'
```
- **Usage**: `current_user: VerifyAdminCoord` in endpoint signature
- **Roles**: `Role.ADMIN`, `Role.COORD`, `Role.USER` (from `users/enums.py`)

### 7. Database Session
- **Engine**: `create_async_engine(Settings().DATABASE_URL, connect_args={'options': '-c timezone=UTC'})`
- **Session**: `async_sessionmaker(engine, expire_on_commit=False)`
- **Dependency**: `async def get_session() -> AsyncGenerator[AsyncSession, None]`
- **Timezone**: All timestamps UTC (`timezone=True`, `server_default=func.timezone('UTC', func.now())`)

### 8. Authentication (JWT)
- **Access token**: Short-lived (configurable minutes), in Authorization header
- **Refresh token**: Long-lived (days), in HttpOnly cookie (`REFRESH_COOKIE_NAME`)
- **Cookie settings**: `secure`, `httponly`, `samesite`, `max_age` from Settings
- **Token payload**: `sub` (username), `exp`, `type` ('access'/'refresh'), optional `purpose`
- **Purpose validation**: `decode_token(token, expected_purpose='password_reset')`

### 9. Password Hashing
- **Library**: `pwdlib[argon2]` → `PasswordHash.recommended()`
- **Functions**: `get_password_hash()`, `verify_password()`

---

## Code Style Rules

### Ruff Configuration (`.ruff` in `pyproject.toml`)
- **Line length**: 79
- **Quote style**: Single
- **Preview**: Enabled
- **Select**: `I, F, E, W, PL, PT, FAST`
- **Per-file ignores**: `__init__.py` (F401), `tests/**` (PLR0913, PLR0917)

### Python Conventions
- **Imports**: Group stdlib → third-party → local (ruff `I` handles)
- **Type hints**: Required for all public functions
- **Async**: All DB operations async (`await session.execute()`, `await session.scalar()`)
- **Timezone**: Always `ZoneInfo('UTC')` or `timezone.utc`, never naive datetime
- **Enums**: `StrEnum` for API values, `IntEnum` if needed for DB

---

## Module-Specific Notes

### Users (`internum/modules/users/`)
- **Model**: `User` with `hiring_date` (periodo aquisitivo base)
- **Roles**: `ADMIN`, `COORD`, `USER`
- **Setores**: `Setor.REGISTRO`, `Setor.ADMINISTRATIVO`, `Setor.OFICIAL` + subsetores (`SUBSETORES_POR_SETOR`)
- **Approval**: Coord/Admin aprova via `VerifyAdminCoord` (role-based; não há verificação de mesmo setor)

### Auth (`internum/modules/auth/`)
- **Endpoints**: `/token`, `/refresh_token`, `/logout`, `/forgot-password`, `/reset-password`
- **Password reset**: Token with `purpose='password_reset'`, stored in `PasswordResetToken` model
- **Email**: `EmailService` (Mailtrap) with HTML templates

### Vacation (`internum/modules/vacation/`)
- **CLT Rules**: Art. 129, 130, 134, 137, 143
- **Validations**: No weekends/holidays (holidays.Brazil(state='PR')), min 5 days, max 3 periods, days not exceeding available (30/yr), saldo restante ≥14 dias a menos que já exista gozo ≥14 dias
- **Model**: `VacationAccrualPeriod` per user com `days_earned`, `days_reserved`, `days_enjoyed`, `days_sold`, `days_double_paid`; status `ACQUISITIVE → CONCESSIVE → EXPIRED/CLOSED`; períodos criados automaticamente a partir de `hiring_date`
- **Grants**: `VacationGrant` (NORMAL/RETROACTIVE/DOUBLE_PAYMENT) com status `GRANTED → FRUITED/PAID_DOUBLE/CANCELLED`; aprovação gera grants + reserva; RH confirma fruição (`confirm-fruition`); grants retroativo/dobro do admin são terminais (já nascem `FRUITED`/`PAID_DOUBLE`, somam em `days_enjoyed`/`days_double_paid`, sem reserva/confirmação)
- **Workflow**: Requests nascem em `SUBMITTED` → `APPROVED/REJECTED/CANCELLED`; aprovação gera concessões e reserva dias
- **By-sector**: `GET /grants/by-sector/{setor}` e `GET /requests/by-sector/{setor}` (Admin/Coord, opcional `?subsetor=`)
- **Migration**: `a911d5bbe8d1` criou `vacation_accrual_periods` + `vacation_grants` e removeu `vacation_balances`/`vacation_historical_periods`

### Library (`internum/modules/library/`)
- **Models**: `Book`, `Loan` (with status enum)
- **Jobs**: `check_overdue_loans` (APScheduler)

### Legal Briefs (`internum/modules/legal_briefs/`)
- **Models**: `LegalBrief` with revisions (versioning)
- **Audit**: Full `AuditMixin` tracking
- **Sanitização**: Conteúdo rico é sanitizado com `bleach` via `internum/utils/sanitize.py` (`sanitize_rich_text`); compare conteúdo por texto puro (`plain_text`) para decidir se houve mudança real
- **Revisão**: Nova `LegalBriefRevision` é criada **apenas** quando o título ou o texto puro do conteúdo mudam — formatação pura (sem alteração de texto) não gera revisão

### Notices (`internum/modules/notices/`)
- **Model**: `Notice` with read tracking per user
- **Endpoints**: List with search/pagination, mark read, deactivate

---

## Testing Patterns

### Conftest (`tests/conftest.py`)
- **Fixtures**: `session`, `client`, `user`, `admin_user`, `coord_user`, `auth_headers`
- **Factories**: `UserFactory`, `BookFactory`, etc. (factory-boy)
- **Database**: Testcontainers PostgreSQL (function-scoped)

### Test Organization
```
tests/
├── test_auth.py
├── test_user.py
├── test_vacation.py
├── test_library_books.py
├── test_library_loans.py
├── test_legal_brief.py
├── test_notice.py
├── test_home.py
├── test_jobs.py
├── test_security.py
├── test_status.py
└── test_vacation.py
```

---

## Migration Workflow
```bash
# Create migration
poetry run alembic revision --autogenerate -m "description"

# Apply
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

---

## Common Pitfalls to Avoid

| Pitfall | Correct Approach |
|---------|------------------|
| Circular imports between models | Use `TYPE_CHECKING` + string annotations |
| Missing `foreign_keys` in relationships | Always specify when multiple FKs to same table |
| Naive datetime | Always `timezone=True` + UTC |
| Sync DB calls in async code | Use `await session.execute()` / `scalar()` |
| Hardcoded limits in schemas | Define constants at module level (`MAX_PERIODS = 3`) |
| Business logic in routers | Move to `services.py` |
| Forgetting `Annotated[..., Depends()]` | All Depends must use Annotated (FAST002) |
| Direct `Settings()` instantiation | Use module-level `settings = Settings()` singleton |
| Missing `ondelete` on FKs | Always specify `CASCADE` or `SET NULL` |

---

## Development Commands
```bash
# Lint + format
poetry run task lint
poetry run task format

# Run
poetry run task run

# Test
poetry run task test

# Migrations
poetry run alembic revision --autogenerate -m "msg"
poetry run alembic upgrade head
```

---

## Environment
- **Required**: `.env.development` with all Settings fields
- **Docker**: `docker compose -f internum/infra/compose.yaml up -d` (PostgreSQL, etc.)
- **Python**: 3.13+ (managed by Poetry)

---

## Key Files Reference
| File | Purpose |
|------|---------|
| `internum/app.py` | FastAPI app + lifespan + CORS |
| `internum/api/main.py` | API v1 router aggregator |
| `internum/core/settings.py` | Pydantic Settings (env config) |
| `internum/core/database.py` | Async engine + session factory |
| `internum/core/security.py` | JWT, passwords, get_current_user |
| `internum/core/permissions.py` | Permission dependencies |
| `internum/core/models/registry.py` | SQLAlchemy registry |
| `internum/core/models/mixins.py` | AuditMixin |
| `internum/utils/sanitize.py` | Sanitização de conteúdo rico (`sanitize_rich_text`) + `plain_text` |
| `pyproject.toml` | Dependencies, Ruff, pytest, tasks |
| `.env.development` | Local environment variables |