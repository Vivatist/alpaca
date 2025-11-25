#!/bin/bash
# Быстрый перезапуск Supabase Kong и Studio для восстановления доступа к UI

echo "🔄 Restarting Supabase Kong and Studio..."

docker restart supabase-kong
docker restart supabase-studio

echo "⏳ Waiting 5 seconds for services to start..."
sleep 5

echo "✅ Services restarted!"
echo "🌐 Open http://localhost:8000 in your browser"
echo ""
echo "📊 Service status:"
docker ps --filter name=supabase-kong --filter name=supabase-studio --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
