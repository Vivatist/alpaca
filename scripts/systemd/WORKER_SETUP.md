# Alpaca Worker Setup

## Установка systemd сервиса

```bash
# Копирование сервис-файла
sudo cp /home/alpaca/alpaca/systemd/alpaca-worker.service /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable alpaca-worker

# Запуск сервиса
sudo systemctl start alpaca-worker

# Проверка статуса
sudo systemctl status alpaca-worker

# Просмотр логов
sudo journalctl -u alpaca-worker -f
```

## Ручной запуск (для разработки)

```bash
cd /home/alpaca/alpaca
source venv/bin/activate
python main.py
```

## Переменные окружения

- `FILEWATCHER_API_URL` - URL API file watcher (по умолчанию: http://localhost:8081)

## Архитектура

```
┌─────────────────┐
│  File Watcher   │  ← Сканирует папку, обновляет БД
│  (Scanner+API)  │     Предоставляет GET /api/next-file
└────────┬────────┘
         │
         ↓
    ┌────────┐
    │   DB   │  ← PostgreSQL с очередью файлов
    └────┬───┘
         ↑
         │
┌────────┴────────┐
│     Worker      │  ← Берет файлы из очереди
│  (этот сервис)  │     Обрабатывает: парсинг → чанкинг → эмбеддинг
└─────────────────┘
```

## Обработка файлов

Worker обрабатывает файлы по приоритету:
1. **deleted** - удаляет чанки и запись из БД
2. **updated** - удаляет старые чанки, обрабатывает заново
3. **added** - парсит, чанкует, создает эмбеддинги

## Масштабирование

Можно запустить несколько worker'ов параллельно:

```bash
# Terminal 1
python main.py

# Terminal 2  
python main.py

# Terminal 3
python main.py
```

Каждый worker будет брать следующий файл из очереди независимо.
