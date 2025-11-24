#!/bin/bash
# Скрипт для запуска file_watcher контейнера

set -e

echo "🐋 Building File Watcher container..."
cd "$(dirname "$0")/.."
docker build -t alpaca-filewatcher -f docker/Dockerfile.filewatcher .

echo ""
echo "✅ Build complete!"
echo ""
echo "To run the container:"
echo "  docker-compose -f docker/docker-compose.yml up filewatcher"
echo ""
echo "Or standalone:"
echo "  docker run -d \\"
echo "    --name filewatcher \\"
echo "    -v /path/to/monitored:/monitored_folder:ro \\"
echo "    -e DATABASE_URL=postgresql://user:pass@host:port/db \\"
echo "    alpaca-filewatcher"
