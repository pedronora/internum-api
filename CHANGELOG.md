# Changelog — internum-api

Todas as mudanças relevantes desta imagem serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o versionamento segue o padrão [Semantic Versioning](https://semver.org/lang/pt-BR/).

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