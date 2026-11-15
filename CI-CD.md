# CI/CD do backend: GitHub Actions e Railway

## Job exclusivo de Database Migrations

O fluxo de produção é **validate → database-migrations → production**.
O serviço privado **ctrl-x-migrations** executa Alembic no pre-deploy antes de
liberar o job da API. A API apenas verifica o schema, sem aplicar migrations.
Configure `RAILWAY_MIGRATIONS_SERVICE_ID` e o serviço adicional antes de ativar
esse fluxo. Veja [comandos, configuração e recuperação](docs/database-migrations.md).

## Fluxo e arquivos

`push feature/*` → CI → PR manual para `develop` → CI e revisão → merge manual
→ CI de `develop` → PR manual para `prod` → CI e revisão → merge manual
→ push em `prod` → CI completa novamente → aprovação de `production`
→ pre-deploy de ctrl-x-migrations → validação do schema da API → ativação → smoke HTTP.

- `.github/workflows/backend.yml`: CI reutilizável, Ruff, pytest, MySQL 8.4 isolado,
  Alembic, build Docker e smoke em configuração de produção.
- `.github/workflows/deploy-production.yml`: somente push em `prod`, CI do SHA
  exato e publicação de `ctrl-x-api`. Não publica MySQL nem frontend.
- `.github/rulesets/{develop,prod}.json`: regras prontas para importar; precisam
  ser ativadas no GitHub para bloquear pushes diretos.
- `railway.json`: Dockerfile, pre-deploy de verificação e healthcheck `/health`.
- `scripts/deploy_migrations.py`: pacote privado e acompanhamento do deployment
  exclusivo de migrations, usando o mesmo código/SHA validado da API.
- `scripts/db.py`: comandos de migrate/status/create e rollback local.
- `scripts/migrate_production.py`: conexão privada, versão MySQL, lock e upgrade.
- `scripts/start_api.py`: valida configuração/schema e faz exec do Uvicorn.
- `scripts/deploy_railway.py`: valida destino, envia fonte, acompanha o ID exato
  do deployment e faz smoke. Importar os módulos não publica nada.

Não há deploy em PR, feature, develop, tag ou dispatch manual. A concorrência
`backend-production` não cancela publicação em andamento. Runs pendentes podem
ser substituídos pelo GitHub; não há FIFO. Após aprovação, um SHA que já não é
o HEAD de prod é rejeitado. Preparar estes arquivos localmente não executa push,
merge, deploy, criação de recursos ou alterações de configurações externas.

## CI e isolamento

Python 3.12 e dependências resolvidas em `requirements.lock`, instaladas por
`pip install -r requirements.lock` e conferidas com `pip check`. `uv` é opcional
para ambiente local/regenerar lock; `requirements.txt` declara faixas e não é
a instalação usada na esteira ou na imagem.

MySQL 8.4 é descartável por job, sem volumes e sem secrets de produção.
`DATABASE_URL` e `TEST_DATABASE_URL` usam apenas `127.0.0.1:3306/ctrlx_ci`, usuário
`ctrlx_ci` e credenciais sintéticas. `scripts.ci_database` e Alembic com `CI=true`
recusam outros destinos. SQLite local não comprova compatibilidade MySQL.

CI executa upgrade, check de drift, downgrade base e novo upgrade **somente nesse
banco descartável**. Depois pytest e build. O smoke da imagem usa configuração
de produção com credenciais sintéticas e alias Docker privado simulado para o
banco isolado. Isso não comprova rede/configuração de um Railway real.

O pacote contém runtime, scripts, lock, Dockerfile, migrations e `railway.json`,
com checksum, consumido no mesmo run/SHA validado. Não contém `.env`, `.git`,
testes ou dados. Railway reconstrói a imagem: não é promoção do mesmo digest.
A tag base e pacotes apt podem mudar entre builds. Actions são fixadas por SHA
e Railway CLI em **5.74.0**; atualizações exigem PR e revisão.

## Configuração manual do GitHub

1. Revisar e integrar a infraestrutura em develop por PR, sem push direto.
2. Usar PRs manuais de feature para develop e de develop para prod.
3. Habilitar merge commits; não usar squash em develop → prod.
   Não habilitar merge queue sem adicionar `merge_group` à CI.
4. Importar os JSONs em Settings → Rules → Rulesets. Conferir **Active**, destinos
   exatos, **nenhum bypass**, inclusive administradores. A disponibilidade
   depende do plano/visibilidade. Selecionar `Backend CI` e `Branch policy`,
   preferencialmente vinculados ao GitHub Actions após o primeiro run; os nomes
   precisam coincidir com os checks reais.
