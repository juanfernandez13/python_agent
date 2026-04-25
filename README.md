# Python Agent Challenge

Backend em Python que recebe perguntas, busca contexto numa base de conhecimento
em Markdown via HTTP e usa um LLM para sintetizar respostas ancoradas e
rastreáveis. Implementação para a vaga A1/A2.

## Contrato

### `POST /messages`

Request:

```json
{
  "message": "O que é composição?",
  "session_id": "sessao-123"
}
```

`session_id` é opcional. Se enviado, o fluxo mantém histórico curto isolado por
sessão; se omitido, cada chamada é independente.

Response (sucesso):

```json
{
  "answer": "...",
  "sources": [{ "section": "Composição" }]
}
```

Response (sem contexto suficiente):

```json
{
  "answer": "Não encontrei informação suficiente na base para responder essa pergunta.",
  "sources": []
}
```

Validações:

- `message`: string não-vazia, 1–4000 chars, sem ser só whitespace.
- `session_id`: 1–128 chars, regex `^[A-Za-z0-9_\-]+$`.
- Estrutura da saída garantida por `MessageResponse` (Pydantic) — não depende
  de `temperature` ou de comportamento do LLM.

### `GET /health`

Endpoint de smoke usado pelo `HEALTHCHECK` do Docker e pelo `make test-contract`.

### Swagger

`http://localhost:8000/docs` — gerado automaticamente pelo FastAPI.

## Arquitetura

```
app/
  api/                       FastAPI routes + modelos Pydantic
    routes.py                  POST /messages, GET /health
    message_request.py         validação da entrada
    message_response.py        contrato da saída (answer + sources)
    source_item.py             cada source com apenas section
  core/                      infra de aplicação
    config.py                  pydantic-settings — todas as env vars
    deps.py                    Depends do FastAPI (orchestrator via app.state)
    logging.py                 logger estruturado
  flow/                      orquestração e prompts
    orchestrator.py            handle(message, session_id) — fluxo principal
    prompts.py                 SYSTEM_PROMPT + builders de contexto/histórico
    result.py                  FlowResult dataclass
  llm/                       cliente LLM
    client.py                  OpenAIClient (chat-completions, qualquer endpoint compatível)
    backend.py                 protocolo
    error.py                   LLMError
    message.py                 LLMMessage dataclass
  tools/                     tool obrigatória de KB
    kb_tool.py                 fetch HTTP + cache TTL + parse + ranking
    knowledge_source.py        protocolo
    section_match.py           resultado do ranking
  memory/                    memória opcional por session_id
    redis_store.py             persistência fora do processo (diferencial)
    in_process_store.py        fallback em RAM (dev/testes)
    null_store.py              memória desligada
    protocol.py                interface MemoryStore
    turn.py                    MemoryTurn dataclass
  utils/                     helpers de texto
    text.py                    tokenize, remove_accents, STOPWORDS_PT
tests/                       pytest com fakes (sem rede)
scripts/                     test_contract.sh — valida o gabarito ponta-a-ponta
docker-compose.yml           API + Redis com healthchecks
Dockerfile                   imagem slim, usuário não-root, HEALTHCHECK
Makefile                     install, dev, up, down, logs, test, clean
```

## Fluxo de execução

`Orchestrator.handle(message, session_id)`:

1. **Recupera histórico** (se houver `session_id` e memória ativa).
2. **Augmenta a query de busca** concatenando turnos anteriores do usuário.
   Aumenta recall em conversas com follow-ups; só afeta o ranking, não vaza
   para `sources`.
3. **Tool de KB** (`KnowledgeTool.search`):
   - Fetch HTTP da KB via `KB_URL` (com cache TTL na memória do processo).
   - Parser extrai seções por cabeçalho `## `.
   - Tokeniza query e seções: lowercase, sem acentos, sem stopwords PT-BR,
     tokens com ≥3 caracteres.
   - Rank: `score = |q ∩ content| + 2 · |q ∩ title|` (peso 2× no título).
   - Filtra `score < CONTEXT_MIN_SCORE`, ordena, corta no `CONTEXT_TOP_K`.
4. **Decisão de fallback (camada 1)**: tool falhou ou retornou vazio →
   `answer` canônica + `sources: []`.
5. **Monta o prompt**: contexto formatado por seção + histórico recente +
   pergunta. System prompt instrui o LLM a ignorar “pontos de atenção”
   (honeypots da KB) e priorizar Definição/Quando usar.
6. **Chama o LLM**:
   - `LLMError` ou string vazia → fallback.
   - **Detecção de paráfrase (camada 2)**: a resposta é normalizada
     (lowercase + sem acento) e comparada contra 9 marcadores comuns
     (“não encontrei informação suficiente”, “não há informação suficiente”,
     etc.). Se bater, força `answer` canônica e `sources: []`.
