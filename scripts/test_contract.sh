#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
FALLBACK="Não encontrei informação suficiente na base para responder essa pergunta."

pass=0
fail=0

_assert_section() {
    local label="$1"; shift
    local body="$1"; shift
    local expected="$1"; shift
    if echo "$body" | grep -Fq "\"section\":\"$expected\""; then
        echo "PASS: $label -> contém seção '$expected'"
        pass=$((pass + 1))
    else
        echo "FAIL: $label -> esperava seção '$expected', body=$body"
        fail=$((fail + 1))
    fi
}

_assert_fallback() {
    local label="$1"; shift
    local body="$1"; shift
    if echo "$body" | grep -Fq "\"sources\":[]" && echo "$body" | grep -Fq "$FALLBACK"; then
        echo "PASS: $label -> fallback ok"
        pass=$((pass + 1))
    else
        echo "FAIL: $label -> esperava fallback, body=$body"
        fail=$((fail + 1))
    fi
}

_post() {
    curl -s -X POST "$BASE_URL/messages" \
        -H "Content-Type: application/json" \
        -d "$1"
}

echo "-> health"
curl -fsS "$BASE_URL/health" >/dev/null && echo "PASS: /health"

_assert_section "O que é composição?" \
    "$(_post '{"message":"O que é composição?"}')" "Composição"

_assert_section "Quando usar herança?" \
    "$(_post '{"message":"Quando usar herança?"}')" "Herança"

_assert_section "Qual o papel da orquestração?" \
    "$(_post '{"message":"Qual o papel da orquestração?"}')" "Orquestração"

_assert_section "Papel da Tool de conhecimento" \
    "$(_post '{"message":"Qual o papel da Tool de conhecimento?"}')" "Tool de conhecimento"

_assert_section "Tool deve responder diretamente?" \
    "$(_post '{"message":"A tool deve responder diretamente ao usuário?"}')" "Tool de conhecimento"

_assert_section "Onde colocar regra de negócio?" \
    "$(_post '{"message":"Onde colocar regra de negócio, no endpoint ou no fluxo interno?"}')" "Endpoint de API"

_assert_fallback "Pergunta fora de escopo" \
    "$(_post '{"message":"Qual o preço do bitcoin hoje?"}')"

_assert_fallback "Como agir sem contexto suficiente?" \
    "$(_post '{"message":"Como agir sem contexto suficiente?"}')"

echo
echo "Resumo: ${pass} pass, ${fail} fail"
if [[ $fail -gt 0 ]]; then
    exit 1
fi
