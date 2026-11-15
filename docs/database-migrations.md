# Migrations do backend

## Arquitetura

Python 3.12, FastAPI, SQLAlchemy 2, Alembic e MySQL 8.4. O schema é versionado
em `alembic/versions/` e controlado pela tabela `alembic_version`; não há uma
segunda ferramenta nem sincronização automática via `create_all` em produção.

No PR, Backend CI usa somente MySQL descartável, valida upgrade, drift,
downgrade e novo upgrade, executa lint/testes, actionlint e build/smoke Docker.
O banco real nunca é configurado em jobs de PR.

Em push autorizado em `prod`, `deploy-production.yml` executa:

```text
validate (Backend CI, SHA exato e artefato com checksum)
  → database-migrations (aprovação do environment production)
  → production (Deploy API e health check público)
```

O job `database-migrations` envia o mesmo código validado ao serviço privado
**ctrl-x-migrations**, no mesmo projeto/environment do MySQL. O pacote temporário
tem um `railway.json` próprio gerado por `scripts.deploy_migrations`; não altera
a configuração da API. O pre-deploy executa `python -m scripts.db db:migrate`
dentro da rede Railway. Esse comando verifica MySQL 8.4, adquire GET_LOCK,
consulta revisões atuais/pendentes, aplica upgrade head e verifica a revisão.
O lock é mantido na mesma conexão do Alembic e liberado no finally.

O serviço então inicia um sentinel HTTP sem dados clínicos, após outra
verificação do schema. O job espera SUCCESS do ID exato retornado no upload;
falha de build, pre-deploy, readiness ou timeout impede o job da API via needs.
Não existe rollback automático. O sentinel fica ativo, sem domínio público;
esse serviço adicional e o segundo build têm custo. Não é um job efêmero.

Somente depois é enviado o pacote original para **ctrl-x-api**. Seu pre-deploy
executa `db:status --require-current`, sem DDL. Cada réplica também confere o
schema antes de iniciar Uvicorn. Deploy e /health público precisam passar.

A concorrência `backend-production`, sem cancelamento de execução em andamento,
cobre todo o fluxo. GET_LOCK protege também contra operadores concorrentes que
utilizem o comando padronizado. GitHub pode substituir runs pendentes; não há
garantia FIFO. Ambos os jobs rejeitam releases que já não sejam HEAD de prod.

## Comandos

Execute na raiz, com dependências de `requirements.lock` e variáveis exportadas
no processo. Os comandos de banco não carregam `.env` automaticamente.

```powershell
python -m scripts.db db:create --message "add assessment reference"
python -m scripts.db db:create --message "add assessment reference" --autogenerate
python -m scripts.db db:status
python -m scripts.db db:migrate
python -m scripts.db db:status --require-current
```

`db:status` lista revisão atual, head e quantidade de pendentes sem alterar dados.
`--require-current` retorna falha se houver diferença. `db:migrate` aplica apenas
revisões ainda não registradas. Reexecutar com schema atualizado não reaplica DDL.
`db:create` gera um arquivo versionado; autogenerate requer um banco local de
desenvolvimento e revisão manual do upgrade/downgrade antes do commit.

Em banco **local descartável**, Alembic permite reverter uma revisão:

```powershell
python -m scripts.db db:rollback --allow-local-rollback
```

Esse comando não oferece garantia de recuperação de dados. Não é permitido em
APP_ENV=production nem quando RAILWAY_ENVIRONMENT_ID está presente. Não execute
Alembic downgrade diretamente em produção para contornar esse controle.

## Ativação manual no GitHub e Railway

1. Criar serviço **ctrl-x-migrations** no mesmo projeto/environment **production**
   de ctrl-x-api/ctrl-x-mysql, após aprovar o custo. Não criar banco novo, volume,
   domínio público, cron ou GitHub Source nesse serviço. Usar uma réplica.
2. Em **ambos** os serviços de código, desconectar GitHub Source, autodeploy,
   previews e image auto-updates. Não basta selecionar prod ou Wait for CI.
   Nenhuma configuração remota foi inspecionada/alterada por esta implementação.
3. Em ctrl-x-migrations, deixar Start Command/configuração via arquivo, sem
   override do painel; o pacote inclui startCommand do sentinel e pre-deploy.
   Definir timeout finito de pre-deploy no painel (por exemplo 600s, revisado).
   Não ativar serverless/sleep automático no serviço sentinel.
4. Configurar APP_ENV=production e as referências de banco abaixo em ambos os
   serviços. O serviço de migrations não precisa de SECRET_KEY nem CORS.
5. No environment GitHub **production**, adicionar variável
   **RAILWAY_MIGRATIONS_SERVICE_ID**, UUID do serviço ctrl-x-migrations, distinto
   de RAILWAY_SERVICE_ID (API). Manter as demais configurações de CI-CD.md.
6. Manter regras sem bypass, CI/revisões obrigatórias e approval de production.
   Os dois jobs usam esse environment; GitHub pode solicitar aprovação em ambos.
   Um PR aprovado e merge em prod são o caminho de execução; não há dispatch.

