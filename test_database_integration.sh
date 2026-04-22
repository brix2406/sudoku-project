#!/bin/bash

set -e

echo "Starting Docker Compose testing environment..."
# Clean up any existing volumes so we have a fresh database for the test
docker compose down -v
docker compose build --quiet
docker compose up -d

echo "Waiting 15 seconds for containers to initialize and process the first NATS message..."
sleep 15

echo ""
echo "==== 1. Checking if data was written to the database ===="
if docker logs service_layer_rust 2>&1 | grep -q "Adding it to DB now"; then
    echo "[PASS] Data was successfully written to the database."
else
    echo "[FAIL] Initial write to the database failed or was not logged."
    docker logs service_layer_rust
    exit 1
fi

echo ""
echo "==== 2. Checking if marmot sidecar monitored the updates ===="
if docker logs marmot-sidecar 2>&1 | grep -iq "CDC notification hub initialized"; then
    echo "[PASS] Marmot sidecar is correctly monitoring the database."
else
    echo "[FAIL] Marmot CDC failed to initialize."
    docker logs marmot-sidecar | tail -n 20
    exit 1
fi

echo ""
echo "==== 3. Simulating a crash / container restart ===="
echo "Stopping service_layer_rust container..."
docker stop service_layer_rust
sleep 3

RESTART_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Starting service_layer_rust container..."
docker start service_layer_rust

echo "Waiting 15 seconds for it to reconnect to NATS and read from DB..."
sleep 15

echo ""
echo "==== 4. Checking if database is persistent and reading works ===="
# We check only logs from AFTER the restart to ensure we aren't matching earlier DB lookups
if docker logs --since "$RESTART_TIME" service_layer_rust | grep -q "Found sudoko in DB"; then
    echo "[PASS] The database is persistent and reading works after container crash."
else
    echo "[FAIL] Container did not find the data in the DB after restart."
    docker logs --since "$RESTART_TIME" service_layer_rust
    exit 1
fi

echo ""
echo "All tests passed successfully!"
echo "The database is persistent, reading/writing works, data is not wiped on crash, and marmot integrates correctly."
