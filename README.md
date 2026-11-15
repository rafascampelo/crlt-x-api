# Ctrl X Backend

## Autenticação

Configure `DATABASE_URL`, `SECRET_KEY` aleatória (mínimo 32 caracteres),
`JWT_ISSUER`, `JWT_AUDIENCE` e `CORS_ORIGINS` (origens explícitas separadas por
vírgula) no ambiente; execute `python -m alembic upgrade head` antes de iniciar.
Defina `APP_ENV=production` em produção e use HTTPS.

`POST /api/v1/auth/register` recebe, por exemplo:

```json
{"email":"person@example.test","password":"fake-password-123","full_name":"Fake Person","role":"PATIENT"}
```

O papel também pode ser `PROFESSIONAL`. Resposta 201: `{"id":"<uuid>",
"email":"person@example.test","role":"PATIENT"}`. Email duplicado retorna
409 e payload inválido 422. A senha exige 12 a 128 caracteres e não é retornada.

`POST /api/v1/auth/login` recebe email e senha e responde com os dados públicos
do usuário. O navegador deve enviar `Origin` de `CORS_ORIGINS` e usar
`credentials: "include"`. O servidor emite cookie HttpOnly, SameSite=Lax,
Secure fora de desenvolvimento, válido por 15 minutos. `GET /api/v1/auth/me`
retorna o usuário da sessão; token ausente, inválido ou expirado retorna 401.
Não armazene tokens no localStorage. Não há refresh token: ao expirar, o usuário
precisa entrar novamente. Em produção, frontend e API devem compartilhar o mesmo
site para SameSite=Lax; operações futuras autenticadas que alterem dados devem
verificar Origin e implementar proteção CSRF apropriada. Revogação antecipada de
tokens e limitação de tentativas ainda precisam ser implementadas.

## Fluxo de desenvolvimento

Fluxo obrigatório: `feature/<nome-em-kebab-case>` → PR para `develop` → PR de
`develop` para `prod`. Para cada mudança, crie uma branch específica a partir da
`develop` atualizada antes de editar arquivos. Nunca trabalhe diretamente em
`develop` ou `prod`; não faça push ou merge sem autorização explícita. Somente
push em `prod`, após CI e aprovação do Environment `production`, pode publicar.
Branches feature e `develop` executam CI sem deploy.

Commits aceitos: `feat`, `fix`, `refactor` ou `tests`, seguidos por uma descrição
curta, imperativa e em inglês, por exemplo `feat: add clinical record form`.
Consulte [CONTRIBUTING.md](CONTRIBUTING.md) antes de iniciar uma mudança.

## Visão do produto

Ctrl X é uma aplicação web responsiva, acessível pelo navegador em desktop,
tablet e celular. O frontend Next.js é publicado na Vercel e a API FastAPI
no Railway.

Pipeline do backend: [CI-CD.md](CI-CD.md). PRs e `develop` executam somente CI;
push em `prod` publica via Railway apenas após CI e proteção do Environment.
As migrações agora estão inicializadas; defina `DATABASE_URL` antes de executar
`python -m alembic upgrade head`. O baseline ainda não contém tabelas de negócio.

## Preparação da base

O desenho inicial está em [docs/architecture.md](docs/architecture.md) e
[docs/api-design.md](docs/api-design.md). As pastas por camada estão reservadas;
apenas `/health` está implementado. O ambiente Alembic está inicializado com
um baseline vazio e validação de migrações na CI.

Alternativa de preparação com uv (sem ativar o ambiente):

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.lock
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

As dependências Python de OCR não instalam o executável Tesseract. Docker Desktop
e Tesseract são instalações separadas no Windows. A integração com banco e o
processamento de documentos serão implementados em incrementos posteriores.

## Prerequisites (Windows)
- Python 3.12+, Docker Desktop with Linux containers / Compose v2
- Tesseract OCR installed on Windows, with Portuguese (`por`) and English (`eng`) language data

## Local setup (PowerShell)
```powershell
Copy-Item .env.example .env
# Edit .env and replace CHANGE_ME, CHANGE_ROOT_ME, SECRET_KEY with strong unique values.
docker compose up -d
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.

Run tests in a separate activated PowerShell session:
```powershell
python -m pytest
python -m ruff check .
```

Tesseract check:
```powershell
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --list-langs
```

The development MySQL service is bound to `127.0.0.1:3307` (container 3306).
Alembic has an empty baseline; application database sessions and business models
are not implemented yet. Migration commands read `DATABASE_URL` from the process
environment, not from `.env` automatically. See CI-CD.md for the separate disposable
CI database. `.env` is local only; do not use real patient data.
