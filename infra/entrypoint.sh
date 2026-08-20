#!/bin/sh
# Partida do container.
#
# As migrations rodam aqui, e nao em uma etapa separada, porque o plano
# gratuito das hospedagens nao oferece fase de release. `alembic upgrade
# head` e idempotente: se o banco ja esta na versao, nao faz nada.
set -e

echo "> aplicando migrations"
alembic upgrade head

# O mundo ficticio so e semeado quando pedido e apenas se o banco estiver
# vazio. Sem a guarda, cada reinicio duplicaria o mundo inteiro.
#
# A falha da semeadura NAO derruba o servico. Ela depende do provedor de
# embeddings, ou seja, de uma chave e de uma rede que nao estao sob o
# controle desta aplicacao. Um servico morto por causa disso nao deixa nem
# a pagina de erro no ar, e ninguem consegue sequer abrir /health para
# descobrir o que houve. Sobe degradado, dizendo o que faltou.
if [ "${SEMEAR_NA_PARTIDA}" = "true" ]; then
	echo "> verificando se o banco precisa de semeadura"
	if ! python -m app.seed --se-vazio; then
		echo "! semeadura falhou. A API sobe assim mesmo, com o banco vazio."
		echo "! corrija a causa acima e reinicie o servico para semear."
	fi
fi

# ${PORT} e injetado pela hospedagem; 8000 e o padrao local.
# --proxy-headers porque a plataforma sempre coloca um proxy na frente.
echo "> subindo a API na porta ${PORT:-8000}"
exec uvicorn app.main:app \
	--host 0.0.0.0 \
	--port "${PORT:-8000}" \
	--proxy-headers \
	--forwarded-allow-ips "*"