5. As regras exigem PR, uma aprovação por outra pessoa, aprovação do último push,
   descarte de aprovações antigas, conversas resolvidas e checks verdes; bloqueiam
   force push e exclusão. **Os JSONs locais sozinhos não bloqueiam push direto.**
6. Designar revisores de workflows, migrations e scripts de release. Todos os PRs
   já exigem revisão; opcionalmente adicionar CODEOWNERS com usuários/equipes
   reais e ativar exigência de code owner. O autor não aprova o próprio PR;
   é necessário outro revisor autorizado. Não autoaprovar com bot.
7. Criar Environment **production**, permitir apenas branch prod, bloquear
   autoaprovação e exigir revisor. Se o plano não oferecer esse gate, não ativar
   deploy até definir/aprovar um controle equivalente. Configurações Railway
   ficam nele, indisponíveis para jobs de PR.

Develop exige feature atualizada com sua base. Branch atrasada/conflitante exige
atualização pelo desenvolvedor e nova revisão.
Prod exige CI, mas não exige que o HEAD de develop contenha o merge commit anterior
de prod: evita ciclo de sincronização reversa entre branches protegidas. O PR
testa o merge resultante e o push em prod repete CI antes de publicar. Mudanças
concorrentes de base exigem atenção na revisão de release.

### Secrets e variáveis de produção

PRs e merges são manuais. Não é necessário GitHub App nem chave de promoção.

| Local | Nome | Valor real a fornecer |
| --- | --- | --- |
| Environment secret production | `RAILWAY_TOKEN` | Project token do projeto/environment de produção |
| Environment variable production | `RAILWAY_PROJECT_ID` | UUID do projeto |
| Environment variable production | `RAILWAY_SERVICE_ID` | UUID de ctrl-x-api, nunca MySQL |
| Environment variable production | `RAILWAY_MIGRATIONS_SERVICE_ID` | UUID de ctrl-x-migrations |
| Environment variable production | `RAILWAY_ENVIRONMENT_ID` | UUID do environment chamado production |
| Environment variable production | `BACKEND_PRODUCTION_URL` | Base HTTPS pública da API, sem path/query/credenciais |

Project token Railway usa `RAILWAY_TOKEN`, não `RAILWAY_API_TOKEN` (conta/workspace).
O escopo é projeto/environment, não serviço: o script também confere nome e ID de
ctrl-x-api antes de upload, recusando ctrl-x-mysql. CLI usa `link`, `up --detach
--json` e `deployment list --json`. Upload aceito não comprova deploy saudável.

Após configurar proteções e revisores, abrir os PRs manualmente, aguardar CI
e revisão humana, e aprovar production somente após conferir backup e migrations.

## Recursos Railway a criar manualmente

No mesmo projeto/environment production, após autorização de custos:

1. **ctrl-x-mysql**: serviço separado, imagem MySQL **8.4**, volume persistente em
   **/var/lib/mysql** e credenciais fortes. Conferir a versão real do template.
   Criar banco e usuário da aplicação com permissões necessárias. Contas distintas
   de migração/runtime são evolução possível. Não expor TCP público sem necessidade.
2. **ctrl-x-api**: serviço separado. Desconectar Source GitHub/autodeploy nativo,
   desativar previews e image auto-updates. Selecionar prod ou Wait for CI não
   desativa autodeploy. Apenas Actions/CLI deve enviar código. Não sobrescrever
   Start Command: o CMD usa scripts.start_api, usuário 10001, `0.0.0.0:$PORT`,
   sem reload e com exec para sinais/encerramento adequados.
3. `railway.json` na raiz enviada à API: builder Dockerfile, pre-deploy
   `python -m scripts.db db:status --require-current`, healthcheck /health e timeout 300s.
   Conferir no deployment se a configuração foi lida. Definir **Pre-deploy
   Timeout** finito no painel, por exemplo 600s ajustado à revisão. Não presumir
   timeout padrão nem inventar um campo JSON não suportado.
4. Domínio público HTTPS para API; conferir DNS, certificado e PORT. MySQL fica
   na rede privada do mesmo environment.
5. Backups de volume com agenda/retenção aprovadas, conforme plano, e backup
   lógico consistente com restauração testada.

Nenhum ID, hostname privado, domínio Vercel ou token real foi fornecido nesta
tarefa. Os nomes acima são requisitos, não recursos criados pela implementação.

### Variables da API

