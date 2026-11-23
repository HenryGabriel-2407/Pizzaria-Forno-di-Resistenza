# Pizzaria Forno di Resistenza — API REST

[![Repositório no GitHub](https://img.shields.io/badge/GitHub-Pizzaria--Forno--di--Resistenza-181717?logo=github)](https://github.com/HenryGabriel-2407/Pizzaria-Forno-di-Resistenza)

Backend da API REST do **Sistema de Gestão para Pizzaria Forno di Resistenza**. Ele atende o aplicativo mobile [Garçom Digital](https://github.com/HenryGabriel-2407/garcom-digital-app) e concentra as regras de negócio, a persistência, a autenticação, o controle de acesso, a auditoria e o envio de e-mails do sistema.

- **Repositório:** [github.com/HenryGabriel-2407/Pizzaria-Forno-di-Resistenza](https://github.com/HenryGabriel-2407/Pizzaria-Forno-di-Resistenza)
- **Cliente mobile:** [`../garcom-digital-app`](https://github.com/HenryGabriel-2407/garcom-digital-app)
- **Licença:** MIT — Copyright (c) 2025 Henry Gabriel

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Importância acadêmica e potencial de negócio](#2-importância-acadêmica-e-potencial-de-negócio)
3. [Stack e requisitos](#3-stack-e-requisitos)
4. [Arquitetura e estrutura](#4-arquitetura-e-estrutura)
5. [Modelo de dados e migrações](#5-modelo-de-dados-e-migrações)
6. [Segurança, autenticação e auditoria](#6-segurança-autenticação-e-auditoria)
7. [API REST](#7-api-rest)
8. [Regras de negócio](#8-regras-de-negócio)
9. [Configuração](#9-configuração)
10. [Como executar](#10-como-executar)
11. [Testes e qualidade](#11-testes-e-qualidade)
12. [Documentação e artefatos](#12-documentação-e-artefatos)
13. [Limitações conhecidas](#13-limitações-conhecidas)
14. [Licença e autoria](#14-licença-e-autoria)

---

## 1. Visão geral

A API expõe **77 endpoints em 11 routers** para gerenciar:

- catálogo (produtos, combos, categorias, métodos de pagamento);
- clientes, endereços e funcionários;
- mesas com QR code, reservas e controle de ocupação;
- comandas (pedidos) com itens, cupons, pagamento, troco e histórico de status;
- códigos promocionais;
- logs de auditoria e estatísticas;
- login, recuperação de senha e envio de recibos por e-mail.

O sistema atende tanto o atendimento presencial (garçom/cozinha/admin) quanto o delivery. O aplicativo mobile consome a API via HTTP/JSON com token JWT Bearer; o banco é definido pela variável `DATABASE_URL`, com PostgreSQL recomendado para produção e SQLite utilizado nos testes automatizados.

---

## 2. Importância acadêmica e potencial de negócio

### 2.1 Acadêmica

O projeto é um caso completo de Engenharia de Software: modelagem (casos de uso, classes, ER e atividades), implementação com FastAPI/SQLAlchemy, migrações versionadas, testes automatizados e apresentação dos resultados. Destaques:

- **15 entidades** com chaves estrangeiras, restrições `CHECK`/`UNIQUE` e índices;
- **máquina de estados** explícita para comandas, com log de transições;
- **RBAC** com papéis `garcom`, `cozinha`, `admin`, `gerente`, além de clientes;
- **auditoria estruturada** com antes/depois, IP e User-Agent;
- **255 testes** automatizados e **95% de cobertura** registrados na apresentação do sistema.

### 2.2 Negócio

A API dá suporte a: redução de perdas com rastreabilidade de operações, campanhas com cupons e combos, fila de preparo para cozinha, fechamento de comandas com troco e recibo digital, gestão de mesas com QR e pedidos delivery. Não há pesquisa de mercado ou projeção financeira nos materiais do projeto; oportunidades como gateway de pagamento, notificações e SaaS multiunidade são evoluções possíveis, ainda não implementadas.

---

## 3. Stack e requisitos

| Camada | Tecnologia | Versão |
|---|---|---|
| Linguagem | Python | `^3.11` (`>=3.11,<4.0`) |
| Framework | FastAPI (extra `standard`, com Uvicorn) | `0.116.1` |
| Validação | Pydantic v2 + Pydantic Settings | `2.11.7` / `2.10.1` |
| ORM / SQL | SQLAlchemy 2.0 (mapped dataclasses) | `2.0.43` |
| Migrações | Alembic | `1.16.4` |
| Segurança | PyJWT + pwdlib (Argon2id) | `2.10.1` / `0.2.1` |
| Banco | PostgreSQL recomendado (`psycopg` 3 e `psycopg2`); SQLite nos testes | — |
| E-mail | `smtplib` + STARTTLS (biblioteca padrão) | — |
| Testes | pytest, pytest-cov, httpx | `8.4.1`, `6.2.1`, `0.28.1` |
| Qualidade | Ruff + Taskipy | `0.12.8`, `1.14.1` |

**Pré-requisitos:** Python 3.11+, [Poetry](https://python-poetry.org/), um banco acessível (PostgreSQL ou SQLite para desenvolvimento) e uma conta SMTP para recuperação de senha e envio de recibos. As versões estão travadas em `pizzaria-system/poetry.lock`.

---

## 4. Arquitetura e estrutura

```text
App mobile (React Native/Expo)  ──HTTP/JSON + JWT──▶  API FastAPI
                                                      │
                                                      ├─ routers/  (11 módulos)
                                                      ├─ pizzaria_system/ (núcleo)
                                                      └─ SQLAlchemy ──▶ banco relacional
```

```text
Pizzaria-Forno-di-Resistenza/
├── Sistema_sobre/                  # diagramas, mockups e PDFs acadêmicos
├── Imagens/                        # logotipo e imagens da marca
├── LICENSE                         # MIT
└── pizzaria-system/
    ├── pizzaria_system/
    │   ├── app.py                  # FastAPI, CORS, lifespan, registro dos routers
    │   ├── settings.py             # variáveis de ambiente
    │   ├── database.py             # engine, sessões e dependency get_session
    │   ├── models.py               # 15 tabelas
    │   ├── schemas.py              # Pydantic v2
    │   ├── security.py             # JWT e hash de senha
    │   ├── audit.py                # registro de auditoria
    │   ├── email_utils.py          # e-mails, recibo HTML e SMTP
    │   ├── seeds.py                # administrador inicial
    │   └── templates/reset_password.html
    ├── routers/                    # auth, produto, combo, categorias, clientes,
    │                               # mesa, promoções, funcionário, auditoria, comanda...
    ├── migrations/versions/        # cadeia Alembic (12 revisões)
    ├── tests/                      # 255 testes + conftest.py
    ├── pyproject.toml              # dependências, Ruff e tarefas Taskipy
    ├── poetry.lock
    └── alembic.ini
```

A aplicação não usa prefixo de versão na URL (por exemplo, `/api/v1`). Os routers são registrados diretamente em `app.py`. No startup (`lifespan`), `criar_primeiro_admin()` cria o administrador caso ainda não exista nenhum funcionário.

---

## 5. Modelo de dados e migrações

### 5.1 Tabelas (15)

| Tabela | Finalidade |
|---|---|
| `categoria_produto` | Categorias do cardápio |
| `produto` | Produtos (preço, imagem, categoria, tempo de preparo, popular, disponível) |
| `combo` | Combos promocionais |
| `combo_produto` | Associação N:N combo ↔ produto |
| `metodo_pagamento` | Formas de pagamento (nome único, ativo) |
| `cliente` | Clientes (e-mail/documento únicos, senha hash, ativo) |
| `endereco_cliente` | Endereços do cliente (apelido, rua, CEP, padrão) |
| `funcionario` | Equipe (nome, e-mail, senha hash, cargo, ativo) |
| `mesa` | Mesas (número, lugares, status, `codigo_qr`) |
| `comanda` | Pedidos (valores, status, pagamento, origem) |
| `pedido_item` | Itens com produto **ou** combo (restrição XOR) |
| `status_comanda_log` | Histórico de transições de status |
| `cod_promocional` | Cupons (código, percentual, validade, ativo) |
| `audit_log` | Auditoria (ação, tabela, antes/depois, IP, User-Agent) |
| `password_reset_token` | Tokens de recuperação (hash do código, expiração, uso) |

**Relacionamentos principais:** `produto` N:1 categoria e N:N combo; `endereco_cliente` N:1 cliente; `comanda` N:1 cliente **ou** mesa, N:1 funcionário (garçom), N:1 método de pagamento e N:1 opcional cupom; `pedido_item` N:1 comanda; `status_comanda_log` N:1 comanda. Há índices em `comanda` e em várias colunas de `audit_log`.

### 5.2 Migrações

A cadeia Alembic é linear, com 12 revisões:

```text
59e46e006efa → 5226554a93e6 → a05db4ce6772 → 13a33ef63c38 → 7b8861698aab
→ 129cfc05d2e0 → 040a1eeca1e6 → 7ae0384eb33a → 646404b0c9ec → a039e367a67a
→ 9d1aa8339fdc → f19bc380e274 (head)
```

- `13a33ef63c38` cria as 15 tabelas de domínio, FKs, `CHECK`s e índices;
- `9d1aa8339fdc` cria `password_reset_token`;
- `migrations/env.py` sobrescreve a URL do `alembic.ini` com `Settings().DATABASE_URL`;
- algumas revisões intermediárias são *no-op* (`pass`);
- aplique com `poetry run alembic upgrade head`.

---

## 6. Segurança, autenticação e auditoria

### 6.1 Autenticação

- `POST /auth/token` usa OAuth2 Password Flow (`username` = e-mail); procura o usuário em `cliente` e depois em `funcionario`;
- **JWT Bearer** com payload `{ sub, tipo: "cliente"|"funcionario", cargo?, exp }` e validade definida por `ACCESS_TOKEN_EXPIRE_MINUTES`;
- **Argon2id** via `pwdlib` para senhas e para o código de recuperação;
- recuperação: código de 6 dígitos (`SystemRandom`), TTL de **30 minutos**, uso único, armazenado apenas como hash. A resposta de `forgot-password` não revela se o e-mail existe.

### 6.2 Autorização

Controle explícito por endpoint, com papéis `admin`, `gerente`, `garcom`, `cozinha`, clientes e proprietários de recursos. Cliente vê apenas suas comandas/dados; funcionários alteram apenas o próprio perfil; administradores gerenciam equipe e catálogo. A consulta de auditoria é restrita a admin/gerente.

### 6.3 Auditoria

`audit.log_audit()` registra `usuario_tipo`, `usuario_id`/`funcionario_id`, `acao`, `tabela_afetada`, `registro_id`, `dados_anteriores`, `dados_novos`, IP e User-Agent. São instrumentados 25 eventos de produtos, combos, clientes/endereços/senha e comandas/itens/status. Há endpoints de listagem com filtros, actions/tabelas disponíveis e estatísticas por ação.

---

## 7. API REST

Base local: `http://127.0.0.1:8000`. Documentação interativa (Swagger UI) em **`/docs`**; especificação OpenAPI em `/openapi.json`.

**Legenda:** `P` público · `A` autenticado · `F` funcionário · `Adm` admin · `Adm/Ger` admin ou gerente · `Próprio` dono do recurso.

### 7.1 Autenticação (3)

| Método | Caminho | Acesso | Finalidade |
|---|---|---|---|
| POST | `/auth/token` | P | Login e emissão do JWT |
| POST | `/auth/forgot-password` | P | Envio do código de 6 dígitos por e-mail |
| POST | `/auth/reset-password` | P | Redefinição de senha |

### 7.2 Catálogo (22)

| Método | Caminho | Acesso | Finalidade |
|---|---|---|---|
| POST · GET | `/produtos/` | Adm · P | Cria · lista (`disponivel`, `categoria_id`) |
| GET · PUT · DELETE | `/produtos/{produto_id}` | P · Adm · Adm | Detalhe · atualiza · exclui (bloqueia se em combo) |
| POST · GET | `/combos/` | Adm · P | Cria · lista (`disponivel`, `popular`) |
| GET · PUT · DELETE | `/combos/{combo_id}` | P · Adm · Adm | Detalhe · atualiza · exclui |
| POST · DELETE | `/combos/{combo_id}/produtos/{produto_id}` | Adm | Adiciona · remove produto do combo |
| GET · POST | `/categorias/` | P · Adm | Lista · cria |
| GET · PUT · DELETE | `/categorias/{categoria_id}` | P · Adm · Adm | Detalhe · atualiza · exclui |
| GET · POST | `/metodos-pagamento/` | P · F | Lista · cria |
| GET · PUT · DELETE | `/metodos-pagamento/{metodo_id}` | P · F · F | Detalhe · atualiza · exclui |

### 7.3 Clientes, mesas e promoções (27)

| Método | Caminho | Acesso | Finalidade |
|---|---|---|---|
| POST | `/clientes/` | P | Cadastro com endereços aninhados |
| GET | `/clientes/` | Adm | Lista filtrável (`search`, `ativo`, `order_by`) |
| GET | `/clientes/me` | Cliente | Perfil do cliente |
| GET | `/clientes/busca?q=` | F | Busca por nome/e-mail/documento |
| GET · PUT · DELETE | `/clientes/{cliente_id}` | Adm/Próprio · Adm/Próprio · Adm | Detalhe · atualiza · exclui |
| POST | `/clientes/{cliente_id}/enderecos` | Adm/Próprio | Adiciona endereço |
| PUT · DELETE | `/clientes/enderecos/{endereco_id}` | Adm/Próprio | Atualiza · remove endereço |
| POST | `/clientes/{cliente_id}/alterar-senha` | Próprio | Troca de senha |
| POST | `/clientes/{cliente_id}/ativar` · `/desativar` | Adm · Adm/Próprio | Ativação e desativação |
| GET · POST | `/mesas/` | P · F | Lista · cria (gera `codigo_qr`) |
| GET · PUT · DELETE | `/mesas/{mesa_id}` | P · F · F | Detalhe · atualiza · exclui |
| POST | `/mesas/{mesa_id}/ocupar` · `/liberar` · `/reservar` | F | Transições de status da mesa |
| GET · POST | `/promocoes/` | P · F | Lista · cria |
| GET · PUT · DELETE | `/promocoes/{promo_id}` | P · F · F | Detalhe · atualiza · exclui |
| POST | `/promocoes/validar` | P | Valida cupom e calcula desconto |

### 7.4 Funcionários, auditoria e comandas (25)

| Método | Caminho | Acesso | Finalidade |
|---|---|---|---|
| POST · GET | `/funcionarios/` | Adm | Cria · lista (`ativo`, `cargo`) |
| GET | `/funcionarios/me` | F | Perfil do funcionário autenticado |
| GET · PUT · DELETE | `/funcionarios/{funcionario_id}` | Adm/Próprio · Adm/Próprio · Adm | Detalhe · atualiza · exclui |
| POST | `/funcionarios/{id}/alterar-senha` | Próprio | Troca de senha |
| POST | `/funcionarios/{id}/ativar` · `/desativar` | Adm | Ativação e desativação |
| GET | `/audit-logs/` | Adm/Ger | Lista com filtros e paginação |
| GET | `/audit-logs/{log_id}` | Adm/Ger | Detalhe do log |
| GET | `/audit-logs/acoes/disponiveis` | Adm/Ger | Ações registradas |
| GET | `/audit-logs/tabelas/disponiveis` | Adm/Ger | Tabelas auditadas |
| GET | `/audit-logs/estatisticas/por-acao` | Adm/Ger | Contagem por ação |
| POST · GET | `/comandas/` | A | Cria · lista (status, entrega, mesa, período) |
| GET · PUT · DELETE | `/comandas/{comanda_id}` | A · F · F | Detalhe · atualiza · exclui |
| POST | `/comandas/{comanda_id}/itens` | A/Próprio | Adiciona item |
| PUT · DELETE | `/comandas/itens/{item_id}` | A/Próprio | Edita · remove item |
| POST | `/comandas/{comanda_id}/status` | A | Máquina de estados |
| POST | `/comandas/{comanda_id}/enviar-recibo` | F | Envio de recibo por e-mail |
| GET | `/comandas/{comanda_id}/status-logs` | A | Histórico de status |

**Total: 77 endpoints em 11 routers.**

---

## 8. Regras de negócio

### 8.1 Máquina de estados da comanda

| Estado atual | Transições válidas |
|---|---|
| `aberta` | `em_preparo`, `cancelada` |
| `em_preparo` | `pronta`, `cancelada`, `aberta` |
| `pronta` | `entregue`, `cancelada`, `paga`, `aberta` |
| `entregue` | `paga` |
| `cancelada` / `paga` | terminais |

Qualquer funcionário pode aplicar transições válidas; o cliente apenas cancela uma comanda aberta. Ao pagar: `status_pagamento = 'pago'`, `data_finalizacao` preenchida, mesa liberada e recibo enviado por e-mail. Ao cancelar: `status_pagamento = 'falhou'`. Toda transição grava `status_comanda_log` e `audit_log`.

Adicionar/editar/remover item enquanto a comanda está `em_preparo` reverte para `aberta` e registra o motivo. Com status `pronta`, a alteração de itens é bloqueada com HTTP 400.

### 8.2 Outros comportamentos

- **Preços:** a API ignora valores enviados pelo cliente para `preco_unitario`/`subtotal` e busca os preços no catálogo; recalcula `preco_total`, `valor_a_pagar` e troco.
- **Cupons:** validam existência, `ativo` e validade; o desconto é aplicado sobre o valor informado. Não é possível excluir um cupom já usado.
- **Mesas:** `POST /mesas/` gera `codigo_qr = BASE_URL/mesa/{id}`; exclusões são bloqueadas se houver comandas.
- **Recibos:** `email_utils.gerar_html_recibo()` monta o HTML; o envio usa SMTP com STARTTLS. O PDF é gerado no app mobile, não no backend.
- **Integridade:** exclusões são bloqueadas quando há vínculos (produto em combo, categoria com produtos, cliente/mesa/método/funcionário com histórico).
- **Seed:** apenas o primeiro administrador, parametrizado por `ADMIN_EMAIL`, `ADMIN_PASSWORD` e `ADMIN_NAME`.

---

## 9. Configuração

Crie `.env` na raiz de `pizzaria-system/` (o `Settings` lê `./.env` em relação ao diretório corrente). Todas as variáveis abaixo são obrigatórias, exceto `BASE_URL`:

| Variável | Exemplo | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://pizzaria:senha@localhost:5432/pizzaria` | URL SQLAlchemy do banco |
| `SECRET_KEY` | *(gere com `python -c "import secrets; print(secrets.token_urlsafe(32))"`)* | Chave de assinatura JWT |
| `ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Validade do token |
| `ADMIN_EMAIL` | `admin@fornodiresistenza.com` | E-mail do admin inicial |
| `ADMIN_PASSWORD` | `troque-esta-senha` | Senha do admin inicial |
| `ADMIN_NAME` | `Administrador` | Nome do admin inicial |
| `BASE_URL` | `http://localhost:8000` | Prefixo do QR code das mesas (opcional) |
| `SMTP_SERVER` | `smtp.gmail.com` | Servidor SMTP |
| `SMTP_PORT` | `587` | Porta SMTP (STARTTLS) |
| `SMTP_FROM_EMAIL` | `contato@fornodiresistenza.com` | Remetente |
| `SMTP_PASSWORD` | `senha-de-app` | Credencial SMTP |

```dotenv
DATABASE_URL=postgresql+psycopg://pizzaria:senha@localhost:5432/pizzaria
SECRET_KEY=substitua-por-uma-chave-aleatoria-longa
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ADMIN_EMAIL=admin@fornodiresistenza.com
ADMIN_PASSWORD=troque-esta-senha
ADMIN_NAME=Administrador
BASE_URL=http://localhost:8000
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM_EMAIL=contato@fornodiresistenza.com
SMTP_PASSWORD=senha-de-app
```

O arquivo `.env` não é versionado (`gitignored`). Não existe `.env.example` no repositório.

---

## 10. Como executar

Todos os comandos devem ser executados dentro de `pizzaria-system/`, pois os imports dos routers são relativos a esse diretório.

```bash
cd /home/henry-gabriel/Documents/projetos/Pizzaria-Forno-di-Resistenza/pizzaria-system

# Instalar dependências
poetry install

# Criar o .env conforme a seção anterior

# Aplicar migrações
poetry run alembic upgrade head

# Subir a API (task Taskipy → fastapi dev pizzaria_system/app.py)
poetry run task run
```

A API ficará em `http://127.0.0.1:8000`, com Swagger UI em `/docs`. O administrador inicial é criado automaticamente no primeiro startup. Para produção, configure um servidor ASGI (o Uvicorn já vem com o extra `standard` do FastAPI) e restrinja o CORS.

Tarefas disponíveis em `pyproject.toml` (via `poetry run task <nome>`):

| Tarefa | Comando | Finalidade |
|---|---|---|
| `run` | `fastapi dev pizzaria_system/app.py` | Servidor de desenvolvimento com reload |
| `test` | `pytest -s -x --cov=pizzaria_system -vv` | Testes com cobertura (roda `lint` antes e gera `htmlcov`) |
| `lint` | `ruff check . && ruff check . --diff` | Análise estática |
| `format` | `ruff check . --fix && ruff format .` | Correção e formatação |

---

## 11. Testes e qualidade

```bash
cd pizzaria-system

poetry run task test          # lint + pytest com cobertura + htmlcov/
poetry run pytest -v          # somente os testes
poetry run pytest tests/test_comanda.py -q
poetry run task lint
poetry run task format
```

- **255 testes** em 12 arquivos: auditoria (26), categorias (18), clientes (31), promoções (30), comandas (22), combos (20), funcionários (31), mesas (29), métodos de pagamento (19), recuperação de senha (11), produtos (16) e segurança (2).
- `tests/conftest.py` usa um **SQLite temporário** com `dependency_overrides[get_session]`, portanto os testes não dependem do PostgreSQL de produção.
- A apresentação do sistema registra **95% de cobertura** (slide 18 de `Apresentação.pdf`, no projeto do app).
- Os testes cobrem CRUD, autorização (401/403), validações, máquina de estados, recuperação de senha e auditoria.

---

## 12. Documentação e artefatos

| Artefato | Local |
|---|---|
| Diagrama de casos de uso | `Sistema_sobre/Diagrama de Caso de Uso.png` |
| Diagrama de atividades | `Sistema_sobre/Diagrama de Atividade - Forno di Resistenza (1).pdf` |
| Diagrama de classes (lógico) | `Sistema_sobre/Diagrama de Classes - Modelo Lógico.png` |
| Diagrama ER (conceitual) | `Sistema_sobre/Diagrama Entidade-Relacionamento - Conceitual.png` |
| Mockups do site e autenticação | `Sistema_sobre/Pizzaria Forno di Resistenza*.pdf` |


> O arquivo `pizzaria-system/README.md` está vazio; este é o README principal do repositório.

---

## 13. Limitações conhecidas

- CORS irrestrito (`allow_origins=["*"]`) com `allow_credentials=True`;
- usuários desativados ainda conseguem login e usar tokens antigos (não há checagem de `ativo`);
- sem refresh token, revogação, `iss`/`aud`/`jti`, rate limiting ou bloqueio de tentativas;
- `desconto_aplicado`, `taxa_entrega`, `tipo_entrega` e status são strings livres; desconto/taxa enviados pelo cliente não são validados na criação da comanda;
- `UniqueConstraint(id_cliente, padrao)` em endereços impede mais de um endereço não padrão por cliente;
- datas *naive* e fusos misturados em expirações/validades; token de recuperação antigo não é invalidado ao emitir outro;
- falha de SMTP no `forgot-password` é engolida e a API responde 200 como se o e-mail tivesse sido enviado;
- auditoria não cobre login, recuperação de senha, funcionários, mesas, categorias, promoções e métodos de pagamento; o commit do log é separado da mutação;
- arquitetura plana (regras dentro dos routers), sem camada de serviços, sem versionamento da API e sem tratamento global de exceções;
- schemas e dependências órfãs (`PagamentoPix*`, `Carrinho*`, `qrcode`, `pillow`), README interno vazio, ausência de `.env.example` e migrações iniciais *no-op*.

---

## 14. Licença e autoria

Projeto desenvolvido por **Henry Gabriel** e distribuído sob a [licença MIT](./LICENSE) — `Copyright (c) 2025 Henry Gabriel`.

