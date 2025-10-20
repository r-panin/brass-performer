import time
import json
from copy import deepcopy
from game.server.game_logic.game import Game
from game.schema import PlayerColor
from game.server.game_logic.services.fast_copy import CopyEngine
from pathlib import Path

def compare_objects(obj1, obj2, path="root"):
    """
    Рекурсивно сравнивает два объекта, включая все вложенные структуры
    """
    # Сравнение типов
    if type(obj1) != type(obj2):
        print(f"Разные типы в {path}: {type(obj1)} vs {type(obj2)}")
        return False
    
    # Для Pydantic моделей сравниваем через model_dump()
    if hasattr(obj1, 'model_dump') and hasattr(obj2, 'model_dump'):
        dict1 = obj1.model_dump()
        dict2 = obj2.model_dump()
        if dict1 != dict2:
            print(f"Разные данные Pydantic модели в {path}")
            print(f"Оригинал: {dict1}")
            print(f"Копия: {dict2}")
            return False
        return True
    
    # Для списков
    elif isinstance(obj1, list):
        if len(obj1) != len(obj2):
            print(f"Разная длина списков в {path}: {len(obj1)} vs {len(obj2)}")
            return False
        
        for i, (item1, item2) in enumerate(zip(obj1, obj2)):
            if not compare_objects(item1, item2, f"{path}[{i}]"):
                return False
        return True
    
    # Для словарей
    elif isinstance(obj1, dict):
        if set(obj1.keys()) != set(obj2.keys()):
            print(f"Разные ключи в словаре {path}: {set(obj1.keys())} vs {set(obj2.keys())}")
            return False
        
        for key in obj1:
            if not compare_objects(obj1[key], obj2[key], f"{path}.{key}"):
                return False
        return True
    
    # Для простых типов
    else:
        if obj1 != obj2:
            print(f"Разные значения в {path}: {obj1} vs {obj2}")
            return False
        return True

def benchmark_copy(engine, state, num_iterations=1000):
    """Замеряет производительность разных методов копирования"""
    
    # Тестируем fast_copy
    print(f"Тестируем fast_copy ({num_iterations} итераций)...")
    start_time = time.perf_counter()
    for i in range(num_iterations):
        copy = engine.fast_copy(state)
    fast_copy_time = time.perf_counter() - start_time
    
    # Тестируем стандартный deepcopy
    print(f"Тестируем deepcopy ({num_iterations} итераций)...")
    start_time = time.perf_counter()
    for i in range(num_iterations):
        copy = deepcopy(state)
    deepcopy_time = time.perf_counter() - start_time
    
    return fast_copy_time, deepcopy_time

def main():
    engine = CopyEngine()
    game = Game()
    colors = list(PlayerColor)
    game.start(4, colors) 
    state = game.get_player_state(game.state_service.get_active_player().color)
    
    print("=== Тестирование корректности копирования ===")
    
    # Тестируем fast_copy
    state_fast_copy = engine.fast_copy(state)
    print("fast_copy корректность:", compare_objects(state, state_fast_copy))
    
    # Тестируем deepcopy для сравнения
    state_deepcopy = deepcopy(state)
    print("deepcopy корректность:", compare_objects(state, state_deepcopy))
    
    # Сравниваем JSON вывод
    original_json = state.model_dump_json()
    fast_copy_json = state_fast_copy.model_dump_json()
    deepcopy_json = state_deepcopy.model_dump_json()
    
    print("JSON оригинал == JSON fast_copy:", original_json == fast_copy_json)
    print("JSON оригинал == JSON deepcopy:", original_json == deepcopy_json)
    
    # Сохраняем в файлы для визуальной проверки
    with open(Path(__file__).resolve().parent / 'starting_state.json', 'w') as outfile:
        outfile.write(original_json)
    
    with open(Path(__file__).resolve().parent / 'copied_state_fast.json', 'w') as outfile:
        outfile.write(fast_copy_json)
    
    with open(Path(__file__).resolve().parent / 'copied_state_deepcopy.json', 'w') as outfile:
        outfile.write(deepcopy_json)
    
    print("\n=== Бенчмарк производительности ===")
    
    # Замер производительности
    num_iterations = 1000
    fast_time, deepcopy_time = benchmark_copy(engine, state, num_iterations)
    
    print(f"\nРезультаты производительности ({num_iterations} итераций):")
    print(f"fast_copy: {fast_time:.4f} секунд")
    print(f"deepcopy: {deepcopy_time:.4f} секунд")
    
    if fast_time > 0:
        speedup = deepcopy_time / fast_time
        print(f"Ускорение: {speedup:.2f}x")
        
        if speedup > 1:
            print(f"fast_copy быстрее в {speedup:.2f} раз")
        else:
            print(f"deepcopy быстрее в {1/speedup:.2f} раз")
    
    # Дополнительная проверка: убеждаемся, что копии действительно независимы
    print("\n=== Тестирование независимости копий ===")
    
    # Изменяем что-то в копии и проверяем, что оригинал не изменился
    original_color = state_fast_copy.your_color
    # Временно изменяем цвет в копии
    state_fast_copy.your_color = "MODIFIED_COLOR"
    
    # Проверяем, что оригинал не изменился
    if state.your_color != "MODIFIED_COLOR":
        print("✓ Копия независима от оригинала (fast_copy)")
    else:
        print("✗ Копия разделяет ссылки с оригиналом!")
    
    # Восстанавливаем оригинальное значение
    state_fast_copy.your_color = original_color

if __name__ == '__main__':
    main()