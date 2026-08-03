# Módulo de Férias - Documentação da Implementação

## Visão Geral

Módulo completo para gestão de férias conforme CLT (Art. 129 e seguintes), integrado ao projeto Internum API.

## Estrutura de Arquivos

```
internum/modules/vacation/
├── __init__.py
├── enums.py          # Enums: VacationStatus, VacationPeriodType, VacationRequestStatus
├── models.py         # Models SQLAlchemy: VacationBalance, VacationRequest, VacationPeriod
├── schemas.py        # Schemas Pydantic para request/response
├── services.py       # CLTVacationService - regras de negócio CLT
└── routers.py        # Endpoints FastAPI com permissões
```

## Models

### VacationBalance
Controle de saldo de férias por período aquisitivo.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | FK(User) | Usuário dono do saldo |
| `current_period_start` | Date | Início do período aquisitivo atual |
| `current_period_end` | Date | Fim do período aquisitivo atual |
| `accrued_days` | Integer | Dias vencidos (30 por ano completo) |
| `proportional_days` | Integer | Dias proporcionais (período incompleto) |
| `enjoyed_days` | Integer | Dias já gozados/aprovados |
| `sold_days` | Integer | Dias vendidos (abono pecuniário) |
| `manual_adjustment_days` | Integer | Ajuste manual (±30) para migração/histórico |
| `adjustment_reason` | String | Justificativa do ajuste |
| `adjusted_at` | DateTime | Quando foi ajustado |
| `adjusted_by_id` | FK(User) | Quem ajustou (admin) |
| `next_period_start` | Date | Início do próximo período |
| `next_period_end` | Date | Fim do próximo período |
| `next_accrued_days` | Integer | Dias previstos para próximo período |

**Propriedades calculadas:**
- `available_days` = accrued + proportional + **manual_adjustment** - enjoyed - sold
- `total_earned` = accrued + proportional

### VacationRequest
Solicitação de férias (workflow: draft → submitted → approved/rejected/cancelled).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | FK(User) | Solicitante |
| `reviewer_id` | FK(User, nullable) | Aprovador (coord/admin) |
| `status` | Enum | DRAFT, SUBMITTED, UNDER_REVIEW, APPROVED, REJECTED, CANCELLED |
| `requested_at` | DateTime | Data de submissão |
| `reviewed_at` | DateTime | Data de análise |
| `reviewer_notes` | String | Observações do aprovador |

### VacationPeriod
Período individual dentro de uma solicitação (máx. 3 por request).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `request_id` | FK(VacationRequest) | Solicitação pai |
| `start_date` | Date | Início do período |
| `end_date` | Date | Fim do período |
| `period_type` | Enum | FULL (≥14 dias) ou PROPORTIONAL (<14 dias) |
| `status` | Enum | PENDING, APPROVED, REJECTED, CANCELLED, ENJOYED |
| `days_count` | Integer | Dias corridos |
| `working_days_count` | Integer | Dias úteis (exclui fds/feriados) |

## Regras CLT Implementadas

| Regra (Art. CLT) | Validação |
|------------------|-----------|
| Art. 134 - Início não em dia de repouso/feriado | `is_weekend()` + `is_holiday()` no start_date |
| Art. 134 - Fim não em dia de repouso/feriado | `is_weekend()` + `is_holiday()` no end_date |
| Art. 134 - Mínimo 14 dias em um período | Pelo menos 1 período ≥ 14 dias corridos |
| Art. 129 - Período aquisitivo de 12 meses | Calculado a partir de `User.hiring_date` |
| Art. 130 - 30 dias por período aquisitivo | `accrued_days` = 30/ano completo |
| Art. 134 §1º - Máx. 3 períodos | Validação `MAX_PERIODS = 3` |
| Art. 134 §2º - Mín. 5 dias por período | Validação `MIN_PERIOD_DAYS = 5` (corridos e úteis) |
| Art. 143 - Abono pecuniário (venda) | Máx. 10 dias (`MAX_SELL_DAYS = 10`), apenas dias vencidos |

## Feriados

Usa biblioteca `holidays` (Brasil, estado PR - Paraná):
```python
BRAZIL_HOLIDAYS = holidays.Brazil(state='PR')
```

## Endpoints

### Saldo
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| GET | `/vacation/balance` | User (próprio) | Meu saldo atual |
| GET | `/vacation/balance/{user_id}` | Admin/Coord | Saldo de outro usuário |

