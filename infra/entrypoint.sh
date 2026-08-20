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
if [ "${SEMEAR_NA_PARTIDA}" = "true" ]; then
	echo "> verificando se o banco precisa de semeadura"
	python -m app.seed --se-vazio
fi

# ${PORT} e injetado pela hospedagem; 8000 e o padrao local.
# --proxy-headers porque a plataforma sempre coloca um proxy na frente.
echo "> subindo a API na porta ${PORT:-8000}"
exec uvicorn app.main:app \
	--host 0.0.0.0 \
	--port "${PORT:-8000}" \
	--proxy-headers \
	--forwarded-allow-ips "*"
