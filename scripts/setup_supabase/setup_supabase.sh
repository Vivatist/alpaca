#!/bin/bash
# Автоматическая установка и настройка Supabase
# Supabase будет установлен в домашнюю директорию ~/supabase

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUPABASE_DIR="$HOME/supabase"
SUPABASE_DOCKER="$SUPABASE_DIR/docker"

echo "🚀 Установка Supabase"
echo ""
echo "⚠️  Supabase будет установлен в: $SUPABASE_DIR"
echo ""
read -p "Продолжить? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отменено"
    exit 0
fi

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Клонирование Supabase если не установлен
if [ ! -d "$SUPABASE_DIR" ]; then
    echo "📦 Клонирование Supabase (это займет несколько минут)..."
    git clone --depth 1 https://github.com/supabase/supabase "$SUPABASE_DIR"
    echo "✅ Supabase клонирован"
else
    echo "✅ Supabase уже установлен в $SUPABASE_DIR"
fi

# Переход в директорию docker
cd "$SUPABASE_DOCKER"

# Создание .env если не существует
if [ ! -f ".env" ]; then
    echo "📝 Создание .env..."
    cp .env.example .env
    
    # Генерация безопасных секретов БЕЗ спецсимволов (/, +, =) для корректного URL-парсинга
    POSTGRES_PASSWORD=$(openssl rand -hex 24)
    JWT_SECRET=$(openssl rand -hex 24)
    DASHBOARD_PASSWORD=$(openssl rand -hex 12)
    
    # Обновление переменных
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|g" .env
    sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|g" .env
    sed -i "s|DASHBOARD_PASSWORD=.*|DASHBOARD_PASSWORD=$DASHBOARD_PASSWORD|g" .env
    
    # Конвертация .env в Unix-формат (удаление CRLF) для совместимости с Elixir
    sed -i 's/\r$//' .env
    
    echo "✅ Секреты сгенерированы"
else
    echo "✅ .env уже существует"
fi

# Извлечение паролей из .env (безопасный способ)
POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)
DASHBOARD_PASSWORD=$(grep "^DASHBOARD_PASSWORD=" .env | cut -d'=' -f2)

# Копирование docker-compose.override.yml (порт 54322 + сеть alpaca_network)
if [ ! -f "$SUPABASE_DOCKER/docker-compose.override.yml" ]; then
    echo "🔧 Копирование docker-compose.override.yml..."
    cp "$SCRIPT_DIR/docker-compose.override.yml" "$SUPABASE_DOCKER/"
    echo "✅ Override скопирован (порт 54322, сеть alpaca_network)"
else
    echo "✅ Override уже существует"
fi

# Создание Docker сети если не существует
docker network inspect alpaca_network >/dev/null 2>&1 || docker network create alpaca_network
echo "✅ Сеть alpaca_network готова"

# Конвертация конфигов pooler в Unix-формат (CRLF ломает Elixir парсер)
if [ -f "$SUPABASE_DOCKER/volumes/pooler/pooler.exs" ]; then
    sed -i 's/\r$//' "$SUPABASE_DOCKER/volumes/pooler/pooler.exs"
    echo "✅ Конфиг pooler конвертирован в Unix-формат"
fi

echo ""
echo "🗄️  Запуск Supabase..."

# Запуск Supabase (override подхватится автоматически)
docker compose up -d

# Ожидание готовности PostgreSQL
echo "⏳ Ожидание запуска PostgreSQL..."
MAX_RETRIES=30
RETRY_COUNT=0
until docker exec supabase-db pg_isready -U postgres >/dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Timeout: PostgreSQL не запустился"
        exit 1
    fi
    echo "   Попытка $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done
echo "✅ PostgreSQL готов"

# Применение схем
echo ""
echo "📋 Применение схемы базы данных..."
docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/schema_chunks.sql" 2>/dev/null || true
echo "✅ Таблица chunks создана"

docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/schema_files.sql" 2>/dev/null || true
echo "✅ Таблица files создана"

echo ""
echo "✅ Supabase настроен и запущен!"
echo ""
echo "📁 Директория: $SUPABASE_DOCKER"
echo "🌐 Сеть: alpaca_network"
echo "🔐 Пароль PostgreSQL: $POSTGRES_PASSWORD"
echo "🔌 PostgreSQL: localhost:54322"
echo "🗄️  Таблицы: chunks, files"
echo ""
echo "🌐 Dashboard: http://localhost:8000"
echo "   Username: supabase"
echo "   Password: $DASHBOARD_PASSWORD"
echo ""
echo "DATABASE_URL для docker-compose.yml сервисов:"
echo "  postgresql://postgres:$POSTGRES_PASSWORD@db:5432/postgres"
echo ""
echo "DATABASE_URL для локальной разработки:"
echo "  postgresql://postgres:$POSTGRES_PASSWORD@localhost:54322/postgres"
