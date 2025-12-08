#!/bin/bash
# Сброс Supabase для переустановки
# Удаляет .env и данные БД, но сохраняет клонированный репозиторий

set -e

SUPABASE_DOCKER="$HOME/supabase/docker"

if [ ! -d "$SUPABASE_DOCKER" ]; then
    echo "❌ Supabase не установлен в $SUPABASE_DOCKER"
    exit 1
fi

echo "⚠️  Это удалит:"
echo "   - Все данные PostgreSQL"
echo "   - Файл .env с паролями"
echo "   - Docker volumes"
echo ""
read -p "Продолжить? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 0
fi

cd "$SUPABASE_DOCKER"

echo "🛑 Остановка контейнеров..."
docker compose down -v 2>/dev/null || true

echo "🗑️  Удаление .env..."
rm -f .env

echo "🗑️  Удаление данных БД..."
rm -rf volumes/db/data

echo ""
echo "✅ Готово к переустановке!"
echo ""
echo "Запустите скрипт установки:"
echo "  ./scripts/setup_supabase/setup_supabase.sh"
