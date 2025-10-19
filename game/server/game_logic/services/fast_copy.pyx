from copy import deepcopy
cimport cython

cdef class CopyEngine
    @cython.boundscheck(False)
    @cython.wraparound(False)
    cpdef fast_copy(self, obj):
        if self._is_dataclass_instance(obj):
            return self._copy_dataclass(obj)
        elif isinstance(obj, list):
            return self._copy_list(obj)
        elif isinstance(obj, dict):
            return self._copy_dict(obj)
        else:
            return deepcopy(obj)  # fallback
    
    cdef _copy_list(self, list original):
        cdef list new_list = []
        cdef object item
        for item in original:
            new_list.append(self.optimized_deepcopy(item))
        return new_list
    
    cdef _copy_dict(self, dict original):
        cdef dict new_dict = {}
        cdef object key, value
        for key, value in original.items():
            new_dict[key] = self.optimized_deepcopy(value)
        return new_dict
    
    cdef _is_dataclass_instance(self, obj):
        return hasattr(obj, '__dataclass_fields__')
    
    cdef _copy_dataclass(self, obj):
        new_obj = type(obj)()
        
        cdef object field_name
        for field_name in obj.__dataclass_fields__:
            original_value = getattr(obj, field_name)
            copied_value = self.optimized_deepcopy(original_value)
            setattr(new_obj, field_name, copied_value)
        
        return new_obj