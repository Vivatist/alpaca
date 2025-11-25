#!/bin/bash
# SSH туннели для доступа к сервисам на удалённой машине
# Запускайте этот скрипт на ЛОКАЛЬНОЙ машине

# Замените 'alpaca' на имя вашего SSH хоста из ~/.ssh/config
SSH_HOST="alpaca"

echo "🔌 Setting up SSH tunnels..."
echo "Press Ctrl+C to stop all tunnels"

# Создаём туннели для всех сервисов
ssh -N -L 8000:localhost:8000 \
       -L 54322:172.17.0.1:54322 \
       -L 8081:localhost:8081 \
       -L 8080:localhost:8080 \
       -L 11434:localhost:11434 \
       $SSH_HOST

# После запуска откройте в браузере:
# Supabase Studio: http://localhost:8000
# File Watcher API: http://localhost:8081
# Admin Backend: http://localhost:8080