Alternativamente a `DATABASE_URL`, configure as cinco variáveis abaixo no serviço
`ctrl-x-api`, usando referências às variáveis do serviço MySQL:

| Variável da API | Referência Railway |
| --- | --- |
| DB_USER | `${{ctrl-x-mysql.MYSQLUSER}}` |
| DB_PASSWORD | `${{ctrl-x-mysql.MYSQLPASSWORD}}` |
| DB_HOST | `${{ctrl-x-mysql.RAILWAY_PRIVATE_DOMAIN}}` |
| DB_PORT | `3306` |
| DB_NAME | `${{ctrl-x-mysql.MYSQLDATABASE}}` |

Confira os nomes reais das variáveis no serviço MySQL. Os cinco campos `DB_*`
têm prioridade sobre `DATABASE_URL`; se algum estiver definido, todos são
obrigatórios. Informe a senha original, sem percent-encoding: `URL.create`
trata os caracteres especiais. API, Alembic e pre-deploy usam a mesma resolução.
O host continua privado, terminado em `.railway.internal`, com MySQL 8.4.
Não use o endereço TCP público. As demais variáveis abaixo continuam necessárias.

| Variável | Configuração |
| --- | --- |
| APP_ENV | production |
| DATABASE_URL | mysql+pymysql, credenciais reais, hostname privado terminado em .railway.internal, porta explícita 3306 e banco real |
| SECRET_KEY | Aleatório único, no mínimo 32 caracteres, guardado com segurança |
| JWT_ISSUER | Emissor da API acordado e estável |
| JWT_AUDIENCE | Audiência do frontend acordada e estável |
| CORS_ORIGINS | Origens HTTPS reais e completas da Vercel/domínio próprio, sem wildcard/path |
| PORT | Fornecido pelo Railway; não fixar porta pública no código |

Usar Add Reference para os valores reais de ctrl-x-mysql e seu domínio privado.
Formato: `mysql+pymysql://<usuario-escapado>:<senha-escapada>@<host-privado>:3306/<banco>`.
Não é URL pronta: caracteres reservados de usuário/senha exigem percent-encoding.
Não imprimir a URL. Não definir CI=true ou TEST_DATABASE_URL no Railway.
Não copiar banco, volume ou .env local para produção.

### Cookies, domínios e armazenamento

O contrato CX-01 usa cookie HttpOnly, Secure em produção, host-only, SameSite=Lax
e Origin estrito nas mutações. Frontend usa credentials: include e sua origem
exata em CORS. Esta infraestrutura preserva esse contrato.

Domínios padrão *.vercel.app e *.up.railway.app são cross-site: CORS sozinho não
resolve cookies Lax. Antes de liberar autenticação, provisionar domínios próprios
HTTPS no mesmo site para frontend/API ou proxy de mesma origem aprovado.
O domínio Vercel real precisa ser informado/configurado. Não trocar automaticamente
para SameSite=None: cookies de terceiros podem seguir bloqueados, e a mudança
exige revisão de contrato/CSRF.

Não guardar documentos/dados clínicos em filesystem efêmero. Tesseract por/eng
está instalado, mas nenhum upload/OCR é implementado aqui. Antes de uploads reais,
definir armazenamento privado persistente, permissões e backup; o diretório
/data/private_uploads da imagem sozinho não é persistente. Pre-deploy não monta volumes.

## Migrations, compatibilidade e recuperação

Após CI/build, o job database-migrations envia a nova imagem ao serviço privado
ctrl-x-migrations. Railway roda seu pre-deploy com Variables e rede privada.
O script valida MySQL 8.4, adquire GET_LOCK e executa Alembic upgrade head na
**mesma conexão** que mantém o lock. Recusa múltiplos heads e confere revisão final.
Libera lock ao terminar/fechar conexão. Falha sai não zero e impede ativação;
mensagens omitem URL, tokens e parâmetros SQL. Migrations não rodam no CMD/réplicas.

Cada réplica só confere conexão e revisão antes de Uvicorn. Não inicia com schema
atrasado, mesmo sem pre-deploy. /health segue liveness, não monitoramento contínuo
do banco. O deploy acompanha o ID exato até SUCCESS e faz smoke público; não
aceita somente health de versão antiga nem usa continue-on-error.

Há uma execução de pre-deploy por tentativa de deployment. **Não existe garantia
distribuída de exactly-once nem transação atômica entre MySQL e ativação Railway.**
Repetições consultam revisões aplicadas; crash em DDL pode deixar estado parcial.
DDL MySQL pode fazer commit implícito. Lock/concurrency não tornam DDL reversível.

