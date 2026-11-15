# CI/CD — Ctrl X Backend

## Branches e publicação

O fluxo obrigatório é `feature/<nome-da-feature>` → PR para `develop` → PR de
`develop` para `prod`. Crie cada branch feature da `develop` atualizada antes de
editar arquivos. PR para `prod` deve vir exclusivamente de `develop`. Não faça
push ou merge sem autorização explícita. Branches feature e `develop` só executam
CI; push em `prod` repete CI e pode publicar após aprovação de `production`.

Os workflows não fazem merge nem push automáticos. Configure proteção das branches
`develop` e `prod` para exigir PR, revisão, checks aprovados, conversas resolvidas,
e bloquear push direto, force push, exclusão e bypass. Consulte
[CONTRIBUTING.md](CONTRIBUTING.md) para nomes de branches e commits.

Ctrl X é uma aplicação web responsiva acessada pelo navegador em desktop,
tablet e celular. O frontend Next.js é publicado na Vercel e a API deste
repositório no Railway. Este documento cobre somente `ctrl-x-backend`; o
frontend e sua publicação na Vercel não são alterados aqui. A pipeline está em
`.github/workflows/backend.yml`; nenhum deploy real foi executado durante sua
implementação.

## Eventos e gates

| Evento | CI | Publicação |
| --- | --- | --- |
| PR com destino `develop` | Sim | Nunca |
| Push em `develop` | Sim | Nunca |
| PR com destino `prod` | Sim | Nunca |
| Push em `prod` | Sim, novamente no SHA do push | Somente após CI verde e Environment production liberado |

PRs para `prod` falham se a branch de origem não for `develop`. PRs e pushes de
feature não iniciam publicação. Mensagens seguem a convenção de CONTRIBUTING.md;
nenhum step do workflow as valida.

Não há `workflow_dispatch`, `pull_request_target`, publicação em tags ou workflow
separado que possa reutilizar um resultado antigo de CI. Não há filtros por
caminho que deixem checks obrigatórios pendentes. O job de produção usa `needs: ci`,
baixa o pacote do mesmo run/SHA e verifica seu checksum. O token Railway existe
apenas no passo de publicação; a CI não usa secrets de produção.

A CI instala `requirements.lock`, verifica dependências com `pip check`, executa
Ruff, valida o destino do banco, aplica Alembic, verifica divergências com
`alembic check`, reverte ao início e reaplica as migrações. Depois roda pytest
contra MySQL 8.4 descartável, constrói Docker, verifica os idiomas `por` e `eng`
do Tesseract e testa o `/health` do container com `PORT=8080`.

O serviço MySQL é novo por job, sem volumes, sem dados reais e sem credenciais
de produção. `DATABASE_URL` e `TEST_DATABASE_URL` são constantes locais da CI.
O guard rejeita host diferente de `127.0.0.1`, porta diferente de 3306, usuário
ou banco diferente de `ctrlx_ci` e parâmetros extras de conexão. Alembic aplica
o guard automaticamente quando `CI=true`. Nunca sobrescrever essas URLs com secrets.

O baseline Alembic é intencionalmente vazio: o scaffold ainda não tem tabelas de
negócio. Ele cria uma história real de versões; não comprova regras clínicas que
ainda não existem. Todo novo modelo deve ser importado em `app/models/__init__.py`
e acompanhado por migração e testes reais. O teste de integração local é pulado
apenas quando não há MySQL configurado; em CI essa ausência causa falha.

## Preparação no GitHub

1. Criar branches `develop` e `prod` no repositório do backend.
2. Em Settings → Environments, criar **production**. Restringir deployment
   branches a **prod**, sem outras branches ou tags. Recomenda-se revisor
   obrigatório e impedir autoaprovação quando o plano GitHub permitir.
3. Cadastrar os valores abaixo **dentro desse Environment**, não na CI.
4. Habilitar Actions e autorizar as actions oficiais fixadas por SHA no workflow.

| Tipo | Nome | Valor |
| --- | --- | --- |
| Environment secret | `RAILWAY_TOKEN` | Project token Railway limitado ao projeto e environment de produção; não usar token pessoal |
| Environment variable | `RAILWAY_PROJECT_ID` | UUID do projeto existente |
| Environment variable | `RAILWAY_SERVICE_ID` | UUID do serviço da API, nunca do MySQL |
| Environment variable | `RAILWAY_ENVIRONMENT_ID` | UUID do environment Railway de produção |
| Environment variable | `BACKEND_PRODUCTION_URL` | Base HTTPS pública da API, sem `/health`, usuário, query ou credenciais |