Variáveis Railway, preferencialmente via Add Reference (conferir os nomes reais):

```text
APP_ENV=production
DB_USER=${{ctrl-x-mysql.MYSQLUSER}}
DB_PASSWORD=${{ctrl-x-mysql.MYSQLPASSWORD}}
DB_HOST=${{ctrl-x-mysql.RAILWAY_PRIVATE_DOMAIN}}
DB_PORT=3306
DB_NAME=${{ctrl-x-mysql.MYSQLDATABASE}}
```

As cinco DB_* têm prioridade; configuração parcial falha. Senha é original,
sem percent-encoding, tratada por SQLAlchemy URL.create. Alternativamente usar
DATABASE_URL mysql+pymysql já escapada. Nunca usar TCP público apenas para CI.
DB_HOST deve terminar em `.railway.internal`. Não cadastrar credenciais de MySQL
no GitHub Actions. O runner usa somente o project token RAILWAY_TOKEN para envio.

O GitHub também mantém RAILWAY_PROJECT_ID, RAILWAY_ENVIRONMENT_ID,
RAILWAY_SERVICE_ID e BACKEND_PRODUCTION_URL como variables, e RAILWAY_TOKEN como
secret do environment production. As configurações de App de promoção continuam
separadas no environment promotion e não são necessárias para acessar MySQL.

## Compatibilidade, backup e recuperação

Usar **Expand and Contract**: adicionar colunas/tabelas compatíveis; migrar dados
com plano revisado; atualizar consumidores; remover estruturas antigas somente
em release posterior. A API antiga continua atendendo durante a migration.
Não automatizar DROP DATABASE, reset, importação local ou DDL destrutivo.
Nenhum detector estático pode provar que uma migration é segura; revisão humana
de cada arquivo continua obrigatória, incluindo SQL e preservação de dados.

Antes de alteração crítica, operador autorizado deve verificar backup recente,
retenção, criptografia e cópia externa; para InnoDB, dump consistente com
`mysqldump --single-transaction`, sem DDL concorrente e sem senha na linha de
comando/log. Testar restore em MySQL isolado, migrations, integridade e acessos;
definir RPO/RTO. Nunca anexar dumps clínicos ao Actions ou ao repositório.

Na falha, a API nova não é publicada. Consultar o ID de deployment no Actions e
os logs Build/Pre-deploy/Deploy desse ID no Railway. Os logs padronizados mostram
somente versões/contagem e tipo do erro, sem URL/senha/conteúdo clínico. Logs
customizados em migrations exigem revisão para não vazar dados.

Conexão recusada: conferir serviço/environment, referências e DNS privado, sem
imprimir as variáveis. Schema pendente: consultar `db:status` dentro de um
container Railway autorizado com o código do release, nunca em railway run local
esperando acesso à rede privada. Não usar código de imagem antiga para consultar
as revisões novas. Código/revisão desconhecida ou vários heads exigem correção.

DDL MySQL pode fazer commit implícito; falha pode deixar schema parcial mesmo
sem atualizar alembic_version. Não repetir às cegas, stamp ou downgrade automático.
Inspecionar estado com operador autorizado e preferir migration corretiva
forward-only por PR. Rollback de código não desfaz DDL. Após falha do deploy,
schema expandido deve continuar compatível com API anterior. Restore de produção
e qualquer migration real nesta fase exigem autorização explícita.

O lock não fornece exactly-once distribuído nem atomicidade entre DDL e Railway.
Se migrations passarem e deploy falhar, permanecem aplicadas; reexecutar o fluxo
confere versões e só aplica pendentes. Serviços devem referenciar o mesmo banco;
startup da API detecta divergência de schema, mas configuração incorreta de um
banco com mesma versão requer conferência operacional antes da ativação.

## Validação local em 15/11/2026

- `python -m pytest -p no:cacheprovider` em Linux com MySQL 8.4 descartável:
  **146 passaram, nenhum pulado**, incluindo lock, falha de migration e
  propagação de erro para o job de deploy.
- `python -m ruff check .` e `git diff --check`: passaram.
- `docker build --progress=plain --tag ctrlx-backend:migrations-check .`: passou.
- actionlint 1.7.7 e ShellCheck, nos três workflows: passaram.
- db:status, db:migrate repetido, status --require-current, rollback local,
  downgrade base/upgrade e Alembic check: passaram somente no banco descartável.
- db:create gerou uma revisão em cópia temporária das migrations.
- Imagem com APP_ENV=production e DB_* sintéticas: schema pendente bloqueou
  startup, migration na rede Docker privada simulada passou; API e sentinel
  responderam HTTP 200 em PORT=8080. Ausência de .env na imagem confirmada.
- `python -m pip check` na imagem: nenhuma dependência quebrada.

Os testes não comprovam a configuração real do Railway/GitHub. Não houve
migration real, deploy remoto, alteração de autodeploy, backup/restore de
produção nem ativação de recursos externos. Há avisos de depreciação existentes
de TestClient/httpx e configuração Alembic; não foram adicionadas dependências.

## Referências

- https://docs.railway.com/deployments/pre-deploy-command
- https://docs.railway.com/config-as-code/reference
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
