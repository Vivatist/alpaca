#!/bin/bash
# Автоматическая установка и настройка Supabase

set -e

SUPABASE_HOME="/home/alpaca/supabase"
SUPABASE_DOCKER="$SUPABASE_HOME/docker"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NETWORK_PATCH="$SCRIPT_DIR/supabase-network-patch.yml"
DB_PORT_PATCH="$SCRIPT_DIR/supabase-db-port-patch.yml"

echo "🚀 Установка Supabase..."
echo ""

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Клонирование Supabase если не установлен
if [ ! -d "$SUPABASE_HOME" ]; then
    echo "📦 Клонирование Supabase (это займет несколько минут)..."
    cd /home/alpaca
    git clone --depth 1 https://github.com/supabase/supabase
    echo "✅ Supabase клонирован"
else
    echo "✅ Supabase уже установлен"
fi

# Переход в директорию docker
cd "$SUPABASE_DOCKER"

# Создание .env если не существует
if [ ! -f ".env" ]; then
    echo "📝 Создание .env..."
    cp .env.example .env
    
    # Генерация безопасных секретов
    POSTGRES_PASSWORD=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 32)
    
    # Обновление переменных
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|g" .env
    sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|g" .env
    
    echo "✅ Секреты сгенерированы"
fi

# Создание резервной копии docker-compose.yml
cp "$SUPABASE_DOCKER/docker-compose.yml" "$SUPABASE_DOCKER/docker-compose.yml.backup"

# Добавление external network в docker-compose.yml
echo "🔧 Настройка сетевого взаимодействия..."

if ! grep -q "alpaca_network" "$SUPABASE_DOCKER/docker-compose.yml"; then
    # Добавляем external network
    if [ -f "$NETWORK_PATCH" ]; then
        cat "$NETWORK_PATCH" >> "$SUPABASE_DOCKER/docker-compose.yml"
    else
        cat >> "$SUPABASE_DOCKER/docker-compose.yml" << 'EOF'

# Подключение к сети проекта alpaca
networks:
  default:
    name: alpaca_network
    external: true
EOF
    fi
    echo "✅ Сеть alpaca_network настроена"
else
    echo "✅ Сеть уже настроена"
fi

# Сохранение DATABASE_URL в .env проекта alpaca
source .env
ALPACA_ENV="/home/alpaca/alpaca/.env"
if [ -f "$ALPACA_ENV" ]; then
    # Обновляем DATABASE_URL в проекте (используем порт 54322 для прямого доступа)
    if grep -q "^DATABASE_URL=" "$ALPACA_ENV"; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:$POSTGRES_PASSWORD@localhost:54322/postgres|g" "$ALPACA_ENV"
    else
        echo "DATABASE_URL=postgresql://postgres:$POSTGRES_PASSWORD@localhost:54322/postgres" >> "$ALPACA_ENV"
    fi
    echo "✅ DATABASE_URL обновлён в проекте alpaca"
fi

echo ""
echo "🗄️  Применение схемы базы данных..."

# Создание Docker сети если не существует
docker network inspect alpaca_network >/dev/null 2>&1 || docker network create alpaca_network

# Запуск Supabase для инициализации базы
echo "📦 Запуск Supabase с пробросом порта БД..."
docker compose -f docker-compose.yml -f "$DB_PORT_PATCH" up -d

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
echo "📋 Применение схемы chunks..."
docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/schema_chunks.sql" >/dev/null 2>&1
echo "✅ Таблица chunks создана"

echo "📋 Применение схемы files..."
docker exec -i supabase-db psql -U postgres -d postgres < "$SCRIPT_DIR/schema_files.sql" >/dev/null 2>&1
echo "✅ Таблица files создана"

echo ""
echo "✅ Supabase настроен и запущен!"
echo ""
echo "📁 Директория: $SUPABASE_DOCKER"
echo "🌐 Сеть: alpaca_network (общая с alpaca проектом)"
echo "🔐 Пароль PostgreSQL: $POSTGRES_PASSWORD"
echo "🔌 PostgreSQL порт: localhost:54322"
echo "🗄️  Таблицы: chunks (векторная), files (отслеживание)"
echo "🌐 Dashboard: http://localhost:8000"
echo ""
echo "Для управления сервисами используйте:"
echo "  ./scripts/start_services.sh  - запуск"
echo "  ./scripts/stop_services.sh   - остановка"
