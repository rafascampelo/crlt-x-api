# Desenho inicial da API

Proposta de evolução. Consulte `frontend-contracts.md` para endpoints já implementados.
Base `/api/v1`, JSON,
UUIDs públicos e timestamps ISO 8601 em UTC. `/health` permanece liveness,
sem dependência de disponibilidade do banco.

| Recurso | Rotas propostas | Regra principal |
| --- | --- | --- |
| Autenticação | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` | Senhas Argon2; sessão curta e revogável; definir transporte de tokens antes de implementar |
| Identidade | `GET /me`, `PATCH /me` | Identidade da sessão; campos editáveis explicitamente permitidos |
| Vínculos | `GET /me/professional-links`, `POST /me/professional-links`, `POST /me/professional-links/{link_id}/accept`, `POST /me/professional-links/{link_id}/revoke` | Solicitação pendente e aceite explícito; definir quem inicia e aceita; criação não concede acesso unilateral ao profissional |
| Pacientes vinculados | `GET /patients`, `GET /patients/{patient_id}` | Profissional limitado aos vínculos ativos; paciente somente a si |
| Prontuários | `GET /patients/{patient_id}/clinical-records`, `POST /patients/{patient_id}/clinical-records` | Leitura própria ou profissional autorizado; criação profissional com vínculo ativo |
| Prontuário individual | `GET /clinical-records/{record_id}`, `PATCH /clinical-records/{record_id}` | Resolver paciente pelo recurso; edição somente do rascunho pelo autor com vínculo ativo |
| Finalização | `POST /clinical-records/{record_id}/finalize` | Transição atômica; impedir edição concorrente e posterior |
| Adendos | `GET /clinical-records/{record_id}/amendments`, `POST /clinical-records/{record_id}/amendments` | Registro finalizado; criação pelo autor com vínculo ativo; motivo obrigatório; sem editar/excluir |
| Diário de dor | `GET /patients/{patient_id}/pain-entries`, `POST /me/pain-entries`, `PATCH /pain-entries/{entry_id}`, `DELETE /pain-entries/{entry_id}` | Escrita somente do paciente dono; leitura profissional exige vínculo ativo |
| Prescrições | `GET /patients/{patient_id}/prescriptions`, `POST /patients/{patient_id}/prescriptions`, `GET /prescriptions/{prescription_id}` | Escrita profissional autorizada; paciente lê as próprias; versionamento a definir antes de editar |
| Evolução | `GET /patients/{patient_id}/progress-entries`, `POST /patients/{patient_id}/progress-entries` | Contrato e autoria serão definidos com o fluxo de acompanhamento |
| Visões | `GET /patients/{patient_id}/timeline`, `GET /patients/{patient_id}/dashboard`, `GET /patients/{patient_id}/calendar` | Consultas autorizadas sobre entidades existentes; timeline usa prontuários finalizados |
| Documentos | `GET /patients/{patient_id}/documents`, `POST /me/documents`, `GET /documents/{document_id}`, `GET /documents/{document_id}/content` | Permissões explícitas e conteúdo privado; nunca URL pública |

O servidor verifica identidade e vínculo em toda operação. IDs na rota não são
prova de autorização. Consultas por recurso resolvem a identidade do paciente
armazenada no banco, inclusive em adendos e referências relacionais.

Convenções propostas: 201 para criação, 204 para exclusão/revogação sem corpo,
401 para sessão ausente/inválida, 403 para papel sem permissão, 404 para recurso
inexistente ou fora do escopo, 409 para conflito de estado e 422 para validação.
Listas terão paginação por cursor e limites; visões temporais terão intervalo
limitado. O formato exato de paginação e erros será definido nos schemas.

Sem exclusão de prontuários finalizados ou adendos. Permissões de documentos,
revisão OCR, payloads e exemplos OpenAPI serão detalhados nos respectivos
incrementos, antes da implementação. Não há endpoints de diagnóstico automático.
