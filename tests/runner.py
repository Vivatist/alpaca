"""
Утилита для запуска тестов программно
"""
import sys
import pytest
from pathlib import Path
from typing import Optional, List

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging import get_logger

logger = get_logger("alpaca.tests")


def run_tests(
    suite: str = "unit",
    verbose: bool = True,
    stop_on_failure: bool = False
) -> bool:
    """Запустить тесты программно
    
    Args:
        suite: Тип тестов для запуска
            - "unit": только unit-тесты (chunker, parser, embedder)
            - "integration": интеграционные тесты
            - "all": все тесты
        verbose: Подробный вывод
        stop_on_failure: Остановиться при первой ошибке
        
    Returns:
        bool: True если все тесты прошли успешно
    """
    tests_dir = Path(__file__).parent
    
    # Определяем какие тесты запускать
    test_files: List[str] = []
    
    if suite == "unit":
        test_files = [
            str(tests_dir / "test_chunker.py"),
            str(tests_dir / "test_parser.py"),
            str(tests_dir / "test_embedder.py"),
        ]
        print("🧪 Запуск unit-тестов...")
    elif suite == "integration":
        test_files = [
            str(tests_dir / "test_worker_integration.py"),
            str(tests_dir / "test_worker_pipeline.py"),
        ]
        print("🧪 Запуск интеграционных тестов...")
    elif suite == "all":
        test_files = [str(tests_dir)]
        print("🧪 Запуск всех тестов...")
    else:
        print(f"❌ Неизвестный тип тестов: {suite}")
        return False
    
    # Формируем аргументы для pytest
    args = test_files.copy()
    
    if verbose:
        args.append("-v")
    else:
        args.append("-q")
    
    if stop_on_failure:
        args.append("-x")
    
    # Запускаем pytest
    try:
        exit_code = pytest.main(args)
        
        if exit_code == 0:
            print("✅ Все тесты пройдены успешно!")
            return True
        else:
            print(f"❌ Тесты завершились с кодом {exit_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при запуске тестов: {e}")
        return False


def run_tests_on_startup(settings) -> bool:
    """Запустить тесты при старте приложения (если включено в настройках)
    
    Args:
        settings: Объект настроек приложения
        
    Returns:
        bool: True если тесты прошли или отключены, False если тесты провалились
    """
    if not settings.RUN_TESTS_ON_START:
        return True
    
    print("=" * 60)
    print("RUN_TESTS_ON_START=True - Запуск тестов перед стартом...")
    print("=" * 60)
    
    success = run_tests(
        suite=settings.TEST_SUITE,
        verbose=True,
        stop_on_failure=False
    )
    
    if not success:
        print("=" * 60)
        print("ВНИМАНИЕ: Тесты провалились!")
        print("Для продолжения работы установите RUN_TESTS_ON_START=False")
        print("=" * 60)
    else:
        print("=" * 60)
        print("Тесты пройдены успешно - продолжаем запуск приложения")
        print("=" * 60)
    
    return success


if __name__ == "__main__":
    """Запуск тестов из командной строки"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Запуск тестов ALPACA")
    parser.add_argument(
        "--suite",
        choices=["unit", "integration", "all"],
        default="unit",
        help="Тип тестов для запуска"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод"
    )
    parser.add_argument(
        "--stop-on-failure", "-x",
        action="store_true",
        help="Остановиться при первой ошибке"
    )
    
    args = parser.parse_args()
    
    success = run_tests(
        suite=args.suite,
        verbose=args.verbose,
        stop_on_failure=args.stop_on_failure
    )
    
    sys.exit(0 if success else 1)
