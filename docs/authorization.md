# Autorização — Unidades, Perfis e Permissões

Este documento é a referência da matriz de autorização do Internum. A fonte
de verdade no código é `internum/core/authorization.py`; o frontend apenas
espelha os mesmos valores em `src/composables/useAuthorization.js`.

## 1. Princípios

- **Lotação não concede permissão.** `unidade` e `subunidade` descrevem onde a
  pessoa trabalha; quem concede acesso são os **perfis** (`roles`).
- **Perfis representam funções de trabalho**, não níveis hierárquicos genéricos.
  Uma pessoa pode ter mais de um perfil.
- **A API é a autoridade.** O frontend esconde ações e rotas sem permissão, mas
  toda decisão é revalidada no backend.
- **Permissões não vão no JWT.** Elas são derivadas dos perfis e devolvidas em
  `GET /api/v1/users/me` (`roles` + `permissions`).

## 2. Unidades

| Valor      | Rótulo na UI | Observação                                              |
| ---------- | ------------ | ------------------------------------------------------- |
| `direcao`  | Direção      | Oficial/Suboficial — nível de decisão                   |
| `registro` | Registro     | Inclui Atendimento e Digitalização                      |
| `gestao`   | Gestão       | Nível executivo/meio                                    |

`subunidade` é **texto livre e opcional**. As sugestões
(`Atendimento`, `Digitalização`, `Pessoas`, `Financeiro`,
`Compras/Patrimônio`, `TI`) servem apenas para orientar o cadastro e podem
ser alteradas sem migration. A unidade `gestao` **não** exige subunidade.

`Apoio` foi removido. O antigo rótulo “Administrativo” passou a ser “Gestão”.

## 3. Perfis

| Perfil                 | Descrição                                      |
| ---------------------- | ---------------------------------------------- |
| `oficial`              | Oficial — conta única, criada pelo seed        |
| `suboficial`           | Suboficial — decisão                           |
| `coord_registro`       | Coordenação do Registro                        |
| `coord_gestao`         | Coordenação da Gestão                          |
| `gestor_pessoas`       | Gestão de pessoas (RH)                         |
| `colaborador_registro` | Colaborador do Registro                        |
| `colaborador_gestao`   | Colaborador da Gestão                          |

O perfil `admin` foi eliminado. A organização tem **um único `oficial`**, e a
conta é criada exclusivamente por `internum/scripts/seed_oficial.py`. A API
nunca atribui o perfil `oficial`; um índice único parcial no banco
(`uq_user_roles_single_oficial`) garante a unicidade.

### 3.1 Hierarquia de atribuição

| Ator         | Pode atribuir/remover                                        |
| ------------ | ------------------------------------------------------------ |
| `oficial`    | Todos os perfis, exceto `oficial`                            |
| `suboficial` | Todos os perfis, exceto `oficial` e `suboficial`             |
| Demais       | Nenhum                                                       |

Regras adicionais:

- Ninguém altera os próprios perfis.
- O último `oficial` ativo não pode ser removido/desativado.
- A conta do `oficial` só pode ser editada ou desativada pelo próprio
  oficial. Suboficial, coordenação e gestão recebem 403.
- Coordenação, gestão de pessoas e colaboradores criam usuários **sem
  perfil**; o seletor de perfis só aparece para oficial e suboficial.
- Alterar perfis exige `users:assign_roles` **e** que todos os perfis
  adicionados/removidos estejam na hierarquia do ator.

## 4. Catálogo de permissões

| Permissão                  | Significado                                                        |
| -------------------------- | ------------------------------------------------------------------ |
| `users:create`             | Criar usuários                                                     |
| `users:read`               | Ver o diretório público de colegas                                 |
| `users:read_sensitive`     | Ver CPF, salário e dados completos de usuários                     |
| `users:edit_profile`       | Editar nome, username, CPF, e-mail, aniversário e telefone         |
| `users:edit_employment`    | Editar unidade, subunidade, admissão, rescisão e status ativo      |
| `users:edit_salary`        | Editar salário bruto                                               |
| `users:assign_roles`       | Atribuir/remover perfis (respeitando a hierarquia)                 |
| `users:change_password`    | Trocar a senha de qualquer usuário (exclusivo do oficial)          |
| `legal_briefs:manage`      | Criar/editar/cancelar ementas                                      |
| `notices:manage`           | Criar/gerir avisos                                                 |
| `library:manage`           | Gerir livros e empréstimos                                         |
| `vacation:read_all`        | Ver férias de qualquer unidade                                     |
| `vacation:manage_all`      | Aprovar/rejeitar solicitações e gerir concessões de qualquer unidade |
| `vacation:confirm_fruition`| Confirmar fruição de concessões                                    |

## 5. Matriz perfil × permissão

