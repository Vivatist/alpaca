#!/usr/bin/env python3
"""
Запуск всех тестов file_watcher

Этот модуль запускает все тестовые модули:
- test_file_filter.py
- test_integration.py  
- test_sync_logic.py
"""
import os
import sys
from pathlib import Path

# Добавляем src/ и корень репозитория в PYTHONPATH
src_path = Path(__file__).parent.parent / "src"
repo_root = Path(__file__).resolve().parents[3]
for extra_path in (src_path, repo_root):
    if str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))


def run_all_tests() -> bool:
    """Запускает все тесты и возвращает True если все прошли успешно"""
    
    print("\n" + "="*70)
    print("ЗАПУСК ВСЕХ ТЕСТОВ FILE WATCHER")
    print("="*70)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL not set")
        return False
    
    total_passed = 0
    total_failed = 0
    test_modules = []
    
    # === TEST 1: File Filter Tests ===
    try:
        print("\n" + "─"*70)
        print("📦 TEST MODULE 1: File Filter")
        print("─"*70)
        
        from test_file_filter import TestFileFilter
        
        test_suite = TestFileFilter()
        success = test_suite.run_all_tests()
        
        if success:
            print("✅ File Filter Tests: PASSED")
            total_passed += 1
        else:
            print("❌ File Filter Tests: FAILED")
            total_failed += 1
            
        test_modules.append(("File Filter", success))
        
    except Exception as e:
        print(f"💥 ERROR loading File Filter tests: {e}")
        import traceback
        traceback.print_exc()
        total_failed += 1
        test_modules.append(("File Filter", False))
    
    # === TEST 2: Integration Tests ===
    try:
        print("\n" + "─"*70)
        print("📦 TEST MODULE 2: Integration Tests")
        print("─"*70)
        
        from test_integration import TestFileWatcher
        
        test_suite = TestFileWatcher()
        success = test_suite.run_all_tests()
        
        if success:
            print("✅ Integration Tests: PASSED")
            total_passed += 1
        else:
            print("❌ Integration Tests: FAILED")
            total_failed += 1
            
        test_modules.append(("Integration", success))
            
    except Exception as e:
        print(f"💥 ERROR loading Integration tests: {e}")
        import traceback
        traceback.print_exc()
        total_failed += 1
        test_modules.append(("Integration", False))
    
    # === TEST 3: Sync Logic Tests ===
    try:
        print("\n" + "─"*70)
        print("📦 TEST MODULE 3: Sync Logic Tests")
        print("─"*70)
        
        from test_sync_logic import TestSyncLogic
        from settings import settings
        
        test_suite = TestSyncLogic(database_url)
        
        try:
            success = test_suite.run_all_tests()
            
            if success:
                print("✅ Sync Logic Tests: PASSED")
                total_passed += 1
            else:
                print("❌ Sync Logic Tests: FAILED")
                total_failed += 1
                
            test_modules.append(("Sync Logic", success))
            
        finally:
            test_suite.cleanup()
            
    except Exception as e:
        print(f"💥 ERROR loading Sync Logic tests: {e}")
        total_failed += 1
        test_modules.append(("Sync Logic", False))
    
    # === SUMMARY ===
    print("\n" + "="*70)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*70)
    
    for module_name, success in test_modules:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{module_name:.<50} {status}")
    
    print("─"*70)
    print(f"Модулей пройдено: {total_passed}/{total_passed + total_failed}")
    print("="*70)
    
    return total_failed == 0


def main():
    """Точка входа"""
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
