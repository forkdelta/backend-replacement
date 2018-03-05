#!/bin/sh

# Set the default variables values
# Service to launch
COMPONENT=${COMPONENT:-websocket}
HUEY_CONCURRENCY=${HUEY_CONCURRENCY:-3}
MIGRATION=${2:-head}

if [ "$COMPONENT" = "websocket" ]; then
    echo "[$0] Starting $COMPONENT service !"
    python3 -m app.services.websocket_server

elif [ "$COMPONENT" = "contract_observer" ]; then
    if [ "$1" = "migrate" ]; then
        echo "[$0] Starting DB migration !"

        alembic upgrade ${MIGRATION}
    else
        echo "[$0] Starting $COMPONENT service !"
        python3 -m app.services.contract_observer
    fi


elif [ "$COMPONENT" = "etherdelta_observer" ]; then
    echo "[$0] Starting $COMPONENT service !"
    python3 -m app.services.etherdelta_observer

elif [ "$COMPONENT" = "huey_consumer" ]; then
    echo "[$0] Starting $COMPONENT service !"
    huey_consumer.py app.services.huey_consumer.huey -w ${HUEY_CONCURRENCY} -k greenlet

elif [ "$COMPONENT" = "ticker" ]; then
    echo "[$0] Starting $COMPONENT service !"
    python3 -m app.services.ticker
else
    echo "[$0] Service [$COMPONENT] is not valid !"
    exit -1
fi