### Preview (Validação Prévia)
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/vacation/preview` | User | Valida períodos sem criar request |

### Solicitações
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/vacation/requests` | User | Criar rascunho |
| GET | `/vacation/requests` | User/Admin/Coord | Listar (filtros: status, user_id, paginação) |
| GET | `/vacation/requests/{id}` | User (próprio), Admin/Coord | Detalhes com períodos |
| PUT | `/vacation/requests/{id}` | User (próprio, apenas DRAFT) | Editar rascunho |
| POST | `/vacation/requests/{id}/submit` | User (próprio, apenas DRAFT) | Enviar para aprovação |
| POST | `/vacation/requests/{id}/approve` | Admin/Coord | Aprovar (opcional editar períodos) |
| POST | `/vacation/requests/{id}/reject` | Admin/Coord | Rejeitar com justificativa |
| POST | `/vacation/requests/{id}/cancel` | User (próprio, SUBMITTED/UNDER_REVIEW) | Cancelar |

### Venda de Dias
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/vacation/sell-days` | User | Vender dias (1-10, apenas vencidos) |

### Ajuste Manual de Saldo (Migração)
| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| PUT | `/vacation/balance/{user_id}/adjust` | **Admin** | Ajustar saldo manualmente (±30 dias) |

## Workflow de Aprovação

```
DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED → ENJOYED
                    ↓
               REJECTED
                    ↓
               CANCELLED (pode vir de SUBMITTED ou UNDER_REVIEW)
```

- **Coord do mesmo setor** aprova (via `VerifyAdminCoord`)
- **Admin** tem acesso total
- **Usuário** só vê/edita seus próprios pedidos

## Validações no Schema

```python
MAX_PERIODS = 3
MAX_SELL_DAYS = 10

VacationRequestCreate:
    periods: List[VacationPeriodCreate]  # min=1, max=3

VacationSellDaysRequest:
    days: int  # ge=1, le=10

VacationBalanceAdjustRequest:  # Apenas Admin
    manual_adjustment_days: int  # ge=-30, le=30
    adjustment_reason: str  # min=5, max=500
```

## Service - CLTVacationService

Métodos principais:
- `calculate_balance(user)` - Cria/atualiza VacationBalance baseado em hiring_date
- `preview_vacation(user, periods)` - Validação completa antes de criar
- `create_request(user, periods)` - Cria VacationRequest + VacationPeriods
- `approve_request(request, reviewer, notes)` - Aprova, atualiza saldo (enjoyed_days)
- `reject_request(request, reviewer, notes)` - Rejeita
- `cancel_request(request, user)` - Cancela (apenas dono, se pendente)
- `sell_vacation_days(user, days)` - Vende dias (reduce accrued, increase sold)
- `adjust_balance(user, adjuster, adjustment_days, reason)` - **Ajuste manual (admin)**

## Ajuste Manual para Migração (Importante)

Para empresas com histórico pré-existente, o cálculo automático baseado em `hiring_date` **não reflete a realidade** (dias já gozados, vendidos, pendentes).

**Solução implementada:**
1. Campo `manual_adjustment_days` (±30 dias) no `VacationBalance`
2. Campo `adjustment_reason` para auditoria
3. Campos `adjusted_at` + `adjusted_by_id` para rastreabilidade
4. Endpoint `PUT /vacation/balance/{user_id}/adrest` (apenas **Admin**)
5. `available_days` inclui o ajuste: `accrued + proportional + manual_adjustment - enjoyed - sold`

**Fluxo de migração sugerido:**
1. Executar migration Alembic (cria tabelas com defaults 0)
2. Para cada funcionário existente, admin faz `PUT /vacation/balance/{id}/adjust` com:
   - `manual_adjustment_days`: saldo real - saldo calculado
   - `adjustment_reason`: "Migração inicial - saldo histórico de X dias gozados, Y vendidos, Z pendentes"
3. Sistema passa a calcular corretamente a partir daí

## Permissões

```python
# core/permissions.py
VerifySelfAdmin      # user_id == current_user.id OR role == 'admin'
VerifySelfAdminCoord # user_id == current_user.id OR role in ['admin', 'coord']
VerifyAdminCoord     # role in ['admin', 'coord']
VerifyAdmin          # role == 'admin'
CurrentUser          # usuário autenticado (get_current_user)
```

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

## Testes

Todos os 132 testes existentes passam. Para testar o módulo:
```bash
poetry run pytest tests/ -k vacation -v
```

## Próximos Passos

1. **Migration Alembic**: `poetry run alembic revision --autogenerate -m "add vacation module"`
2. **Testes específicos**: Criar `tests/test_vacation.py` cobrindo:
   - Validações CLT (fds, feriados, 14 dias, 3 períodos)
   - Cálculo de saldo (período aquisitivo, proporcionais)
   - Workflow completo (draft → submit → approve → enjoy)
   - Venda de dias
   - Permissões (user vs coord vs admin)
3. **Notificações**: Email ao submeter/aprovar/rejeitar (integrar `EmailService`)
4. **Relatórios**: Exportar férias por setor/período