O workflow usa apenas `contents: read`. Não publica imagens em registry, não
precisa de `packages: write`, OIDC ou token GitHub pessoal, e não persiste
credenciais no checkout. Proteger alterações ao workflow e aos scripts de release
com revisão; os arquivos executados na produção vêm de `prod`.

Aplicar branch protection/rulesets em **develop e prod**: exigir PR, aprovação,
conversas resolvidas, branch atualizada e o status obrigatório **Backend CI**.
Selecionar **Backend CI** após o primeiro run. Bloquear force push, exclusão e
bypass por administradores/automação quando possível. Não exigir o job
`Backend production` como check de merge, pois ele não roda em PR.
Se ativar merge queue, adicionar suporte e validação de `merge_group` antes de usar.

## Preparação no Railway (manual, antes do primeiro release)

1. Criar ou selecionar o projeto, environment de produção, serviço da API e MySQL.
2. No serviço da **API**, Settings → Source: desconectar o repositório GitHub
   (ou desativar Automatic Deployments se essa opção estiver disponível).
   Desativar também PR/preview environments e image auto-updates. Apenas
   selecionar `prod` ou habilitar Wait for CI não desativa autodeploy. Confirmar
   com um push em `develop` que não aparece deployment no Railway.
3. Configurar build por **Dockerfile**, raiz do pacote `.` e nenhum start command
   que sobrescreva o CMD. O Docker usa usuário não root, Tesseract Linux com
   `por`/`eng` e Uvicorn ouvindo `0.0.0.0:$PORT`.
4. Configurar **Pre-deploy Command**: `python -m alembic upgrade head`.
   Uma falha deve bloquear a ativação. Não executar migração em cada réplica
   nem utilizar `create_all()`. Alterações de esquema exigem backup e revisão.
5. Configurar **Healthcheck Path** `/health` e timeout de 300 segundos. O
   healthcheck Docker é usado na CI; configurar o Railway separadamente é
   obrigatório. A CLI aguarda o status `SUCCESS` do deployment exato e depois
   verifica HTTP 200 com JSON `{"status":"ok"}` no domínio público.
6. Configurar domínio HTTPS e as variáveis da aplicação no Railway:
   `APP_ENV=production`, `DATABASE_URL` com dialeto `mysql+pymysql`, banco privado,
   `SECRET_KEY` forte e `CORS_ORIGINS` com as origens reais do frontend.
   Escapar caracteres especiais na URL; não copiar os placeholders do exemplo.
   Não definir `CI=true`, nem expor MySQL publicamente para os testes.
7. Manter `TESSERACT_CMD=/usr/bin/tesseract` e `OCR_LANG=por+eng` (defaults da
   imagem). Antes de implementar uploads reais, provisionar armazenamento privado
   persistente em `/data/private_uploads`, com acesso do UID/GID 10001. O filesystem
   efêmero do container não oferece retenção de prontuários/documentos.

Estas configurações externas não são aplicadas pela criação dos arquivos.
O `/health` atual é somente liveness e não comprova acesso ao banco; o pre-deploy
testa a conexão/migração. Antes de endpoints persistentes, implementar readiness
segura e incluí-la no gate de publicação.

## Artefato, concorrência e falhas

Após todos os checks, a CI empacota somente o código de runtime e ferramentas de
release, Dockerfile, lock e migrações. O job de produção publica **essa fonte
validada** usando Railway CLI **5.74.0**, fixada para estabilizar flags e formato
de saída. O Railway reconstrói a imagem pelo mesmo Dockerfile/lock; não é promoção
do mesmo digest Docker. Pacotes apt e a tag base podem mudar entre os builds.
Para exigir promoção binária idêntica futuramente, adotar registry e deploy por
digest em uma mudança específica. Atualizações da CLI, actions, lock e imagem
base devem passar por PR e verificação dos comandos/parser antes de liberar.

CI de PR/develop pode cancelar execução obsoleta. Publicações usam concorrência
`backend-production` com `cancel-in-progress: false`: não cancelar uma publicação
enquanto migrações ou troca de tráfego ocorrem. Depois da espera/aprovação, o job
confere se o SHA ainda é o HEAD de `prod` e falha se estiver obsoleto. Releases
intermediários podem ser substituídos por um run mais recente ainda pendente;
GitHub concurrency não promete ordem FIFO.

