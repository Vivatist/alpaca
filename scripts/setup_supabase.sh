#!/bin/bash
# Автоматическая установка и настройка Supabase

set -e

SUPABASE_HOME="/home/alpaca/supabase"
SUPABASE_DOCKER="$SUPABASE_HOME/docker"

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
cp docker-compose.yml docker-compose.yml.backup

# Добавление external network в docker-compose.yml
echo "🔧 Настройка сетевого взаимодействия..."
if ! grep -q "alpaca_network" docker-compose.yml; then
    # Добавляем external network
    cat >> docker-compose.yml << 'EOF'

# Подключение к сети проекта alpaca
networks:
  default:
    name: alpaca_network
    external: true
EOF
    echo "✅ Сеть alpaca_network настроена"
else
    echo "✅ Сеть уже настроена"
fi

# Сохранение DATABASE_URL в .env проекта alpaca
source .env
ALPACA_ENV="/home/alpaca/alpaca/.env"
if [ -f "$ALPACA_ENV" ]; then
    # Обновляем DATABASE_URL в проекте
    if grep -q "^DATABASE_URL=" "$ALPACA_ENV"; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:$POSTGRES_PASSWORD@supabase-db:6543/postgres|g" "$ALPACA_ENV"
    else
        echo "DATABASE_URL=postgresql://postgres:$POSTGRES_PASSWORD@supabase-db:6543/postgres" >> "$ALPACA_ENV"
    fi
    echo "✅ DATABASE_URL обновлён в проекте alpaca"
fi

echo ""
echo "✅ Supabase готов к запуску!"
echo ""
echo "📁 Директория: $SUPABASE_DOCKER"
echo "🌐 Сеть: alpaca_network (общая с alpaca проектом)"
echo "🔐 Пароль PostgreSQL: $POSTGRES_PASSWORD"
echo ""
echo "Для запуска всех сервисов используйте:"
echo "  ./scripts/start_services.sh"
