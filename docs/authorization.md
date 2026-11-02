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
| `admin`                | Administração técnica com break-glass          |
| `oficial`              | Oficial — decisão                              |
| `suboficial`           | Suboficial — decisão                           |
| `coord_registro`       | Coordenação do Registro                        |
| `coord_gestao`         | Coordenação da Gestão                          |
| `gestor_pessoas`       | Gestão de pessoas (RH)                         |
| `colaborador_registro` | Colaborador do Registro                        |
| `colaborador_gestao`   | Colaborador da Gestão                          |

### 3.1 Hierarquia de atribuição

| Ator             | Pode atribuir/remover                                        |
| ---------------- | ------------------------------------------------------------ |
| `admin`          | Qualquer perfil                                              |
| `oficial`        | Qualquer perfil, exceto `admin`                              |
| `suboficial`     | Qualquer perfil, exceto `admin`                              |
| `gestor_pessoas` | `colaborador_registro`, `colaborador_gestao`                 |
| `coord_gestao`   | `colaborador_gestao`                                         |
| `coord_registro` | `colaborador_registro`                                       |
| Demais           | Nenhum                                                       |

Regras adicionais:

- Ninguém altera os próprios perfis.
- O último `admin` ativo não pode ser removido/desativado.
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
| `legal_briefs:manage`      | Criar/editar/cancelar ementas                                      |
| `notices:manage`           | Criar/gerir avisos                                                 |
| `library:manage`           | Gerir livros e empréstimos                                         |
| `vacation:read_all`        | Ver férias de qualquer unidade                                     |
| `vacation:manage_all`      | Aprovar/rejeitar solicitações e gerir concessões de qualquer unidade |
| `vacation:confirm_fruition`| Confirmar fruição de concessões                                    |

## 5. Matriz perfil × permissão

| Permissão                   | admin | oficial | suboficial | coord_registro | coord_gestao | gestor_pessoas | colab_registro | colab_gestao |
| --------------------------- | :---: | :-----: | :--------: | :------------: | :----------: | :------------: | :------------: | :----------: |
| `users:create`              |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:read`                |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       ✔        |      ✔       |
| `users:read_sensitive`      |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_profile`        |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_employment`     |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `users:edit_salary`         |  ✔   |    ✔    |     ✔      |       —        |      —       |       ✔        |       —        |      —       |
| `users:assign_roles`        |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `legal_briefs:manage`       |  ✔   |    ✔    |     ✔      |       ✔        |      —       |       —        |       —        |      —       |
| `notices:manage`            |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `library:manage`            |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:read_all`         |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:manage_all`       |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |
| `vacation:confirm_fruition` |  ✔   |    ✔    |     ✔      |       ✔        |      ✔       |       ✔        |       —        |      —       |

`admin`, `oficial` e `suboficial` recebem **todas** as permissões
(break-glass). `gestor_pessoas` é a coordenação acrescida de
`users:edit_salary`.

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
| `GET /api/v1/vacation/grants/by-unit/{u}` | `vacation:manage_all`              | concessões da unidade            |
| `GET /api/v1/vacation/requests/by-unit/{u}` | `vacation:manage_all`            | solicitações da unidade          |

Os endpoints `by-unit` aceitam `?subunidade=` opcional. As rotas de escrita de
férias usam `vacation:manage_all`; a confirmação de fruição usa
`vacation:confirm_fruition`.

## 8. Frontend

- `authStore.can(permission)` decide ações e itens de menu.
- Rotas usam `meta.permission` e o guard redireciona para `Home` quando falta
  permissão.
- Rótulos e opções de unidade/perfil ficam em
  `src/composables/useAuthorization.js` (`roleLabel`, `roleColor`,
  `unidadeLabel`, `assignableRoles`).
- O diretório de colegas (`/colaboradores`) usa `UsersService.directory()` e
  mostra apenas nome, username, unidade/subunidade, e-mail, telefone e perfis.