7. **Filtro de citação (camada 3)**: cada seção candidata só vira `source`
   se o **primeiro token significativo do título** aparecer na `answer`. Se
   nada bater, mantém o top-1 do ranking como rede de segurança (evita
   `sources: []` em resposta válida).
8. **Persiste turnos** na memória (apenas se houver `session_id`).

## Decisões técnicas

### Fluxo / decisão

- **Validação no boundary**. `MessageRequest` rejeita entradas inválidas antes
  do orquestrador. `MessageResponse` valida o contrato de saída — a estrutura
  do JSON não depende do que o LLM retornar.
- **Fallback em camadas convergente**. Erro da tool, tool vazia, erro do LLM,
  LLM vazio e paráfrase de fallback caem **na mesma string canônica**
  (constante `FALLBACK_ANSWER`) com `sources: []`. O texto exato exigido pela
  spec não depende do LLM reproduzir.
- **Detector de paráfrases**. 9 marcadores normalizados cobrem variantes do
  “não encontrei informação suficiente”. Se o LLM hesita e parafraseia, o
  orquestrador re-canoniza a resposta.
- **Filtro de `sources` por uso real**. O ranker pode trazer seções relevantes
  que o LLM acabou não citando. O filtro mantém só seções cujo primeiro token
  do título aparece na resposta — evita citar fontes “fantasma”.
- **Prompt anti-armadilha**. A KB tem `### Ponto de atenção` com afirmações
  deliberadamente erradas (honeypots de avaliação). O system prompt orienta o
  LLM a tratá-las como provocações e priorizar Definição/Quando usar.
  Validado em smoke contra duas armadilhas (composição/herança e prompt longo
  vs validação).
- **Augmentação de query com histórico** (search-time only). Turnos anteriores
  do usuário entram na query do ranker para aumentar recall em conversas;
  não influenciam `sources`.

### KB / Tool

- **Cache da KB com TTL**. `KnowledgeTool` mantém o Markdown em memória por
  `KB_CACHE_TTL_SECONDS` e pré-aquece no `lifespan` do FastAPI. A fonte
  oficial continua sendo `KB_URL` via HTTP; o cache só evita re-downloads
  redundantes.
- **Ranking lexical com peso no título**. Simples, transparente e suficiente
  para a KB curta e técnica do desafio. Peso 2× no título reflete a heurística
  “casar o nome da seção é evidência forte”. O score é determinístico e
  auditável via log `retrieval matches=N useful=N scores=[...]`.

### LLM

- **Cliente OpenAI-compatible**. Cobre OpenAI, Groq, OpenRouter, Together,
  DeepSeek, xAI, Mistral e qualquer endpoint compatível — basta configurar
  `LLM_BASE_URL` e `LLM_API_KEY`.
- **Provedor/modelo trocáveis sem código**. Toda a configuração do LLM vive
  no `.env`.
- **Sem dependência de `temperature` para formato**. Estrutura é validada por
  Pydantic; semântica de fallback é validada pelo código (camadas 2 e 3).

### Memória de sessão (diferencial)

- **`RedisMemoryStore`** (usado no `docker compose`). Cada `session_id` vira
  uma `List` em `memory:{session_id}`. Pipeline `LPUSH` → `LTRIM` (mantém só
  os N mais recentes) → `EXPIRE` (TTL renovado a cada escrita — sliding
  window). Sobrevive a reinício do container via volume.
- **`InProcessMemoryStore`** (default em dev). Mesma semântica em RAM, com
  `deque(maxlen=N)` e prune por TTL no acesso. Útil para testes e execução
  local sem Redis.
- **`NullMemoryStore`**. Stub usado quando `MEMORY_ENABLED=false`.
- **Resiliência**. Erros de Redis caem em log e o orquestrador segue como se
  o histórico estivesse vazio — falha de memória **nunca** derruba a resposta
  do agente.
- **Isolamento entre sessões**. Chave por `session_id` no Redis; dict por
  `session_id` em memória. Sem possibilidade de leitura cruzada.

### Injeção de dependências

- **`Orchestrator` recebe interfaces** (`tool`, `llm_generate`, `memory`) no
  construtor. Tudo é instanciado no `lifespan` do FastAPI (não no import) e
  injetado pela rota via `Depends`. Os testes de orquestração rodam 100%
  offline usando fakes.

### Operacional

- **`docker compose`** com API e Redis, ambos com healthcheck. A API só sobe
  depois que o Redis reporta saudável.
- **Dockerfile**. Base `python:3.11-slim`, usuário não-root, `HEALTHCHECK`
  nativo, separação entre camada de dependências e código (cache Docker
  amigável).
