#!/bin/bash
# =============================================================================
# ALPACA - Установка Ollama в Docker и загрузка моделей
# =============================================================================
# Этот скрипт запускает Ollama в Docker и загружает модели для ALPACA:
#   - bge-m3: модель эмбеддингов (1024 измерений)
#   - qwen2.5:32b: LLM для генерации ответов и извлечения метаданных
#
# Использование:
#   ./setup_ollama.sh           # Запустить Ollama в Docker + загрузить модели
#   ./setup_ollama.sh --models  # Только загрузить модели (контейнер уже запущен)
#   ./setup_ollama.sh --check   # Проверить установку
#   ./setup_ollama.sh --stop    # Остановить контейнер
#
# Требования:
#   - Docker и docker-compose
#   - Для GPU: NVIDIA драйверы и nvidia-container-toolkit
# =============================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Модели для ALPACA
EMBEDDING_MODEL="bge-m3"
CHAT_MODEL="qwen2.5:32b"

# Определяем путь к docker-compose.ollama.yml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.ollama.yml"

# Функции вывода
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# Проверка GPU
check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        info "Обнаружена NVIDIA GPU:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
        HAS_GPU=true
        
        # Проверка nvidia-container-toolkit
        if docker info 2>/dev/null | grep -q "nvidia"; then
            success "nvidia-container-toolkit настроен"
        else
            warning "nvidia-container-toolkit не обнаружен в Docker"
            info "Установите: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
        fi
    else
        warning "NVIDIA GPU не обнаружена. Ollama будет работать на CPU."
        HAS_GPU=false
    fi
}

# Проверка docker-compose файла
check_compose_file() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "Не найден $COMPOSE_FILE"
    fi
}

# Запуск Ollama в Docker
start_ollama() {
    info "Запуск Ollama в Docker..."
    
    check_compose_file
    
    # Проверяем, запущен ли уже контейнер
    if docker ps --format '{{.Names}}' | grep -q "alpaca-ollama"; then
        success "Ollama контейнер уже запущен"
        return 0
    fi
    
    docker compose -f "$COMPOSE_FILE" up -d
    
    info "Ожидание запуска Ollama..."
    
    # Проверка здоровья
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            success "Ollama запущена в Docker"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    echo ""
    
    error "Ollama не отвечает после 60 секунд. Проверьте логи: docker logs alpaca-ollama-ollama-1"
}

# Остановка Ollama
stop_ollama() {
    info "Остановка Ollama..."
    
    check_compose_file
    
    docker compose -f "$COMPOSE_FILE" down
    
    success "Ollama остановлена"
}

# Загрузка модели через Docker exec
pull_model() {
    local model=$1
    local description=$2
    
    info "Загрузка модели $model ($description)..."
    
    # Проверяем, есть ли уже модель
    local existing=$(docker exec alpaca-ollama-ollama-1 ollama list 2>/dev/null || echo "")
    if echo "$existing" | grep -q "$model"; then
        success "Модель $model уже загружена"
        return 0
    fi
    
    # Загружаем через docker exec
    if docker exec alpaca-ollama-ollama-1 ollama pull "$model"; then
        success "Модель $model загружена"
    else
        error "Не удалось загрузить модель $model"
    fi
}

# Загрузка всех моделей для ALPACA
pull_alpaca_models() {
    info "Загрузка моделей для ALPACA..."
    echo ""
    
    # Проверяем, что контейнер запущен
    if ! docker ps --format '{{.Names}}' | grep -q "alpaca-ollama"; then
        error "Ollama контейнер не запущен. Сначала выполните ./setup_ollama.sh"
    fi
    
    pull_model "$EMBEDDING_MODEL" "эмбеддинги, 1024 измерений"
    echo ""
    
    pull_model "$CHAT_MODEL" "LLM для чата и метаданных"
    echo ""
    
    success "Все модели загружены!"
    echo ""
    
    info "Список загруженных моделей:"
    docker exec alpaca-ollama-ollama-1 ollama list
}

# Проверка установки
verify_installation() {
    echo ""
    info "Проверка установки..."
    
    # Проверка контейнера
    if docker ps --format '{{.Names}}' | grep -q "alpaca-ollama"; then
        success "Ollama контейнер запущен"
    else
        warning "Ollama контейнер не запущен"
        return 1
    fi
    
    # Проверка API
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        error "Ollama API не отвечает на http://localhost:11434"
    fi
    success "Ollama API доступен"
    
    # Проверка моделей
    local models=$(docker exec alpaca-ollama-ollama-1 ollama list 2>/dev/null || echo "")
    
    if echo "$models" | grep -q "$EMBEDDING_MODEL"; then
        success "Модель эмбеддингов ($EMBEDDING_MODEL) доступна"
    else
        warning "Модель эмбеддингов ($EMBEDDING_MODEL) не найдена"
    fi
    
    if echo "$models" | grep -q "$CHAT_MODEL"; then
        success "LLM модель ($CHAT_MODEL) доступна"
    else
        warning "LLM модель ($CHAT_MODEL) не найдена"
    fi
    
    # Тест эмбеддингов
    info "Тест эмбеддингов..."
    local emb_response=$(curl -s http://localhost:11434/api/embeddings \
        -d "{\"model\": \"$EMBEDDING_MODEL\", \"prompt\": \"тест\"}" 2>/dev/null)
    
    if echo "$emb_response" | grep -q "embedding"; then
        local emb_size=$(echo "$emb_response" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['embedding']))" 2>/dev/null || echo "?")
        success "Эмбеддинги работают (размерность: $emb_size)"
    else
        warning "Не удалось получить эмбеддинги (модель возможно ещё не загружена)"
    fi
    
    echo ""
    success "Проверка завершена!"
    echo ""
    info "Для использования с ALPACA сервисами:"
    echo "  На этой машине:   OLLAMA_BASE_URL=http://host.docker.internal:11434"
    echo "  С другой машины:  OLLAMA_BASE_URL=http://$(hostname -I | awk '{print $1}'):11434"
}

# Показать справку
show_help() {
    echo "ALPACA - Установка Ollama в Docker"
    echo ""
    echo "Использование: $0 [ОПЦИЯ]"
    echo ""
    echo "Опции:"
    echo "  (без опций)   Запустить Ollama в Docker и загрузить модели"
    echo "  --models      Только загрузить модели (контейнер уже запущен)"
    echo "  --check       Проверить установку"
    echo "  --stop        Остановить контейнер Ollama"
    echo "  --help        Показать эту справку"
    echo ""
    echo "Модели для ALPACA:"
    echo "  - $EMBEDDING_MODEL: модель эмбеддингов (1024 измерений)"
    echo "  - $CHAT_MODEL: LLM для генерации ответов"
    echo ""
    echo "Файлы:"
    echo "  - $COMPOSE_FILE"
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    echo ""
    echo "🦙 ALPACA - Установка Ollama (Docker)"
    echo "======================================="
    echo ""
    
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --models)
            pull_alpaca_models
            verify_installation
            ;;
        --check)
            check_gpu
            verify_installation
            ;;
        --stop)
            stop_ollama
            ;;
        "")
            check_gpu
            start_ollama
            pull_alpaca_models
            verify_installation
            ;;
        *)
            error "Неизвестная опция: $1. Используйте --help для справки."
            ;;
    esac
}

main "$@"
