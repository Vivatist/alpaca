#!/bin/bash
# Проброс SOCKS5 прокси для Docker-контейнеров
# Запускать на хосте перед работой с Dev Containers

PROXY_SRC="127.0.0.1:10808"
PROXY_DST="172.17.0.1:10809"

# Убиваем старый процесс если есть
pkill -f "socat.*10809" 2>/dev/null

# Запускаем socat
socat TCP-LISTEN:10809,bind=172.17.0.1,fork,reuseaddr TCP:127.0.0.1:10808 &

sleep 1

if ss -tlnp | grep -q "172.17.0.1:10809"; then
    echo "✅ Прокси проброшен: $PROXY_SRC → $PROXY_DST"
    echo "   Контейнеры могут использовать: socks5://172.17.0.1:10809"
else
    echo "❌ Не удалось запустить socat"
    exit 1
fi
