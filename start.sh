#!/bin/bash

echo "Starting AI Novel Writing Platform..."
echo ""

docker compose up -d --build

echo ""
echo "Services are starting up..."
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8001"
echo "  Postgres: localhost:5433"
echo "  Redis:    localhost:6380"
echo ""
echo "Use 'docker compose logs -f' to follow logs."
