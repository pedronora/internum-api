# Teste Manual do Módulo de Férias (Swagger UI)

Guia para estudar o fluxo completo do módulo de férias via `/docs` (Swagger UI),
usando dados fictícios.

## Setup

```bash
poetry run task servicesUp      # sobe o Postgres
poetry run alembic upgrade head # aplica migrações
poetry run task seedAdmin       # cria o admin (se não existir)
poetry run task run             # sobe a API em http://localhost:8000
```

Abra **http://localhost:8000/docs**.

**Login no Swagger:** `POST /api/v1/auth/token` (form-data: `username` + `password`)
→ copie o `access_token` → clique **Authorize** (topo direito) e cole o token
(o Swagger adiciona o prefixo `Bearer` sozinho; se der 401, cole com `Bearer ` na frente).

## Dados fictícios

Senhas seguem a regra (8–64 chars, maiúscula, minúscula, dígito, especial).
CPFs abaixo são válidos.

| Pessoa | username | senha | role | setor / subsetor | admissão |
|---|---|---|---|---|---|
| Pedro Nora (admin) | `pedronora` | (do `.env.development`) | admin | administrativo / Apoio | 2023-01-18 |
| Marina Souza | `marinacoord` | `Feria@2026a` | coord | registro / Análise | 2022-05-10 |
| João Silva | `joaosilva` | `Feria@2026b` | user | registro / Análise | 2024-03-01 |
| Ana Costa | `anacosta` | `Feria@2026c` | user | registro / Conferência | **2021-07-15** (antiga → períodos expirados) |
| Carlos Lima | `carloslima` | `Feria@2026d` | user | administrativo / Atendimento | 2024-06-20 |

CPFs: Marina `03102851606`, João `12716202605`, Ana `69312594311`, Carlos `80810443880`.

## Etapa 1 — Cadastro de usuários

`POST /api/v1/users/` (com o token do admin). Exemplo (Marina):

```json
{
  "name": "Marina Souza", "username": "marinacoord", "cpf": "03102851606",
  "email": "marina@test.com", "birthday": "1990-05-20",
  "hiring_date": "2022-05-10", "setor": "registro", "subsetor": "Análise",
  "role": "coord", "active": true, "password": "Feria@2026a"
}
```

Repita para João, Ana e Carlos (`role`: `user`). Depois `GET /api/v1/users/` para
conferir os `id`s (necessários nas rotas de admin). **Observe:** só admin pode criar outro admin.

## Etapa 2 — Períodos aquisitivos (criação automática)

Faça login como **João** (`POST /auth/token`) e:

- `GET /api/v1/vacation/accrual-periods` → lista P1 **expired**, P2 **concessive**,
  P3 **acquisitive** (gerados a partir de `hiring_date`). P2 é o que vamos usar.

Como **admin**: `GET /vacation/accrual-periods/{joao_id}` e
`GET /vacation/accrual-periods/{joao_id}/{periodo_id}` (mesma visão + grants).

## Etapa 3 — Preview (validação CLT)

Com o token do João, `POST /api/v1/vacation/preview`:

```json
{
  "periods": [
    { "start_date": "2026-09-14", "end_date": "2026-09-27" },
    { "start_date": "2026-11-09", "end_date": "2026-11-13" }
  ]
}
```

→ `valid: true` (14 dias + 5 dias). Depois teste um caso inválido (início em sábado):

```json
{ "periods": [ { "start_date": "2026-09-12", "end_date": "2026-09-25" } ] }
```

→ observe os erros (início em dia de repouso, mínimo de 14 dias, etc.).
Esse endpoint é só para estudar as regras, não persiste nada.

## Etapa 4 — Solicitação (workflow principal)

1. **João** `POST /vacation/requests`:

```json
{
  "target_accrual_period_id": 2,
  "periods": [
    { "start_date": "2026-09-14", "end_date": "2026-09-27" },
    { "start_date": "2026-11-09", "end_date": "2026-11-13" }
  ]
}
```

→ nasce `submitted` (201). Guarde o `request_id`.

2. João `GET /vacation/requests` → vê só a dele.
3. João `POST /vacation/requests/{id}/cancel` → vira `cancelled` (teste de cancelamento).
4. Crie **outra request** (mesma body) e agora **Marina** (coord) aprova:

`POST /vacation/requests/{id}/approve` com `{ "reviewer_notes": "Ok" }`
→ vira `approved` e são criados grants (um por período) com `days_reserved`.

5. Confira em `GET /vacation/accrual-periods` (João): `days_reserved` = 14 + 5 = 19,
   `available_days` = 11.
6. Teste `POST /vacation/requests/{id}/reject` com outra request para ver o fluxo de rejeição.

## Etapa 5 — Grants e confirmação de fruição (RH)

1. João `GET /vacation/grants` → grants `granted`.
2. **Admin** `POST /vacation/grants/{grant_id}/confirm-fruition` com `{ "confirm": true }`
   → grant `fruited`.
