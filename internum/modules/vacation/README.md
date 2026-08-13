# Módulo de Férias - Documentação da Implementação

## Visão Geral

Módulo de gestão de férias conforme CLT (Art. 129 e seguintes), integrado ao projeto Internum API.
A arquitetura é centrada em **períodos aquisitivos** (`VacationAccrualPeriod`), **concessões**
(`VacationGrant`) e **solicitações** (`VacationRequest`). Todos os contadores são expressos em
**dias corridos** (Art. 130 CLT).

## Estrutura de Arquivos

```
internum/modules/vacation/
├── __init__.py
├── enums.py          # Enums de status/tipos (accrual, grant, request, period)
├── models.py         # Models SQLAlchemy: VacationAccrualPeriod, VacationGrant, VacationRequest, VacationPeriod
├── schemas.py        # Schemas Pydantic para request/response
├── services.py       # CLTVacationService - regras de negócio CLT
└── routers.py        # Endpoints FastAPI com permissões
```

## Models

### VacationAccrualPeriod
Período aquisitivo (12 meses trabalhados) + concessivo (12 meses para gozo) de um usuário.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | FK(User) | Usuário dono do período |
| `period_number` | Integer | Sequencial (1, 2, ...) a partir de `hiring_date` |
| `acquisitive_start` / `acquisitive_end` | Date | Período aquisitivo (trabalhou) |
| `concessive_start` / `concessive_end` | Date | Período concessivo (pode gozar) |
| `status` | Enum | `ACQUISITIVE`, `CONCESSIVE`, `EXPIRED`, `CLOSED` |
| `days_earned` | Integer | Dias adquiridos (30/ano completo, proporcional se incompleto) |
| `days_reserved` | Integer | Dias reservados por concessões aprovadas |
| `days_enjoyed` | Integer | Dias efetivamente gozados (RH confirmou) |
| `days_sold` | Integer | Dias vendidos (abono pecuniário) |
| `days_double_paid` | Integer | Dias pagos em dobro (não gozados) |
| `is_double_eligible` | Boolean | `True` quando o concessivo expirou e ainda há saldo a regularizar |

**Propriedade calculada:**
- `available_days` = days_earned - days_reserved - days_enjoyed - days_sold - days_double_paid

### VacationGrant
Concessão de férias (gozo normal, gozo retroativo ou pagamento em dobro) vinculada a um período.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | FK(User) | Usuário beneficiado |
| `accrual_period_id` | FK(VacationAccrualPeriod) | Período aquisitivo de origem |
| `start_date` / `end_date` | Date | Intervalo do gozo |
| `days_count` | Integer | Dias corridos |
| `grant_type` | Enum | `NORMAL`, `RETROACTIVE`, `DOUBLE_PAYMENT` |
| `status` | Enum | `GRANTED`, `IN_PROGRESS`, `FRUITED`, `CANCELLED`, `PAID_DOUBLE` |
| `approved_by_id` / `approved_at` | FK(User) / DateTime | Quem e quando aprovou |
| `confirmed_by_id` / `confirmed_at` | FK(User) / DateTime | RH confirmou fruição |
| `notes` | String | Observações |

**Propriedade calculada:**
- `is_regularization` = `True` quando o grant é de regularização de período expirado (`RETROACTIVE` ou `DOUBLE_PAYMENT`)

