#!/bin/bash
# Watchdog для автоматического перезапуска Supabase UI при проблемах с доступом
# Запускайте в фоне: nohup ./scripts/supabase_ui_watchdog.sh &

INTERVAL=30  # Проверка каждые 30 секунд
MAX_FAILURES=3
failures=0

echo "🐕 Supabase UI Watchdog started"
echo "Checking http://localhost:8000 every ${INTERVAL}s"

while true; do
    if curl -sf http://localhost:8000 > /dev/null 2>&1; then
        if [ $failures -gt 0 ]; then
            echo "✅ $(date '+%Y-%m-%d %H:%M:%S') - UI recovered"
        fi
        failures=0
    else
        failures=$((failures + 1))
        echo "⚠️  $(date '+%Y-%m-%d %H:%M:%S') - UI check failed ($failures/$MAX_FAILURES)"
        
        if [ $failures -ge $MAX_FAILURES ]; then
            echo "🔄 $(date '+%Y-%m-%d %H:%M:%S') - Restarting Kong and Studio..."
            docker restart supabase-kong supabase-studio
            echo "⏳ Waiting 10s for recovery..."
            sleep 10
            failures=0
        fi
    fi
    
    sleep $INTERVAL
done
