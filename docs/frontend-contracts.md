# Contratos implementados para o frontend

Todas as rotas abaixo usam `/api/v1`. JSON, UUIDs e datas ISO 8601 em UTC.
Enviar `credentials: "include"` em fetch e o Origin permitido nas mutações.
As respostas autenticadas possuem `Cache-Control: no-store`.

## Autenticação

| Método e rota | Entrada | Sucesso |
| --- | --- | --- |
| `POST /auth/register` | `email`, `password` (12–128 caracteres), `full_name`, `role` (`PATIENT` ou `PROFESSIONAL`) | 201, `{id, email, role}` |
| `POST /auth/login` | `email`, `password` | 200, `{id, email, role}` e cookie `ctrlx_access` |
| `GET /auth/me` | Cookie | 200, `{id, email, role}` |
| `POST /auth/logout` | Cookie e Origin | 204, revoga sessão e remove cookie |

Cookie HttpOnly, host-only, SameSite=Lax, Secure fora de desenvolvimento,
validade de 900 segundos. Reautenticar após expiração. Login limitado a cinco
tentativas por conta em 300 segundos, com 429 e `Retry-After`.

## Perfis e vínculos

| Método e rota | Entrada | Sucesso |
| --- | --- | --- |
| `GET /me` | Cookie | 200, perfil próprio |
| `PATCH /me` | `{full_name}` | 200, perfil atualizado |
| `GET /patients/{patient_id}` | Cookie | 200, perfil do paciente próprio ou vinculado ativamente |
| `GET /me/professional-links` | `limit` (1–100, padrão 20), `cursor` UUID opcional | 200, `{items, next_cursor}` |
| `POST /me/professional-links` | Paciente envia `{professional_id}` | 201, vínculo pendente |
| `POST /me/professional-links/{link_id}/accept` | Profissional destinatário, sem corpo | 200, vínculo ativo |
| `POST /me/professional-links/{link_id}/revoke` | Um dos participantes, sem corpo | 204, inclusive se já revogado |

Perfil tem `{id, user_id, role, full_name}`. `id` identifica o perfil de paciente
ou profissional. `user_id` identifica a conta e corresponde a `id` de `/auth/me`.
Usar o ID de perfil nos parâmetros `patient_id` e `professional_id`.
Somente `full_name` é editável. A API rejeita campos adicionais.

Vínculo tem `{id, patient_id, professional_id, status, created_at, accepted_at,
revoked_at}`. Status `pending`, `active` ou `revoked`. Datas de aceite e revogação
são nulas enquanto não ocorrerem. O paciente inicia o pedido, e o profissional
destinatário aceita. Criar pedido requer conhecer o UUID do profissional.
Uma busca pública de profissionais depende de contrato futuro.
Pedidos pendentes não liberam acesso. Existe no máximo um vínculo ativo por
paciente, inclusive sob concorrência. Pode haver pedidos pendentes para outros
profissionais. Revogação preserva o histórico. Novo consentimento exige novo pedido.

A lista inclui apenas vínculos do usuário autenticado, ordenados por UUID,
com cursor exclusivo. Seguir `next_cursor` até ser nulo. IDs são imutáveis,
e a ordem por UUID não representa ordem cronológica.

## Erros

Formato `{detail: string}`. 401 requer login, 403 indica papel ou Origin
sem permissão, 404 cobre recurso inexistente ou fora do escopo do usuário,
409 indica conflito de estado, 422 indica payload/parâmetro inválido.
Erros de validação omitem os valores recebidos.

## Próximos incrementos P0

Diário de dor, prontuários nativos com finalização e adendos e timeline
longitudinal ainda dependem de implementação. As rotas propostas estão em
`api-design.md`. A existência de vínculo profissional não concede acesso
automático a documentos.