### VacationRequest
Solicitação de férias submetida por um usuário, contendo 1..3 períodos.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | FK(User) | Solicitante |
| `target_accrual_period_id` | FK(VacationAccrualPeriod) | Período de origem do gozo |
| `reviewer_id` | FK(User, nullable) | Aprovador (coord/admin) |
| `status` | Enum | `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `CANCELLED` |
| `requested_at` / `reviewed_at` | DateTime | Datas de submissão/análise |
| `reviewer_notes` | String | Observações do aprovador |

### VacationPeriod
Período individual dentro de uma solicitação (máx. 3 por request).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `request_id` | FK(VacationRequest) | Solicitação pai |
| `start_date` / `end_date` | Date | Intervalo |
| `period_type` | Enum | `MAIN` (≥14 dias) ou `COMPLEMENTARY` (5–13 dias) |
| `days_count` | Integer | Dias corridos |

## Enums

### VacationAccrualStatus
| Valor | Significado |
|-------|-------------|
| `acquisitive` | Período aquisitivo em andamento |
| `concessive` | Período concessivo (pode gozar) |
| `expired` | Concessivo terminou sem gozo (dobro aplicável) |
| `closed` | Regularizado (gozou/pagou em dobro) |

### VacationGrantType
| Valor | Significado |
|-------|-------------|
| `normal` | Gozo normal aprovado |
| `retroactive` | Gozo atrasado cadastrado pelo admin |
| `double_payment` | Pagamento em dobro (não gozou) |

### VacationGrantStatus
| Valor | Significado |
|-------|-------------|
| `granted` | Aprovado, dias reservados |
| `in_progress` | Período de gozo iniciado |
| `fruited` | RH confirmou fruição |
| `cancelled` | Cancelado (RH negou ou usuário não gozou) |
| `paid_double` | Pagamento em dobro confirmado |

### VacationRequestStatus
`draft` → `submitted` → `under_review` → `approved` / `rejected` / `cancelled`

## Regras CLT Implementadas

| Regra (Art. CLT) | Validação |
|------------------|-----------|
| Art. 129 - Período aquisitivo de 12 meses | Calculado a partir de `User.hiring_date` (aniversários) |
| Art. 130 - 30 dias por período aquisitivo | `days_earned` = 30/ano completo; proporcional se incompleto |
| Art. 134 §3º - Início não em dia de repouso/feriado | Início vedado em sexta/sábado/domingo/feriado ou ≤2 dias antes de feriado |
| Art. 134 §1º - Mínimo 14 dias em um período | Pelo menos 1 gozo ≥14 dias corridos por período |
| Art. 134 §1º - Máx. 3 períodos | `MAX_PERIODS = 3` |
| Art. 134 §2º - Mín. 5 dias por período | `MIN_PERIOD_DAYS = 5` (dias corridos) |
| Art. 134 - Intervalo entre gozos | Períodos sem sobreposição e com ≥1 dia de intervalo |
| Art. 143 - Abono pecuniário (venda) | Máx. 10 dias (`MAX_SELL_DAYS = 10`), apenas admin, período não expirado |
| Art. 137 - Dobra por não gozo | `double_payment` apenas em períodos `EXPIRED`, via admin |

**Regra de gozo fracionado (saldo restante):**
- Restante 1–4 dias → erro (mínimo para novo período é 5 dias).
- Restante 5–13 dias sem que o período já tenha um gozo de ≥14 dias → erro.

## Feriados

Usa biblioteca `holidays` (Brasil, estado PR - Paraná):
```python
BRAZIL_HOLIDAYS = holidays.Brazil(state='PR')
```

## Endpoints

Prefixo: `/api/v1/vacation` (definido em `internum/api/main.py`).

### Períodos Aquisitivos
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| GET | `/accrual-periods` | User (próprio) | Meus períodos (cria os ausentes e sincroniza) |
| GET | `/accrual-periods/{user_id}` | Admin/Coord | Períodos de outro usuário |
| GET | `/accrual-periods/{user_id}/{period_id}` | Admin/Coord | Período específico com concessões |
| POST | `/accrual-periods/{user_id}/{period_id}/sell` | **Admin** | Vender dias (abono pecuniário) |
| POST | `/accrual-periods/{user_id}/{period_id}/grants` | Admin/Coord | Cadastrar concessão: `normal` (marcar férias em período concessivo), `retroactive`/`double_payment` (período expirado) |

### Solicitações (Requests)
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/requests` | User | Criar solicitação (já em `submitted`) |
| GET | `/requests` | User (próprio) / Admin/Coord (todos) | Listar (filtros: status, user_id, skip, limit) |
| GET | `/requests/{request_id}` | User (próprio) / Admin/Coord | Detalhes com períodos |
| GET | `/requests/by-sector/{setor}` | Admin/Coord | Solicitações por setor (opcional `?subsetor=`, `?status=`) |
| POST | `/requests/{request_id}/approve` | Admin/Coord | Aprovar (gera concessões e reserva dias) |
| POST | `/requests/{request_id}/reject` | Admin/Coord | Rejeitar |
| POST | `/requests/{request_id}/cancel` | User (próprio) | Cancelar (se `submitted`/`under_review`) |

### Concessões (Grants)
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| GET | `/grants` | User (próprio) / Admin/Coord | Listar (filtros: status, user_id, accrual_period_id) |
| GET | `/grants/{grant_id}` | User (próprio) / Admin/Coord | Detalhe da concessão |
| GET | `/grants/by-sector/{setor}` | Admin/Coord | Concessões por setor (opcional `?subsetor=`, `?status=`) |
| POST | `/grants/{grant_id}/confirm-fruition` | **Admin** | RH confirma (ou não) a fruição efetiva |

### Preview e Alertas
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/preview` | User | Valida períodos sem criar request |
| GET | `/alerts` | Admin/Coord | Períodos expirados com saldo a regularizar (candidatos a dobro) |

## Workflow

### Período aquisitivo (automático)

```
ACQUISITIVE → CONCESSIVE → EXPIRED → (admin cadastra dobro/gozo retroativo) → CLOSED
                          ↓
                    regularização (FRUITED/PAID_DOUBLE) → CLOSED
```

Os períodos são criados sob demanda (lazy) a partir de `hiring_date` quando o usuário acessa
seus períodos ou solicita férias. O status é sincronizado com `date.today()`.

### Solicitação e concessão

```
Usuário                  Admin/Coord              RH (Admin)
--------                 -----------              ---------
[preview] validações
POST /requests (submitted)
                         POST .../approve
                         → cria N grants GRANTED
                           e reserva days_reserved
                         POST .../reject
POST .../cancel (dono)
                                                   POST .../confirm-fruition
                                                   confirm=true  → FRUITED (ou PAID_DOUBLE)
                                                   confirm=false → CANCELLED (devolve reserva)
