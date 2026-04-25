# Python Agent Challenge

Backend em Python com orquestração, tool de recuperação e LLM para responder
perguntas ancoradas em uma base de conhecimento em Markdown (KB pública).

## Contrato

- `POST /messages` — entrada: `{ "message": "...", "session_id?": "..." }`
- Resposta: `{ "answer": "...", "sources": [{ "section": "..." }] }`
- Fallback quando não há contexto suficiente:
  `Não encontrei informação suficiente na base para responder essa pergunta.` + `sources: []`
- `GET /health` — verificação de status
- Swagger: `http://localhost:8000/docs`

## Arquitetura

```
app/
  api/      rotas e modelos Pydantic de request/response
  core/     config (pydantic-settings), logging, deps do FastAPI
  flow/     orquestração do fluxo e templates de prompt
  tools/    KnowledgeTool (HTTP + cache TTL + ranking keyword com peso no título)
  llm/      cliente LLM compatível com OpenAI Chat Completions
  memory/   store in-process (TTL + janela de turnos) e NullStore
  utils/    tokenização, remoção de acentos, normalização de espaços
tests/      unit tests com fakes + testes de rota via TestClient
scripts/    test_contract.sh — valida os 6 casos do gabarito
```

## Decisões técnicas

- **Cache da KB com TTL**: `KnowledgeTool` guarda o Markdown em memória com
  TTL configurável (`KB_CACHE_TTL_SECONDS`) e pré-aquece no `lifespan` do
  FastAPI — evita baixar a KB a cada request e acelera a primeira chamada. A
  fonte oficial continua sendo `KB_URL` via HTTP; o cache só evita downloads
  redundantes.
- **Injeção via `app.state` + `Depends`**: o orquestrador é construído no
  startup e injetado na rota por dependência do FastAPI. Nada é instanciado
  no import do módulo.
- **Orquestrador com dependências por interface**: recebe `tool`,
  `llm_generate` e `memory` no construtor, o que torna os testes
  independentes de rede.
- **Fallback em camadas**: erro da tool, tool vazia, erro do LLM, LLM vazio
  e detecção de marcadores de fallback na resposta — todos caem no mesmo
  fallback canônico com `sources: []`.
- **Detector de fallback por marcadores normalizados**: depois que o LLM
  responde, o texto é normalizado (lowercase, sem acentos) e comparado contra
  uma lista de paráfrases comuns ("não encontrei informação suficiente",
  "não tenho informação suficiente", "não há informação suficiente", etc.).
  Se bater, força a `answer` canônica e `sources: []`. Cobre o caso em que o
  LLM decidiu fallback parafraseando levemente.
- **Filtro de citação em `sources`**: depois da resposta, cada seção
  candidata (vindas do tool) é mantida apenas se o **primeiro token
  significativo do título** aparece na `answer` tokenizada. Evita devolver
  como fonte uma seção que o tool achou relevante mas que o LLM não usou de
  fato. Safety net: se nenhuma bater, mantém o top-1 do ranking para não
  retornar `sources: []` junto a uma resposta não-fallback.
- **Prompt anti-armadilha**: o system prompt instrui o LLM a ignorar os
  "pontos de atenção" da KB (provocações propositais com afirmações
  categóricas que contradizem o restante da própria seção) e priorizar
  Definição/Quando usar.
- **Texto exato do fallback garantido no código**: o texto de fallback é uma
  constante; não depende do LLM reproduzi-lo.
- **Memória in-process (padrão)**: `InProcessMemoryStore` com TTL por turno
  e `deque(maxlen)` para janela curta. Isolamento por `session_id`. Para
  desligar, basta `MEMORY_ENABLED=false` — o `NullMemoryStore` assume.
- **LLM genérico**: cliente OpenAI-compatible cobre OpenAI, Groq,
  OpenRouter, Together, DeepSeek, xAI, Mistral, etc. Basta configurar
  `LLM_BASE_URL` e `LLM_API_KEY` no `.env`.
- **Logs estruturados**: `kb_fetched bytes=...`,
  `retrieval matches=... useful=... scores=[...]`, `tool_error`, `llm_error`
  — permitem auditoria do fluxo.
- **Dockerfile**: imagem `python:3.11-slim`, usuário não-root,
  `HEALTHCHECK` interno, separação de cache de dependências e código.

## Regras de decisão do fluxo

1. Valida a `message` no boundary HTTP (não vazia, máx. 4000 chars,
   `session_id` pattern).
2. `KnowledgeTool` baixa a KB (via cache) e extrai seções por cabeçalho
   `## `.
3. Tokeniza query e seções (minúsculas, sem acentos, sem stopwords PT-BR).
   Quando há `session_id`, a query enviada à tool é aumentada com os turnos
   anteriores do usuário (search-time only — não afeta `sources`).
4. Rank: `score = 1*|q∩content| + 2*|q∩title|`. Top-K por score, corte em
   `CONTEXT_MIN_SCORE`.
5. Se a tool não retornou nada útil → fallback canônico com `sources: []`.
   Caso contrário, monta o prompt com contexto + histórico recente (se
   houver) e a pergunta.
6. LLM gera a resposta. O código:
   - Valida que não está vazia → senão, fallback.
   - Verifica se contém algum marcador de fallback (paráfrases) → se sim,
     substitui pela `answer` canônica e força `sources: []`.
7. Filtro de citação: mantém em `sources` apenas as seções cujo primeiro
   token do título aparece na `answer`. Se nenhuma bater, mantém o top-1
   do ranking como rede de segurança.

## Configuração

```bash
cp .env.example .env
# edite .env preenchendo LLM_API_KEY (e outras variáveis se trocar de provider)
```

Variáveis principais:

| Variável | Default | Descrição |
|---|---|---|
| `KB_URL` | _obrigatória_ | URL raw da KB em Markdown |
| `LLM_PROVIDER` | `openai` | rótulo (logging); o request usa `LLM_BASE_URL` |
| `LLM_MODEL` | `gpt-4o-mini` | nome do modelo |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | endpoint do provedor |
| `LLM_API_KEY` | _vazio_ | chave do provedor |
| `CONTEXT_TOP_K` | `3` | máximo de seções por resposta |
| `CONTEXT_MIN_SCORE` | `2` | score mínimo para considerar uma seção |
| `KB_CACHE_TTL_SECONDS` | `60` | cache do Markdown |
| `MEMORY_ENABLED` | `true` | ativa memória por `session_id` |
| `MEMORY_TTL_SECONDS` | `900` | TTL por turno |
| `MEMORY_MAX_TURNS` | `6` | janela de turnos por sessão |

## Executar

### Docker (recomendado)

```bash
make up        # docker compose up -d --build
make logs      # acompanhar logs
make down
```

### Local (desenvolvimento)

```bash
make install
make dev       # hot reload
```

## Testes

```bash
make test-unit     # pytest (rápido, sem rede)
make test-contract # bash script validando os 6 casos (requer servidor UP)
make test          # tudo
```

## Exemplos de uso

```bash
curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"O que é composição?"}'

curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"Qual o preço do bitcoin hoje?"}'

curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"Pode resumir?", "session_id":"sessao-123"}'
```
