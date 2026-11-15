# Contribuindo com o Ctrl X Backend

## Branches

Antes de alterar arquivos, confira `git status --short --branch`; mudanças locais
devem ser preservadas e resolvidas antes de começar. Atualize `develop` com
fast-forward e crie uma branch específica:

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/<feature-name>
```

Use inglês, letras minúsculas e kebab-case, por exemplo
`feature/clinical-records`, `feature/pain-diary` ou `feature/fix-login`. Para
correções e refatorações, mantenha o prefixo `feature/` e descreva a mudança no
nome. Nunca edite diretamente em `develop` ou `prod`.

Abra PR de `feature/*` para `develop`. O único caminho normal de publicação é PR
de `develop` para `prod`. PR para `prod` vindo de outra branch falha no CI. Não
faça push ou merge sem autorização explícita do usuário. A pipeline não realiza
merge, push ou deploy automático de feature ou `develop`.

## Commits

Use exclusivamente um dos tipos permitidos, dois-pontos, espaço e descrição curta
em inglês no imperativo:

```text
feat: add clinical record form
fix: validate patient access
refactor: extract pain record service
tests: cover clinical record permissions
```

Faça commits pequenos, cada um com uma mudança lógica. Não misture funcionalidade,
correção e refatoração independentes. Antes de cada commit, execute os testes,
lint e validações relevantes. O formato acima é uma convenção da equipe; a CI
não bloqueia commits com base em suas mensagens.

Nunca inclua `.env`, credenciais, tokens, segredos, dumps ou dados clínicos reais.
Use somente dados sintéticos nos testes.

## Validação antes de commit e PR

No mínimo, para este backend:

```powershell
python -m ruff check .
python -m pytest
```

Execute também as validações relevantes à mudança, como migrações Alembic e
build Docker. A CI executa Ruff, pytest com MySQL isolado, validação Alembic,
build e smoke test Docker. Não ignore falhas para liberar um PR.

## Proteção de branches

Configure rulesets/branch protection em `develop` e `prod` para exigir PR,
aprovação, checks CI, conversas resolvidas e branch atualizada. Bloqueie pushes
diretos, force push, exclusão e bypass. Proteja `.github/workflows/**` e scripts
de release com revisão. Em GitHub, `Backend CI` é o check de validação; o job de
produção não é requisito de PR, pois só roda em push para `prod`.