| Permissão                   | oficial | suboficial | coord_registro | coord_gestao | gestor_pessoas | colab_registro | colab_gestao |
| --------------------------- | :-----: | :--------: | :------------: | :----------: | :------------: | :------------: | :----------: |
| `users:create`              |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:read`                |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       ✔        |      ✔       |
| `users:read_sensitive`      |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_profile`        |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_employment`     |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_salary`         |    ✔    |     ✔      |       —        |      —       |       ✔        |       —        |      —       |
| `users:assign_roles`        |    ✔    |     ✔      |       —        |      —       |       —        |       —        |      —       |
| `users:change_password`     |    ✔    |     —      |       —        |      —       |       —        |       —        |      —       |
| `legal_briefs:manage`       |    ✔    |     ✔      |       ✔        |      —       |       —        |       —        |      —       |
| `notices:manage`            |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `library:manage`            |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:read_all`         |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:manage_all`       |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:confirm_fruition` |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |

`oficial` recebe **todas** as permissões. `suboficial` recebe todas, exceto
`users:change_password`: ele não pode assumir a conta de outro usuário.
`gestor_pessoas` é a coordenação acrescida de `users:edit_salary`.

## 6. Edição de usuário (campo a campo)

`PUT /api/v1/users/{id}` aplica a permissão de cada campo:

| Campo                                                        | Permissão                |
| ------------------------------------------------------------ | ------------------------ |
| `name`, `username`, `cpf`, `email`, `birthday`, `phone`      | `users:edit_profile`     |
| `unidade`, `subunidade`, `hiring_date`, `termination_date`, `active` | `users:edit_employment` |
| `gross_salary`                                               | `users:edit_salary`      |
| `roles`                                                      | `users:assign_roles`     |

Exceção: o próprio usuário pode editar `name`, `username`, `email`,
`birthday` e `phone` via `PUT /users/{id}`, mas **nunca** os próprios perfis.
O frontend (Meu Perfil) envia somente esses campos.

A conta do `oficial` é protegida por um guard adicional: qualquer outro
usuário recebe 403 ao tentar editar ou desativar o oficial
(`PUT`/`DELETE /users/{id}`). Isso impede que um suboficial troque o e-mail do
oficial e use a recuperação de senha para assumir a conta.

## 7. Endpoints relevantes

| Endpoint                                  | Permissão                          | Retorno                          |
| ----------------------------------------- | ---------------------------------- | -------------------------------- |
| `GET /api/v1/users/me`                    | autenticado                        | `UserSelf` (`roles` + `permissions`) |
| `GET /api/v1/users/directory`             | `users:read`                       | `UserPublic` (sem CPF/salário)   |
| `GET /api/v1/users/`                      | `users:read_sensitive`             | `UserRead`                       |
| `GET /api/v1/users/{id}`                  | `users:read_sensitive`             | `UserRead`                       |
| `POST /api/v1/users/`                     | `users:create`                     | `UserRead`                       |
| `PUT /api/v1/users/{id}`                  | por campo (tabela acima)           | `UserRead`                       |
| `DELETE /api/v1/users/{id}`               | `users:edit_employment`            | 204                              |
| `POST /api/v1/users/{id}/change-password` | self ou `users:change_password`    | 200 (sessões do alvo revogadas)  |
| `GET /api/v1/vacation/grants/by-unit/{u}` | `vacation:manage_all`              | concessões da unidade            |
| `GET /api/v1/vacation/requests/by-unit/{u}` | `vacation:manage_all`            | solicitações da unidade          |

Os endpoints `by-unit` aceitam `?subunidade=` opcional. As rotas de escrita de
férias usam `vacation:manage_all`; a confirmação de fruição usa
`vacation:confirm_fruition`.

Na troca de senha, a autoalteração exige `old_password`. O `oficial` pode
trocar a senha de qualquer usuário sem informar a senha antiga; a resposta
traz `access_token: null` e todas as sessões do alvo são revogadas. Nenhum
outro perfil troca a senha de terceiros.

## 8. Frontend

- `authStore.can(permission)` decide ações e itens de menu.
- Rotas usam `meta.permission` e o guard redireciona para `Home` quando falta
  permissão.
- Rótulos e opções de unidade/perfil ficam em
  `src/composables/useAuthorization.js` (`roleLabel`, `roleColor`,
  `unidadeLabel`, `assignableRoles`).
- O diretório de colegas (`/colaboradores`) usa `UsersService.directory()` e
  mostra apenas nome, username, unidade/subunidade, e-mail, telefone e perfis.

## 9. Proteções de autenticação

- **Rate limit**: `/token`, `/refresh_token`, `/forgot-password` e
  `/reset-password` são limitados por IP (`slowapi`). Os valores ficam em
  `RATE_LIMIT_LOGIN`, `RATE_LIMIT_REFRESH`, `RATE_LIMIT_FORGOT_PASSWORD` e
  `RATE_LIMIT_RESET_PASSWORD`. Ao exceder, a API responde `429` com
  `Retry-After`.
- **Hash do reset**: `password_reset_tokens` guarda somente
  `sha256(token)`; o token cru só existe no link enviado por e-mail.
- **Headers**: toda resposta da API traz CSP restritiva,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, COOP/CORP e, quando `SECURE_COOKIE=True`, HSTS.
