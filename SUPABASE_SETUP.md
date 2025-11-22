# Установка Supabase (отдельно)

Supabase устанавливается отдельно от основного проекта для упрощения управления.

## Вариант 1: Self-Hosted Supabase (Docker)

### Установка

```bash
# Клонируйте репозиторий Supabase в отдельную директорию
cd ~/
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker

# Скопируйте конфигурацию
cp .env.example .env
```

### Настройка .env

Отредактируйте `.env` и установите следующие переменные:

```bash
# ОБЯЗАТЕЛЬНО измените эти значения!
POSTGRES_PASSWORD=ваш-надежный-пароль
JWT_SECRET=$(openssl rand -base64 32)
ANON_KEY=сгенерируйте-через-jwt
SERVICE_ROLE_KEY=сгенерируйте-через-jwt
```

Для генерации JWT ключей:

```bash
# Установите PyJWT
pip install PyJWT

# Генерация ANON_KEY
python3 -c "
import jwt
import datetime
secret = 'ваш-JWT_SECRET'
payload = {
    'role': 'anon',
    'iss': 'supabase',
    'iat': int(datetime.datetime.now().timestamp()),
    'exp': int((datetime.datetime.now() + datetime.timedelta(days=3650)).timestamp())
}
print(jwt.encode(payload, secret, algorithm='HS256'))
"

# Генерация SERVICE_ROLE_KEY
python3 -c "
import jwt
import datetime
secret = 'ваш-JWT_SECRET'
payload = {
    'role': 'service_role',
    'iss': 'supabase',
    'iat': int(datetime.datetime.now().timestamp()),
    'exp': int((datetime.datetime.now() + datetime.timedelta(days=3650)).timestamp())
}
print(jwt.encode(payload, secret, algorithm='HS256'))
"
```

### Запуск

```bash
cd ~/supabase/docker
docker compose up -d
```

### Доступ

- **Studio UI**: http://localhost:8000
- **API Gateway**: http://localhost:8000
- **PostgreSQL (прямое подключение)**: localhost:5432
- **PostgreSQL (pooled)**: localhost:6543

### Connection String для проекта

После запуска используйте pooled connection в `.env` проекта:

```
DATABASE_URL=postgresql://postgres:ваш-пароль@localhost:6543/postgres
```

## Вариант 2: Supabase Cloud

1. Зарегистрируйтесь на https://supabase.com
2. Создайте новый проект
3. Перейдите в Settings → Database
4. Скопируйте Connection String
5. Вставьте в `.env` проекта

## Проверка подключения

```bash
# Из виртуального окружения проекта
cd ~/alpaca
source venv/bin/activate
python -c "
from app.settings import settings
print(f'DATABASE_URL: {settings.DATABASE_URL}')
"
```
