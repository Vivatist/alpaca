"""Основной модуль worker с совместимостью старого API."""

from utils.logging import setup_logging, get_logger
from settings import settings
from core.domain.files.models import FileSnapshot
from tests.runner import run_tests_on_startup
from core.application.files import ResetStuckFiles
from core.application.bootstrap import build_worker_application

logger = get_logger("core.worker")

bootstrap_app = build_worker_application(settings)

word_parser = bootstrap_app.word_parser
ingest_document = bootstrap_app.ingest_document
process_file_use_case = bootstrap_app.process_file_event
chunking = bootstrap_app.chunker
worker = bootstrap_app.worker
db = bootstrap_app.repository


def ingest_pipeline(file: FileSnapshot) -> bool:
    """Backward-compatible entry point для тестов и скриптов."""
    return ingest_document(file)




if __name__ == "__main__":
    # Запуск тестов при старте (если включено в настройках)
    tests_passed = run_tests_on_startup(settings)

    if not tests_passed:
        exit(1)

    # Переинициализируем logging после тестов (pytest может закрыть handlers)
    setup_logging()
    logger.info("🚀 Запуск worker после успешного прохождения тестов")

    # Сбрасываем зависшие 'processed' статусы на 'added' при старте
    try:
        reset_use_case = ResetStuckFiles(db)
        reset_count = reset_use_case()
        if reset_count > 0:
            logger.info(f"🔄 Reset {reset_count} stuck 'processed' files to 'added' on startup")
    except Exception as e:
        logger.error(f"Failed to reset processed statuses: {e}")

    # Создаём worker и запускаем
    worker.start(
        poll_interval=settings.WORKER_POLL_INTERVAL,
        max_workers=settings.WORKER_MAX_CONCURRENT_FILES,
    )

