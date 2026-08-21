#!/usr/bin/env bash
# Liga, desliga e mostra a proteção de branch do repositório alvo.
#
# Usa a SUA credencial do `gh`, nunca a do GitHub App — e isso é deliberado.
# O App tem `checks: write`, `contents: read` e `pull_requests: read`, e NÃO
# tem `administration`. Se ele pudesse mexer na proteção de branch, o portão
# teria permissão para desligar a regra que o obriga, e bastaria comprometer a
# chave privada para liberar qualquer merge. Quem afrouxa a regra é a pessoa,
# com a credencial dela, deixando rastro no log de auditoria do GitHub.
#
#   scripts/protecao_branch.sh estado
#   scripts/protecao_branch.sh desligar    # antes de trabalhar com a infra no chão
#   scripts/protecao_branch.sh ligar       # depois de `make subir`
#
# Por que desligar é às vezes necessário: com checagem obrigatória e a
# infraestrutura destruída, todo PR novo fica esperando para sempre um
# `seguranca/portcullis` que ninguém vai reportar.

set -euo pipefail

REPO="${REPO_ALVO:-gabhrielv/hoppr}"
BRANCH="${BRANCH_ALVO:-main}"
CHECAGEM="seguranca/portcullis"
CAMINHO="repos/${REPO}/branches/${BRANCH}/protection"

ligar() {
  # `strict: false` de propósito: exigir branch atualizada com a main faria
  # cada avanço da main disparar uma análise nova de ~4 min em todo PR aberto.
  # `enforce_admins: true` é o que impede o dono de mergear por cima do
  # vermelho — sem isso o portão vira decoração.
  gh api -X PUT "$CAMINHO" --input - >/dev/null <<JSON
{
  "required_status_checks": {
    "strict": false,
    "checks": [{"context": "${CHECAGEM}"}]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
  echo "protecao LIGADA em ${REPO}:${BRANCH} exigindo '${CHECAGEM}'"
}

desligar() {
  gh api -X DELETE "$CAMINHO" >/dev/null
  echo "protecao DESLIGADA em ${REPO}:${BRANCH}"
  echo "AVISO: o merge deixa de depender do portao ate voce religar."
}

estado() {
  if ! gh api "$CAMINHO" >/dev/null 2>&1; then
    echo "${REPO}:${BRANCH} — sem protecao"
    return
  fi
  gh api "$CAMINHO" --jq "\"${REPO}:${BRANCH} — protegida
  checagens exigidas : \(.required_status_checks.checks | map(.context) | join(\", \"))
  vale para admin    : \(.enforce_admins.enabled)
  exige branch atual : \(.required_status_checks.strict)
  exige PR           : \(.required_pull_request_reviews != null)\""
}

case "${1:-}" in
  ligar) ligar ;;
  desligar) desligar ;;
  estado) estado ;;
  *)
    echo "uso: $(basename "$0") {ligar|desligar|estado}" >&2
    exit 2
    ;;
esac