Revisar migrations antes de prod. Usar expand → migrar dados → consumidores →
contract em releases separados. A versão antiga pode atender durante pre-deploy:
a migration precisa ser compatível com ela. Não executar drops, renomes
incompatíveis, recriação de tabelas, create_all ou importação de dados locais
automaticamente em produção. CI não prova ausência de migração destrutiva:
revisão humana e plano de recuperação são gates.

Em falha, parar promoção e inspecionar revisão/schema com operador autorizado.
Não repetir DDL parcialmente aplicado às cegas. Preferir migration corretiva
forward-only por PR. Não fazer downgrade automático em produção. Reverter código
não reverte banco; código anterior precisa suportar schema expandido. Rollback
manual Railway exige autorização e reconciliação posterior por PR.

Backup anterior a mudanças de schema, recuperação ensaiada em ambiente isolado,
RPO/RTO e retenção definidos. Backup lógico InnoDB deve ser consistente (mysqldump
--single-transaction, sem DDL concorrente), criptografado e externo ao container.
Validar restauração, migrations, integridade e acessos antes de substituir produção.
Não anexar dumps ao Actions nem despejar dados clínicos em logs.

## Primeiro deploy e diagnóstico

1. Concluir serviços, Variables, DNS/cookies, backups e desativação de autodeploy.
2. Concluir regras, secrets e revisores. Conferir bloqueio de push e ausência
   de bypass; não testar usando dados reais.
3. Feature → develop → prod por PR, CI e aprovações. Liberar production só após
   revisar migrations/backup.
4. Actions verifica SHA, checksum e destino, envia só API, acompanha ID e smoke.
   Conferir pre-deploy/configuração no painel Railway.
5. Validar /health, login/logout/cookie no navegador e /api/v1/auth/me com frontend
   real. Health verde sozinho não valida CORS/cookies nem habilitação clínica.

Logs de CI/falhas ficam no Actions. JUnit/pacote têm retenção de sete dias, sem
dump de banco ou logs clínicos. No Railway, abrir o ID exato e consultar Build,
Pre-deploy e Deploy Logs. Diagnóstico autorizado: railway logs <deployment-id>
--lines 100 ou --build, sem imprimir Variables. Em falha de conexão, conferir
environment, private DNS, usuário/banco e URL escapada. Em falha de migration,
conferir revisão e estado parcial. Em falha HTTP, conferir PORT, certificado,
domínio, ID e mensagens sanitizadas de startup.

## Validação local desta entrega (15/11/2026)

- `python -m pytest`: 119 passaram e 8 casos MySQL foram pulados no Windows.
- `python -m pytest -p no:cacheprovider` com MySQL 8.4 isolado: **127 passaram,
  nenhum pulado**, incluindo lock, falha de migration e preservação de legado.
- `python -m ruff check .`: passou no Windows e na cópia Linux normalizada.
- `python -m alembic upgrade head`, `check`, `downgrade base`, novo upgrade/check:
  passaram exclusivamente no MySQL descartável.
- `docker build`: passou; `pip check`, Tesseract por/eng, usuário 10001,
  ausência de .env, health HTTP 200 em PORT=8080 e SIGTERM limpo confirmados.
- Imagem em production recusou startup com revisão pendente; pre-deploy
  `python -m scripts.migrate_production` na rede privada Docker simulada passou.
- actionlint 1.7.7 e ShellCheck: passaram nos três workflows.
- Railway CLI 5.74.0: versão e ajuda das flags conferidas, sem autenticação/deploy.

Há avisos preexistentes de depreciação de TestClient/httpx e configuração Alembic.
Não foi executado run no GitHub, auto-merge real, conexão Railway de produção,
backup/restore de produção ou deploy externo. Esses testes e a ativação manual
continuam necessários antes do primeiro release.

## Referências oficiais

- [Pre-deploy Railway](https://docs.railway.com/deployments/pre-deploy-command)
- [Config as code](https://docs.railway.com/config-as-code/reference)
- [MySQL](https://docs.railway.com/databases/mysql)
- [CLI e autenticação](https://docs.railway.com/cli)
- [CLI 5.74.0 upload](https://github.com/railwayapp/cli/blob/v5.74.0/src/commands/up.rs)
- [CLI 5.74.0 status](https://github.com/railwayapp/cli/blob/v5.74.0/src/commands/status.rs)
- [Eventos e tokens GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
- [Regras efetivas por branch](https://docs.github.com/en/rest/repos/rules)
