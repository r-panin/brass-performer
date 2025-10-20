from copy import deepcopy
cimport cython

cdef class CopyEngine:
    
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cpdef fast_copy(self, obj):
        cdef type obj_type = type(obj)
        
        # Специализированные копии для наиболее частых случаев
        if hasattr(obj_type, 'model_fields'):
            return self._copy_pydantic_hybrid(obj)
        else:
            return deepcopy(obj)
    
    cdef _copy_pydantic_hybrid(self, obj):
        """Гибридный подход для Pydantic: shallow copy + selective deep copy"""
        cdef type obj_type = type(obj)
        cdef dict model_data = obj.model_dump()
        cdef dict processed_data = {}
        cdef object key, value
        
        for key, value in model_data.items():
            # Определяем, нужно ли глубокое копирование для этого поля
            if self._needs_deep_copy(value):
                processed_data[key] = deepcopy(value)
            else:
                processed_data[key] = value
        
        return obj_type(**processed_data)
    
    cdef _needs_deep_copy(self, obj):
        """Определяет, требует ли объект глубокого копирования"""
        if obj is None:
            return False
            
        cdef type obj_type = type(obj)
        
        # Примитивные типы - не требуют deepcopy
        if obj_type in (int, float, str, bool):
            return False
            
        # Списки и словари могут требовать deepcopy
        if obj_type in (list, dict):
            return True
            
        # Другие изменяемые типы
        if hasattr(obj, '__dict__') or hasattr(obj, '__slots__'):
            return True
            
        return False