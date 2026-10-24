# Динамический импорт: статический анализатор зависимостей rpm (python3.req)
# не должен видеть здесь внутренний модуль приложения как внешнюю зависимость.
import importlib
import sys

sys.exit(importlib.import_module("kachalka.app").main(sys.argv))
