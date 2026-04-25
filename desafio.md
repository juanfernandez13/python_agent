# Python Agent Challenge

Desafio técnico para vaga **A1/A2**: construir um backend Python com orquestração de fluxo por IA e uma base de conhecimento em Markdown.

## Objetivo

Montar uma solução simples e funcional com:

- API em Python.
- Orquestração de fluxo no backend (pode usar padrões de agente ou estrutura equivalente).
- Uso de uma tool para buscar contexto.
- Resposta gerada com LLM e rastreável por fonte.

## Entrega obrigatória

- Endpoint único: `POST /messages`
- KB obrigatória: `KB_URL` deve apontar para a base do desafio neste repositório:  
  `https://raw.githubusercontent.com/igortce/python-agent-challenge/refs/heads/main/python_agent_knowledge_base.md`
- A solução enviada deve usar esta KB pública como fonte oficial de validação final.
- Regra de aceite: para a validação final da vaga, `KB_URL` precisa referenciar esta URL (sem usar cópia local da KB como fonte principal).
- Entrada mínima: `message`
- No fluxo principal de `/messages`, orquestrar as etapas de:
  - receber `message`,
  - consultar contexto via tool,
  - chamar LLM com pergunta + contexto,
  - retornar `answer`.
- Uso obrigatório de **uma tool** para consultar a base de conhecimento em Markdown
- A consulta da tool deve ser via HTTP, usando `KB_URL` (URL configurável).
- Uso de LLM no fluxo principal
- Retornar apenas:
  - `answer` (texto)
  - `sources` (apenas `section`)
- Em `sources`, cada item deve ter somente `section`.
- `session_id`: opcional.
  - Se enviado, o fluxo pode manter contexto curto para esse identificador.
  - Se não enviado, cada chamada é independente.
- Explicar em texto curto quais regras foram passadas ao fluxo no projeto (sem publicar “receita pronta” de prompt).
- Sem frontend obrigatório

## Regras técnicas

