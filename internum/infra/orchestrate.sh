#!/bin/bash

cleanup() {
    echo "Sinal de interrupção recebido. Executando post-run..."
    poetry run task servicesStop
}

trap cleanup SIGINT

echo "Inicializando o container do Postgress..."
poetry run task servicesUp

echo "Inicializando a aplicação..."
fastapi dev internum/app.py &

PID=$!

wait $PID