3. Volte em `GET /vacation/accrual-periods` do João: `days_reserved` caiu e `days_enjoyed` subiu.
4. Teste também `{ "confirm": false }` em outro grant → `cancelled` e a reserva é devolvida.

## Etapa 6 — Venda de dias (abono pecuniário)

**Admin**: `POST /vacation/accrual-periods/{joao_id}/{periodo_id}/sell` com `{ "days": 10 }`
→ `days_sold = 10` no período. Tente `days: 11` para ver o erro (máx. 10).

## Etapa 7 — Períodos expirados: retroativo, dobro e alertas

1. Login **Ana** → `GET /vacation/accrual-periods` → vários períodos `expired` (admissão antiga).
2. **Admin** `GET /vacation/alerts` → lista os períodos expirados com saldo
   (use o `id` do período da Ana).
3. **Admin** cadastra gozo retroativo:

`POST /vacation/accrual-periods/{ana_id}/{periodo_id}/grants`

```json
{ "start_date": "2023-05-02", "end_date": "2023-05-06", "grant_type": "retroactive", "notes": "Ajuste de implantação" }
```

→ nasce `fruited`, soma em `days_enjoyed` (sem reserva/confirmação).

4. **Admin** cadastra dobro: mesmo endpoint com `"grant_type": "double_payment"`
   → nasce `paid_double`, soma em `days_double_paid`.
5. Ana `GET /accrual-periods` → quando o retroativo cobrir todo o saldo:
   `status: closed`, `is_double_eligible: false`.
6. **Admin** `GET /alerts` de novo → os períodos regularizados somem dos alertas.

## Etapa 8 — Filtros por setor/subsetor (Admin/Coord)

- `GET /vacation/requests/by-sector/registro` e `GET /vacation/grants/by-sector/registro`
  → só empregados do Registro.
- Adicione `?subsetor=Análise` para restringir.

## Etapa 9 — Permissões (cenários negativos)

Login **Carlos** (user comum) e confirme 403 em:

- `GET /vacation/alerts`
- `GET /vacation/accrual-periods/{joao_id}` (período de outro)
- `POST /vacation/grants/{id}/confirm-fruition`
- `POST /vacation/accrual-periods/{id}/{periodo}/sell`
- `GET /vacation/grants/by-sector/registro`

## Resumo dos endpoints (prefixo `/api/v1/vacation`)

| # | Método/Rota | Permissão | Finalidade | Etapa |
|---|---|---|---|---|
| 1 | GET `/accrual-periods` | User | Meus períodos | 2 |
| 2 | GET `/accrual-periods/{user_id}` | Admin/Coord | Períodos de outro | 2 |
| 3 | GET `/accrual-periods/{user_id}/{period_id}` | Admin/Coord | Período + grants | 2 |
| 4 | POST `/accrual-periods/{user_id}/{period_id}/sell` | **Admin** | Venda de dias | 6 |
| 5 | POST `/accrual-periods/{user_id}/{period_id}/grants` | **Admin** | Retroativo/dobro (terminais) | 7 |
| 6 | POST `/requests` | User | Criar solicitação | 4 |
| 7 | GET `/requests` | User/Admin/Coord | Listar (filtros) | 4 |
| 8 | GET `/requests/by-sector/{setor}` | Admin/Coord | Por setor/subsetor | 8 |
| 9 | GET `/requests/{id}` | Dono/Admin/Coord | Detalhe | 4 |
| 10 | POST `/requests/{id}/approve` | Admin/Coord | Aprovar → grants + reserva | 4 |
| 11 | POST `/requests/{id}/reject` | Admin/Coord | Rejeitar | 4 |
| 12 | POST `/requests/{id}/cancel` | Dono | Cancelar pendente | 4 |
| 13 | GET `/grants` | User/Admin/Coord | Listar concessões | 5 |
| 14 | GET `/grants/by-sector/{setor}` | Admin/Coord | Por setor/subsetor | 8 |
| 15 | GET `/grants/{id}` | Dono/Admin/Coord | Detalhe | 5 |
| 16 | POST `/grants/{id}/confirm-fruition` | **Admin** | RH confirma/nega fruição | 5 |
| 17 | POST `/preview` | User | Validação sem persistir | 3 |
| 18 | GET `/alerts` | Admin/Coord | Expirados a regularizar | 7 |

## Observações

- As datas da Etapa 3/4 foram escolhidas para passar nas regras (segunda-feira como início,
  ≥14 dias no período principal). Se o `preview` apontar feriado do PR, ajuste um dia e revalide —
  é exatamente o que o endpoint faz.
- Os períodos aquisitivos são criados sob demanda (lazy) a partir de `hiring_date` e o status
  é sincronizado com `date.today()`.
- Grants retroativo/dobro cadastrados por admin são **terminais**: já nascem
  `FRUITED`/`PAID_DOUBLE`, somam em `days_enjoyed`/`days_double_paid` e não passam pela
  confirmação do RH (nem reservam dias).