- Pode usar qualquer framework/lib de API e qualquer biblioteca de LLM (ou implementação manual), desde que o comportamento final atenda ao contrato.
- Não precisa de arquitetura complexa nem serviços extras na entrega mínima.
- Para padronizar, deixe o provedor/modelo configurável por ambiente (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL` no `.env`).
- O serviço em `docker compose` deve ler variáveis do `.env` (seja via `env_file` no serviço ou configuração equivalente).
- É recomendado usar FastAPI por ergonomia (Swagger automático), mas não é obrigatório.

## LLM no fluxo principal (sem detalhe de framework)

- O LLM é responsável pela síntese final da resposta.
- O fluxo de orquestração deve combinar `message` + contexto da tool e gerar `answer`.
- A lógica de busca fica fora do LLM, via tool obrigatória.
- A tool deve buscar a KB em Markdown via HTTP a partir de `KB_URL` e retornar trechos relevantes para contexto.
- Não pode responder com texto hardcoded ou regras internas fora da KB.
- Não confie em `temperature` para garantir formato; valide saída no código (especialmente estrutura).
- Fallback obrigatório: sem contexto suficiente, retornar `answer` padrão + `sources: []`.
- Quando falamos de “regras do fluxo/prompt”, queremos regras de decisão simples:
  - quando chamar a tool;
  - quais partes do contexto entram no LLM;
  - quando retornar fallback.

## Diferencial (opcional)

- Expor OpenAPI/Swagger (ex.: FastAPI automático).
- Implementar estado por sessão com `session_id` para manter contexto curto entre chamadas.
- Se implementar sessão:
  - manter isolamento entre `session_id`;
  - manter limite de histórico (janela curta) por sessão;
  - aplicar expiração (TTL) do estado para limpar memória antiga.
- Se a sessão precisar persistência fora do processo da aplicação, incluir serviço de armazenamento no `docker compose` (sem requisito de tecnologia específica).
- Disponibilizar `Makefile` com objetivos básicos (opcional):
  - `make up` (subir ambiente);
  - `make down` (encerrar ambiente);
  - `make test` (validar contrato mínimo).

## Configuração da KB

- Use `KB_URL` apontando para a KB em Markdown do repositório do desafio:  
  `https://raw.githubusercontent.com/igortce/python-agent-challenge/refs/heads/main/python_agent_knowledge_base.md`
- A resposta do sistema deve ser construída a partir do contexto retornado pela tool.
- A base de conhecimento é propositalmente técnica e curta; o objetivo é o candidato justificar decisões com base nela, não copiar fluxo inteiro.

> A URL acima é a fonte oficial de validação. O candidato pode sobrescrever `KB_URL` para testes locais, **mas a submissão final deve usar esta KB pública**.

### Exemplo de variáveis (`.env.example`)

```env
KB_URL=https://raw.githubusercontent.com/igortce/python-agent-challenge/refs/heads/main/python_agent_knowledge_base.md
# Exemplo (padrão de execução). Outras combinações de LLM são aceitas.
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sua_chave_aqui

MEMORY_STORE=

HOST=0.0.0.0
PORT=8000
```

`MEMORY_STORE` pode ficar vazio na entrega mínima; use somente se implementar memória por `session_id`.

### Observação importante de interoperabilidade

- O `.env.example` usa OpenAI apenas como ponto de partida.
- O que importa para aprovação é o fluxo funcional com `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL` e `LLM_API_KEY` corretos.
- Provedores alternativos (como Azure OpenAI, OpenRouter, Ollama, Mistral, etc.) são aceitos desde que:
  - o serviço responda ao modelo escolhido via API compatível;
  - o restante do contrato esteja correto;
  - o fallback e a integração com a KB funcionem.

## Como validar localmente (mínimo)

- Copiar variáveis: `cp .env.example .env` (ou criar `.env` equivalente).
- Confirmar no `docker compose` que o serviço consome `KB_URL`/`LLM_*` do `.env`.
- Subir serviços: `docker compose up -d --build`.
- Executar a rota de sucesso com uma pergunta base.
- Executar pergunta sem contexto para validar fallback.
- Desligar serviços ao fim: `docker compose down`.
- Se houver `Makefile` com os alvos acima, pode usar `make up`, `make test` e `make down`.

## Requisito mínimo de composição (compose)

- Entrega mínima deve incluir `docker compose` funcional.
- O container da API deve expor porta `8000`.
- O container da API deve iniciar a partir das variáveis definidas em `.env`.
- Em revisão, é necessário ver que `KB_URL`, `LLM_PROVIDER`, `LLM_MODEL` e `LLM_API_KEY` entram no runtime do container.

Exemplos esperados:

```bash
curl -X POST "http://localhost:8000/messages" \
  -H "Content-Type: application/json" \
  -d '{"message":"O que é composição?"}'

curl -X POST "http://localhost:8000/messages" \
  -H "Content-Type: application/json" \
  -d '{"message":"Pergunta fora do escopo da KB"}'

# Opcional (com session_id): testar continuidade de contexto
curl -X POST "http://localhost:8000/messages" \
  -H "Content-Type: application/json" \
  -d '{"message":"O que é composição?","session_id":"sessao-123"}'

curl -X POST "http://localhost:8000/messages" \
  -H "Content-Type: application/json" \
  -d '{"message":"Pode resumir em uma frase?","session_id":"sessao-123"}'
```

## Contrato da API

### Requisição

```json
{
  "message": "O que é composição?"
}
```

```json
{
  "message": "Pode resumir o que falamos?",
  "session_id": "sessao-123"
}
```

> `session_id` pode ser enviado opcionalmente para fluxos com memória curta:
> ```json
> { "message": "Pode resumir a resposta anterior?", "session_id": "sessao-123" }
> ```

### Resposta (sucesso)

```json
{
  "answer": "A ferramenta de conhecimento localiza trechos úteis da base em Markdown para apoiar a resposta.",
  "sources": [
    {
      "section": "Tool"
    }
  ]
}
```

> `sources` no sucesso deve conter **pelo menos 1** seção.
> Cada item deve conter apenas `section` (sem exigir `excerpt` no contrato).
> Se necessário, pode haver múltiplas seções em `sources`.

> Observação de implementação: em logs internos de avaliação você pode incluir `line`/`excerpt` para depuração, mas **não** é requisito do contrato da API.

### Sem contexto suficiente

```json
{
  "answer": "Não encontrei informação suficiente na base para responder essa pergunta.",
  "sources": []
}
```

## Fluxo mínimo esperado

1. Receber `message`.
2. O fluxo de orquestração chama a tool para buscar contexto relevante.
3. Tool consulta `KB_URL` por HTTP e retorna seções/trechos.
4. O fluxo monta chamada ao LLM com pergunta + contexto.
5. Retornar resposta final em JSON. Sem contexto: fallback obrigatório.

## Regras de implementação

- Validar `message` na entrada.
- Separar responsabilidades em API, orquestração, tool e cliente LLM.
- `sources` só pode conter seções realmente usadas.
- Documentar a estratégia do fluxo (regras de decisão): quando consultar tool, como montar contexto e como decidir fallback.
- Não responder perguntas de forma hardcoded.
- Implementar fallback com `sources: []` quando não houver contexto suficiente.
- Se implementar memória por sessão, garantir:
  - sessões isoladas por `session_id`;
  - contexto curto por sessão;
  - não vazamento de estado entre sessões diferentes.

## Entrega do candidato

- Repositório próprio no GitHub (com acesso para revisão).
- Código-fonte da API.
- `docker compose` funcional.
- Instruções para executar localmente.
- `.env.example` (se houver variáveis).
- Explicação curta de decisões técnicas.

## Validação (automática + revisão)

### Casos mínimos obrigatórios para revisão (4 perguntas)

- `O que é composição?`  
  - `sources`: `Composição`.
- `Qual o papel da Tool de conhecimento?`  
  - `sources`: `Tool de conhecimento`.
- `A tool deve responder diretamente ao usuário?`  
  - `sources`: `Tool de conhecimento`.
- `Como agir sem contexto suficiente?`  
  - `sources`: `[]` e mensagem padrão de fallback.

- Validação mínima automatizada:
  - `POST /messages` retorna JSON válido com `answer` e `sources`.
  - Em validação final, confirmar que a KB carregada pelo fluxo é a URL oficial do desafio.
  - Pergunta sem contexto retorna o fallback com `sources: []`.
  - O texto do fallback deve ser:
    - `Não encontrei informação suficiente na base para responder essa pergunta.`
- Validação opcional:
  - sem `session_id`: chamadas independentes;
  - com `session_id` repetido: manter estado de conversa;
  - com `session_id` novo: iniciar nova sessão sem histórico anterior.
  - Esta validação só é exigida se a memória por `session_id` estiver implementada.
- Pontuação de diferencial de sessão (e opcional de persistência) só é considerada se o candidato implementar corretamente `session_id`.
- `Makefile` opcional para automação local (up/down/test) pode aumentar ponto de organização se presente.
- Validação de qualidade:
  - 4 a 6 perguntas de referência na KB.
  - `sources` deve incluir seção esperada.
  - Conteúdo da resposta com termos centrais esperados (sem exigir texto idêntico).

### Gabarito mínimo de avaliação (padronizado)

- Pergunta: `O que é composição?`
  - `sources`: `Composição`
  - Esperado: definição breve e observação de uso prático.
- Pergunta: `Quando usar herança?`
  - `sources`: `Herança`
  - Esperado: citar cenários de semelhança de contrato/comportamento.
- Pergunta: `Qual o papel da orquestração?`
  - `sources`: `Orquestração`
  - Esperado: coordenar decisão de fluxo, tool e chamada do LLM.
- Pergunta: `A tool deve responder diretamente ao usuário?`
  - `sources`: `Tool de conhecimento`
  - Esperado: explicar que a tool recupera contexto e o LLM gera resposta final.
- Pergunta: `Como agir sem contexto suficiente?`
  - `sources`: `Falta de contexto`
  - Esperado: fallback padrão com `sources: []`.
- Pergunta: `Onde colocar regra de negócio, no endpoint ou no fluxo interno?`
  - `sources`: `Endpoint de API` (e, de preferência, `Responsabilidade única`)
  - Esperado: regra de negócio fora do endpoint, principalmente separando orquestração.

### Recomendação prática de LLM (custo)

- O teste deve funcionar com qualquer modelo, desde que:
  - seja acessível via HTTP;
  - aceite prompt + contexto;
  - retorne texto consistente no formato.
- Para reduzir custo no teste, recomenda-se:
  - modelo mais leve/mais barato do provedor escolhido;
  - poucas chamadas e perguntas curtas.
- Para não travar custo, as chamadas podem começar com um modelo gratuito/disponibilizado pelo candidato (se disponível), desde que seja trocável pela configuração acima.
- Se não houver orçamento para chamadas pagas, pode-se usar qualquer endpoint gratuito equivalente durante desenvolvimento, mas a entrega final precisa manter o fluxo real de LLM ativo.

## Critérios de aprovação

- Endpoint e contrato corretos.
- Uso real de orquestração + tool + LLM no fluxo principal.
- Explicitação clara da política de decisão do fluxo (regras de decisão) na entrega.
- `sources` consistente com a KB usada.
- Resposta de fallback clara sem contexto.
- Organização razoável para o nível A1/A2.
- Falha em qualquer item da validação mínima (incluindo `KB_URL` oficial e fallback padrão) invalida o teste.

## Escopo

- Não é necessário frontend.
- Não é necessário MCP real.
- Não são necessários múltiplos serviços complexos.