O script lê o `deploymentId` do JSON devolvido pelo upload, consulta **esse ID** até
`SUCCESS` e rejeita estados de falha, respostas inesperadas e timeout. Um upload
aceito ou um `/health` de versão antiga não bastam para passar o gate. Erros da
CLI, build, migração, status ou health check fazem o job falhar. Não há
`continue-on-error`, testes fictícios ou fallback que libere produção com falhas.

Logs de checks/build ficam no GitHub Actions; o relatório JUnit é retido por sete
dias e o pacote de release também por sete dias. Deploy imprime ID e transições
de status, e só registra sucesso no resumo após os gates. Em erro, consultar
Railway → deployment correspondente → Build/Deploy Logs. Para diagnóstico
autorizado, usar `railway logs <deployment-id> --build --lines 100` e
`railway logs <deployment-id> --lines 100` no projeto/environment corretos.
Logs da aplicação não devem conter tokens, PII, texto OCR ou conteúdo clínico;
não anexar dumps de runtime ou banco a artifacts. Uvicorn roda sem access log.

## Release e compatibilidade com o frontend

1. Desenvolver em branch de trabalho e abrir PR para `develop`; revisar CI.
2. Abrir PR `develop` → `prod`, revisar contrato `/api/v1`, changelog,
   migrações, impacto no frontend publicado e plano de rollback.
3. Fazer merge em `prod`. O push executa CI novamente. Liberar o Environment
   quando aplicável e acompanhar o ID do deployment e o health check.
4. Somente após API compatível estar saudável liberar o frontend em seu próprio
   repositório. Nesta entrega nenhum arquivo do frontend foi alterado.

Releases independentes exigem mudanças aditivas: campos novos opcionais, manter
rotas/campos existentes e aceitar payloads da versão anterior do frontend.
Usar expand → migrar dados → atualizar consumidores → contract em releases
separados. Não remover/renomear colunas ou alterar significado no mesmo release
que começa a usar o novo contrato. Mudanças incompatíveis exigem nova versão de
API, período de coexistência e testes de contrato com consumidores reais.
A pipeline atual valida a API existente, mas não substitui esses testes quando
os endpoints de negócio e o frontend estiverem implementados.

## Rollback

- Preferir revert do commit defeituoso por PR para `prod`: nova CI e publicação
  do código revertido. Não fazer force push nem editar o workflow para pular gates.
- Em incidente, um operador autorizado pode usar **Rollback** no deployment
  saudável anterior do Railway, conferir ID/status e `/health`, e registrar
  incidente/SHA. Depois reconciliar o código com um PR. Não automatizar rollback
  cego ou usar `redeploy` do último deployment como se fosse versão anterior.
- Rollback da aplicação não desfaz migrações. O código anterior precisa aceitar
  o esquema expandido. Não executar `alembic downgrade` automaticamente em produção.
  Para perda/corrupção de dados, seguir restauração de backup testada e plano
  aprovado; não descartar prontuários ou histórico para restaurar a aplicação.

## Verificação local sem publicar

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements.lock
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
docker build -t ctrlx-backend:local .
```

Para testar migrações, iniciar um MySQL **descartável** 8.4 na porta 3306 com banco
e usuário `ctrlx_ci`, sem reutilizar o volume do Compose de desenvolvimento.
Definir `DATABASE_URL` e `TEST_DATABASE_URL` iguais, com essa identidade e host
`127.0.0.1`, depois executar os mesmos comandos Alembic e pytest do workflow.
Não definir token Railway para validar CI e não executar `scripts.deploy_railway`
localmente. Nenhuma etapa local precisa do banco de produção.

Verificação desta implementação: Ruff e actionlint passaram; pytest teve 21 testes
aprovados e um teste MySQL pulado por falta de servidor local. Alembic gerou SQL
offline do baseline e identificou um único head. As opções da CLI 5.74.0 foram
conferidas sem autenticação. Build Docker, migrações online e smoke do container
não puderam ser executados nesta máquina: WSL não está instalado e o engine
Linux do Docker não está disponível. Esses checks permanecem obrigatórios na
pipeline; é necessário conferir o primeiro run no GitHub antes do primeiro release.

Referências oficiais: [Railway CLI](https://docs.railway.com/cli/up),
[CLI 5.74.0: upload](https://github.com/railwayapp/cli/blob/v5.74.0/src/commands/up.rs),
[status por deployment](https://docs.railway.com/cli/deployment),
[healthchecks](https://docs.railway.com/deployments/healthchecks) e
[GitHub Environments e concorrência](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments).
