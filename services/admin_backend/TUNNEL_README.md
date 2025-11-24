# SSH Tunnel Configuration

## Схема соединения

```
Локальный компьютер          →  SSH туннель (port 2222)  →    Удаленный сервер (95.217.205.233)
localhost:22                 →  autossh -p 2222          →    0.0.0.0:2223
localhost:8080               →  autossh -p 2222          →    0.0.0.0:8080
                                                               ↓
                                                               nginx :8443 → localhost:8080
                                                               ↓
                                                               https://api.alpaca-smart.com:8443
```

**Примечание:** Подключение к удаленному серверу идет через порт **2222** (SSH сервер на удаленной машине), а не стандартный 22.

## Текущие туннели

| Локальный порт | Удаленный порт | Назначение |
|----------------|----------------|------------|
| 22             | 2223           | SSH доступ к локальному компьютеру |
| 8080           | 8080           | Admin Backend API |

## Управление туннелями

### Добавить новый порт

1. Редактируем systemd сервис:
```bash
sudo nano /etc/systemd/system/autossh-tunnel.service
```

2. Добавляем строку с портом в секцию `ExecStart`:
```
-R 0.0.0.0:<remote_port>:localhost:<local_port> \
```

3. Применяем изменения:
```bash
sudo systemctl daemon-reload
sudo systemctl restart autossh-tunnel.service
```

### Удалить порт

1. Удаляем строку с портом из `/etc/systemd/system/autossh-tunnel.service`
2. Перезапускаем:
```bash
sudo systemctl daemon-reload
sudo systemctl restart autossh-tunnel.service
```

## Проверка

### Статус сервиса
```bash
sudo systemctl status autossh-tunnel.service
```

### Активные туннели (локально)
```bash
ps aux | grep autossh
```

### Порты на удаленном сервере
```bash
ssh -p 2222 root@95.217.205.233 "ss -tlnp | grep -E ':2223|:8080'"
```

### Проверка API
```bash
curl -s https://api.alpaca-smart.com:8443/ | jq
```

## Troubleshooting

### Туннель не работает
```bash
sudo journalctl -u autossh-tunnel.service -f
```

### Перезапустить туннель
```bash
sudo systemctl restart autossh-tunnel.service
```

### Проверить доступность удаленного сервера
```bash
ping -c 3 95.217.205.233
ssh -p 2222 root@95.217.205.233 "uptime"
```