- **Logs estruturados**. `kb_fetched bytes=...`,
  `retrieval matches=N useful=N scores=[...]`, `tool_error`, `llm_error`,
  `redis_add_turn_failed` — auditoria do fluxo sem precisar de tracing
  dedicado.

## Diferenciais implementados

| Diferencial da spec | Status |
|---|---|
| Swagger automático (`/docs`) | FastAPI nativo |
| `session_id` com isolamento, janela curta e TTL | Implementado em Redis e in-process |
| Persistência fora do processo no `docker compose` | Redis com volume `redis-data` |
| `Makefile` com `up` / `down` / `test` | Inclui também `install`, `dev`, `logs`, `clean` |

## Configuração

```bash
cp .env.example .env
# editar LLM_API_KEY (e demais variáveis se trocar de provider)
```

| Variável | Default | Descrição |
|---|---|---|
| `KB_URL` | _obrigatória_ | URL raw da KB em Markdown (oficial do desafio) |
| `LLM_PROVIDER` | `openai` | rótulo (logging) — request usa `LLM_BASE_URL` |
| `LLM_MODEL` | `gpt-4o-mini` | nome do modelo |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | endpoint OpenAI-compatible |
| `LLM_API_KEY` | _vazio_ | chave do provedor |
| `LLM_TEMPERATURE` | `0.2` | passada na request, não load-bearing |
| `LLM_MAX_TOKENS` | `400` | teto da resposta |
| `LLM_TIMEOUT_SECONDS` | `30` | timeout do request ao LLM |
| `CONTEXT_TOP_K` | `3` | máximo de seções por resposta |
| `CONTEXT_MIN_SCORE` | `2` | score mínimo para incluir uma seção |
| `KB_CACHE_TTL_SECONDS` | `60` | TTL do cache em memória do Markdown |
| `KB_TIMEOUT_SECONDS` | `15` | timeout do fetch HTTP da KB |
| `MEMORY_ENABLED` | `true` | liga memória por `session_id` |
| `MEMORY_STORE` | _vazio_ | `""` = in-process; `redis://host:6379/0` = Redis |
| `MEMORY_TTL_SECONDS` | `900` | TTL de sessão (renovado a cada escrita) |
| `MEMORY_MAX_TURNS` | `6` | janela de turnos (mensagens) por sessão |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | bind do uvicorn |
| `LOG_LEVEL` | `INFO` | nível dos logs |

## Como executar

### Docker (recomendado)

```bash
make up       # docker compose up -d --build
make logs     # acompanhar logs
make down     # encerrar
```

A API responde em `http://localhost:8000`. O Redis fica interno na rede do
compose (não exposto externamente).

### Local (desenvolvimento)

```bash
make install  # cria .venv e instala requirements
make dev      # uvicorn --reload em http://localhost:8000
```

Em modo local, `MEMORY_STORE` vazio cai no `InProcessMemoryStore` — não exige
Redis para rodar.

## Testes

```bash
make test-unit      # pytest, sem rede (rápido)
make test-contract  # bash + curl, requer servidor UP — valida o gabarito
make test           # ambos
```

`make test-unit` se auto-bootstrapa: se a `.venv` ainda não existir (clone
limpo), ele dispara `make install` antes de rodar o pytest. Não exige passo
manual de `make install` antes.

`tests/` cobre orquestrador, memory stores (Redis com cliente fake e
in-process), KB tool e rotas FastAPI via `TestClient`.
`scripts/test_contract.sh` valida ponta-a-ponta os casos da seção abaixo.

## Casos validados (gabarito)

| Pergunta | `sources` esperado |
|---|---|
| `O que é composição?` | `Composição` |
| `Quando usar herança?` | `Herança` |
| `Qual o papel da orquestração?` | `Orquestração` |
| `Qual o papel da Tool de conhecimento?` | `Tool de conhecimento` |
| `A tool deve responder diretamente ao usuário?` | `Tool de conhecimento` |
| `Onde colocar regra de negócio, no endpoint ou no fluxo interno?` | `Endpoint de API` |
| `Como agir sem contexto suficiente?` | `[]` (fallback canônico) |
| `Qual o preço do bitcoin hoje?` | `[]` (fora de escopo) |

Cobre o gabarito de 6 da spec mais os 4 casos mínimos obrigatórios em uma
única passagem do `make test-contract`.

## Exemplos de uso

```bash
# pergunta dentro do escopo
curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"O que é composição?"}'

# pergunta fora do escopo (fallback)
curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"Qual o preço do bitcoin hoje?"}'

# sequência com session_id (memória curta entre chamadas)
curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"O que é composição?", "session_id":"sessao-123"}'

curl -X POST http://localhost:8000/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"Pode resumir em uma frase?", "session_id":"sessao-123"}'
```
