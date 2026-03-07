# Internum API

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supported-336791?logo=postgresql)
![Tests](https://img.shields.io/github/actions/workflow/status/pedronora/internum-api/lint-and-test.yaml?label=Tests)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📌 Sobre o projeto

A **Internum API** é o backend de uma **intranet corporativa para um Registro de Imóveis**, voltada exclusivamente para o **público interno** da instituição.

Esta API centraliza operações relacionadas a:

- Gestão de usuários e permissões
- Gestão de avisos internos
- Repositório de ementas
- Biblioteca e acervo digital internos
- Geração e envio de e-mails
- Workflows e módulos administrativos
- Persistência e segurança dos dados

Construída com **FastAPI**, **SQLAlchemy**, **PostgreSQL** e **Alembic**, a aplicação segue uma arquitetura modular e organizada, facilitando escalabilidade e manutenção.

---

## 🚀 Tecnologias principais

- **Python 3.13+**
- **FastAPI**
- **SQLAlchemy 2.0 / Async**
- **PostgreSQL**
- **Alembic**
- **Pydantic**
- **Poetry**
- **Docker & Docker Compose**
- **GitHub Actions (lint + test)**

---

## 📁 Estrutura do projeto

```text
.
├── alembic.ini
├── internum
│   ├── api
│   │   ├── main.py
│   │   └── schemas.py
│   ├── app.py
│   ├── core
│   │   ├── database.py
│   │   ├── email.py
│   │   ├── models
│   │   │   ├── __init__.py
│   │   │   ├── mixins.py
│   │   │   └── registry.py
│   │   ├── permissions.py
│   │   ├── scheduler
│   │   │   └── scheduler.py
│   │   ├── security.py
│   │   └── settings.py
│   ├── infra
│   │   ├── compose.yaml
│   │   └── orchestrate.sh
│   ├── __init__.py
│   ├── modules
│   │   ├── auth
│   │   │   ├── jobs.py
│   │   │   ├── models.py
│   │   │   ├── routers.py
│   │   │   └── schemas.py
│   │   ├── home
│   │   │   ├── routers.py
│   │   │   ├── schemas.py
│   │   │   └── services.py
│   │   ├── legal_briefs
│   │   │   ├── models.py
│   │   │   ├── routers.py
│   │   │   └── schemas.py
│   │   ├── library
│   │   │   ├── enums.py
│   │   │   ├── jobs.py
│   │   │   ├── models.py
│   │   │   ├── routers.py
│   │   │   └── schemas.py
│   │   ├── notices
│   │   │   ├── models.py
│   │   │   ├── routers.py
│   │   │   └── schemas.py
│   │   └── users
│   │       ├── enums.py
│   │       ├── models.py
│   │       ├── routers.py
│   │       └── schemas.py
│   ├── scripts
│   │   └── seed_admin.py
│   └── utils
│       └── datetime.py
├── migrations
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions
│       └── 504a0de55569_initial_tables.py
├── poetry.lock
├── pyproject.toml
├── README.md
└── tests
    ├── conftest.py
    ├── __init__.py
    ├── test_auth.py
    ├── test_home.py
    ├── test_jobs.py
    ├── test_legal_brief.py
    ├── test_library_books.py
    ├── test_library_loans.py
    ├── test_notice.py
    ├── test_security.py
    ├── test_status.py
    └── test_user.py

19 directories, 59 files
```

---

## 🛠️ Instalação e uso (modo desenvolvimento)

1. Clonar o repositório

```bash
git clone https://github.com/pedronora/internum-api.git
cd internum-api
```

2. Instalar dependências

```bash
poetry install
```

3. Criar arquivo `.env.development`

```bash
SECRET_KEY='...'
ALGORITHM='...'
ACCESS_TOKEN_EXPIRE_MINUTES=999
REFRESH_COOKIE_NAME='...'
REFRESH_COOKIE_PATH='...'
REFRESH_TOKEN_EXPIRE_DAYS=999
REFRESH_COOKIE_MAX_AGE=999
RESET_TOKEN_EXPIRE_MINUTES=999

FRONTEND_URL='...'

SECURE_COOKIE=...
REFRESH_COOKIE_SAMESITE='...'

POSTGRES_HOST=...
POSTGRES_PORT=...
POSTGRES_USER=...
POSTGRES_DB=...
POSTGRES_PASSWORD=...
DATABASE_URL=postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB

ADMIN_NAME='...'
ADMIN_USERNAME='...'
ADMIN_EMAIL='...'
ADMIN_PASSWORD=''
ADMIN_BIRTHDAY='YYYY-MM-DD'

MAILTRAP_TOKEN='...'
```

---

4. Rodar migrações

```bash
poetry run alembic upgrade head
```

5. Iniciar servidor

```bash
poetry run task run
```

A API estará em:
👉 http://localhost:8000

👉 Documentação automática: `/docs` ou `/redoc`

## 🧪 Testes

1. Rodar linters e formatadores:

```bash
poetry run task format
```

2. Rodar todos os testes

```bash
poetry run task test
```

## 🐳 Deploy (Docker + TrueNAS)

1. Construir a imagem do backend localmente:

```bash
docker build -t internum-api:0.1.0 .
```

2. Exportar a imagem para arquivo:

```bash
docker save internum-api:0.1.0 -o internum-api-0.1.0.tar
```

3. No TrueNAS, importar a imagem:

```bash
docker load -i internum-api-0.1.0.tar
```

4. No TrueNAS, criar a aplicação/container usando a imagem importada (`internum-api:0.1.0`).

5. Configurar as variáveis de ambiente de produção no painel (ex.: `POSTGRES_*`, `DATABASE_URL`, `SECRET_KEY`, `MAILTRAP_TOKEN`).

Observações:
- A imagem já possui `ENTRYPOINT` para aguardar o banco e iniciar a API.
- Por padrão, as migrations são aplicadas no startup (`RUN_MIGRATIONS=true`).
- Garanta conectividade da API com o banco de dados e persistência no serviço de banco.

---

## 📡 Estrutura dos módulos

- auth – autenticação, tokens, login, permissões

- users – CRUD de usuários internos

- home – dados do painel/boas-vindas

- notices – avisos internos do RI

- library – biblioteca técnica interna (livros, empréstimos, categorias)

- legal_briefs – Ementas de entendimentos jurídicos consolidados internamente

- core/email – serviço de envio assíncrono de e-mails

## 👤 Autor

**Pedro Nora**

[![GitHub](https://img.shields.io/badge/GitHub-pedronora-181717?logo=github)](https://github.com/pedronora)  
[![Email](https://img.shields.io/badge/Email-pedro@nora.vc-blue?logo=gmail&logoColor=white)](mailto:pedro@nora.vc)

---

## 📄 Licença

Distribuído sob a licença MIT.

Consulte o arquivo LICENSE para mais detalhes.