```

Grants cadastrados pelo **admin** em período expirado (retroativo/dobro) são **terminais**:
já nascem `FRUITED`/`PAID_DOUBLE`, somam direto em `days_enjoyed`/`days_double_paid` e não passam
pela confirmação do RH (nem reservam dias).

A **marcação direta** de férias (`grant_type=normal`) em período concessivo nasce `GRANTED`,
reserva dias (`days_reserved`) e segue o fluxo normal de confirmação do RH
(`POST /grants/{grant_id}/confirm-fruition`).

### Fluxos especiais (Admin/Coord)

1. **Marcação direta de férias** (`grant_type=normal`): admin/coord registra o gozo em período
   `CONCESSIVE` sem solicitação prévia. Valida as mesmas regras CLT das solicitações
   (mín. 5 dias, sem início em sexta/sábado/domingo/feriado e regra do saldo restante).
   Nasce `GRANTED` e reserva dias até a confirmação do RH.
2. **Venda de dias** (`POST .../sell`): abono pecuniário (Art. 143), máx. 10 dias/período,
   apenas em período não expirado, respeitando saldo e a regra de gozo fracionado.
3. **Gozo retroativo** (`grant_type=retroactive`): cadastro de gozo ocorrido no passado,
   apenas em período `EXPIRED`, mínimo 5 dias. Já nasce `FRUITED` e soma em `days_enjoyed`.
4. **Pagamento em dobro** (`grant_type=double_payment`): indenização por não gozo (Art. 137),
   apenas em período `EXPIRED`. Já nasce `PAID_DOUBLE` e soma em `days_double_paid`.
5. **Alertas** (`GET /alerts`): lista períodos expirados com saldo a regularizar.

## Validações no Schema

```python
MAX_PERIODS = 3
MIN_PERIOD_DAYS = 5
MIN_MAIN_PERIOD_DAYS = 14
MAX_SELL_DAYS = 10

VacationRequestCreate:
    target_accrual_period_id: int
    periods: list[VacationPeriodCreate]  # min=1, max=3

VacationSellDaysRequest:
    days: int  # ge=1, le=10

VacationGrantAdminCreate:  # Admin/Coord
    start_date: date
    end_date: date
    grant_type: VacationGrantType  # normal | retroactive | double_payment
    notes: Optional[str]

VacationConfirmFruitionRequest:
    confirm: bool
    notes: Optional[str]
```

## Service - CLTVacationService

Métodos principais:
- `ensure_accrual_periods(user)` - Cria períodos faltantes e sincroniza status/dias
- `get_accrual_periods(user)` / `get_accrual_period(user, period_id)` - Consulta com grants
- `preview_vacation(user, data)` - Validação completa sem persistir
- `create_request(user, data)` - Cria request + períodos (status `submitted`)
- `approve_request(request, reviewer, notes)` - Aprova, cria grants e reserva dias
- `reject_request(request, reviewer, notes)` - Rejeita
- `cancel_request(request, user)` - Cancela (apenas dono, se pendente)
- `create_grant(data, creator)` - Marcação direta (normal, período concessivo, com validação CLT) ou regularização (retroativo/dobro, período expirado)
- `list_grants(user_id, status, accrual_period_id, setor, subsetor)` - Concessões com filtros (inclui por setor/subsetor do empregado)
- `confirm_fruition(grant, user, confirm, notes)` - RH confirma/nega fruição
- `sell_days(accrual, days, admin)` - Venda de dias (abono pecuniário)
- `get_double_payment_alerts()` - Alertas de períodos expirados

## Permissões

```python
# core/permissions.py
CurrentUser          # usuário autenticado (get_current_user)
VerifyAdminCoord     # role in ['admin', 'coord']
VerifyAdmin          # role == 'admin'
```

- **Admin/Coord** aprovam/rejeitam solicitações, veem dados de qualquer usuário, recebem alertas e cadastram concessões (`normal`/`retroactive`/`double_payment`).
- **Admin** (apenas) vende dias e confirma fruição de grants normais.
- **Usuário** consulta e solicita apenas seus próprios dados.

## Integração

Registrado em `internum/api/main.py`:
```python
from internum.modules.vacation.routers import router as vacation_router
router.include_router(vacation_router)  # prefix: /api/v1/vacation
```

Dependência adicionada em `pyproject.toml`:
```toml
"holidays (>=0.52.0,<1.0.0)",
```

## Migração

A migração `a911d5bbe8d1` ("refactor vacation to accrual periods and grants") cria
`vacation_accrual_periods` e `vacation_grants`, remove `vacation_balances` e
`vacation_historical_periods`, e adiciona `target_accrual_period_id` a `vacation_requests`.

```bash
poetry run alembic upgrade head
```

## Testes

Todos os testes do módulo passam (64 casos em `tests/test_vacation.py`). Para executar:
```bash
poetry run task test -- -k vacation
```

Observação: freezegun interfere na construção de schemas pydantic. A fixture
`warm_fastapi_schemas` pré-compila os schemas fora do freeze.
