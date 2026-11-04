# Changelog — internum-api

Todas as mudanças relevantes desta imagem serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o versionamento segue o padrão [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [2.0.0] - 2026-11-04

### Removed

- **Breaking:** o perfil `admin` foi eliminado. A organização tem **um único
  `oficial`**, criado exclusivamente por `seed_oficial.py` e protegido por um
  índice único parcial (`uq_user_roles_single_oficial`). Vínculos `ADMIN`
  existentes são descartados pela migration `7f3c9d2a1b45`.
- **Breaking:** `roles` deixou de ser obrigatório na criação de usuário.
  Coordenação, gestão e demais perfis criam usuários **sem perfil**, que
  recebem acesso depois.
- **Breaking:** trocar a senha de terceiros agora exige
  `users:change_password`, exclusivo do `oficial`.

### Added

- Autorização por permissões (`core/authorization.py` + `core/permissions.py`),
  com perfis por unidade, múltiplos papéis por usuário, edição por campo e
  matriz documentada em `docs/authorization.md`.
- Rotação e revogação de refresh tokens no servidor, com detecção de reuso,
  `session_started_at` e poda diária dos tokens expirados.
- Limite absoluto de sessão de 7 dias (`REFRESH_TOKEN_ABSOLUTE_DAYS`).
- Invalidação de access tokens após troca/reset de senha via
  `password_changed_at`, mantendo a sessão atual na autoalteração.
- Política de senha compartilhada no reset e na troca (8–64 caracteres, com
  maiúscula, minúscula, dígito e caractere especial).
- Seed `seed_oficial.py` idempotente, executado no boot do container e no
  compose de desenvolvimento.
- Guard que impede editar/desativar a conta do `oficial` por qualquer outro
  usuário, e proteção do último `oficial` ativo.
- Testes dedicados para unicidade do oficial, troca de senha e seed.

### Changed

- `/docs`, `/redoc` e `/openapi.json` só existem com `DOCS_ENABLED=True`.
- `GET /api/v1/status` não expõe mais detalhes internos em caso de falha.
- A troca de senha do próprio usuário devolve um novo `access_token`; quando o
  `oficial` troca a senha de outra pessoa, retorna `access_token: null` e
  revoga todas as sessões do alvo.

### Fixed

- Tokens de refresh e de reset não autenticam mais como access tokens
  (`type`/`purpose` são validados em `get_current_user`).
- Rotas de férias por unidade respeitam a permissão `vacation:manage_all` em
  vez de checar o perfil.

### Security

- Rate limit por IP em `/token`, `/refresh_token`, `/forgot-password` e
  `/reset-password` (`slowapi`), configurável por `RATE_LIMIT_*`, com resposta
  429 e `Retry-After`.
- `password_reset_tokens` guarda apenas `sha256(token)`; a migration
  `c4e1a9b7d2f6` converte os tokens existentes.
- Headers de segurança em todas as respostas da API: CSP restritiva,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, COOP/CORP e HSTS quando `SECURE_COOKIE=True`.

## [1.3.0] - 2026-09-12

### Added

- Campos opcionais `phone` (String(20)) e `gross_salary` (Numeric(14,2)) no
  cadastro de usuários e nas demais ações do CRUD (migration `b061be051fe4`).
  Telefone é normalizado/validado no padrão brasileiro (10–13 dígitos) e
  editável pelo próprio usuário; `gross_salary` é visível/editável apenas por
  admin/coord (sensitive field).

## [1.2.0] - 2026-08-20

### Added

- Sanitização do conteúdo rico (HTML do editor TipTap) em ementas e avisos com
  `bleach`: permitidas apenas as tags do editor, atributos `href`/`title`/etc.
  em links e `text-align` via `CSSSanitizer` (deps `bleach` + `tinycss2`).
- `update_legal_brief` agora só cria `LegalBriefRevision` quando o **texto**
  (ignorando marcação HTML) ou o **título** mudam. Alterações apenas de
  formatação (mesmo conteúdo) atualizam a `LegalBrief` diretamente, sem nova
  revisão (helper `plain_text()`).

## [1.1.1] - 2026-08-13

### Fixed

- Mensagem de erro de login ajustada para "Usuário ou senha incorretos", deixando claro
  que o problema pode estar no usuário, e não apenas no email.

## [1.1.0] - 2026-08-13

### Added

- Cadastro direto de férias por Admin/Coord: `POST /accrual-periods/{user_id}/{period_id}/grants`
  agora aceita `grant_type=normal` (gozo normal) em período concessivo, com as mesmas
  validações CLT das solicitações (mín. 5 dias, sem início em sexta/sábado/domingo/feriado,
  regra do saldo restante). A concessão nasce `GRANTED` (reserva dias) e segue para
  confirmação de fruição pelo RH.

### Changed

- Otimização da imagem Docker: removida a duplicação de camada causada pelo
  `chown -R` sobre o virtualenv. Os arquivos agora são copiados com
  `COPY --chown=app:app`, mantendo apenas o `chmod` do entrypoint.
  - Redução da imagem de ~316MB para ~210MB (~30% menor) sem alteração de runtime.

## [1.0.1] - 2026-08-13

### Changed

- Refatoração do módulo de férias: substituição de `vacation_balances` e
  `vacation_historical_periods` por `vacation_accrual_periods` (períodos
  aquisitivos/concessivos) e `vacation_grants` (concessões), com status
  `ACQUISITIVE → CONCESSIVE → EXPIRED/CLOSED`.
- Renomeados os valores de enums do módulo de férias para refletir a semântica
  de períodos aquisitivos e tipos de período (`MAIN`/`COMPLEMENTARY`).
- Aprovação de solicitações de férias agora gera concessões e reserva de dias;
  grants retroativo/dobro do admin nascem terminais (`FRUITED`/`PAID_DOUBLE`).
- Consultas por setor (`GET /grants/by-sector/{setor}` e
  `GET /requests/by-sector/{setor}`) para Admin/Coord com filtro opcional por
  subsecretaria (`?subsetor=`).

### Added

- Endpoints de reset de senha (`/forgot-password`, `/reset-password`) com token
  de propósito `password_reset` e e-mail via Mailtrap.
- Suporte a feriados brasileiros (estado do PR) nas validações de férias.