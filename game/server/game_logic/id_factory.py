import hashlib
import json
from collections import defaultdict
from typing import Dict
from pydantic import BaseModel

class IDFactory:
    def __init__(self):
        self._scopes: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._counters: Dict[str, int] = defaultdict(int)
        self._known_hashes: Dict[str, Dict[str, int]] = defaultdict(dict)

    def get_id(self, obj: BaseModel, scope: str) -> int:
        # Генерируем хеш содержимого объекта
        content_hash = self._get_content_hash(obj)
        
        # Проверяем, видели ли мы этот хеш в текущем скоупе
        if content_hash in self._known_hashes[scope]:
            return self._known_hashes[scope][content_hash]
        
        # Генерируем новый ID
        new_id = self._counters[scope] + 1
        self._counters[scope] = new_id
        self._known_hashes[scope][content_hash] = new_id
        
        return new_id

    def _get_content_hash(self, obj: BaseModel) -> str:
        # Сериализуем объект, сортируя ключи для детерминированности
        dict_data = obj.model_dump()
        sorted_json = json.dumps(dict_data, sort_keys=True)
        return hashlib.md5(sorted_json.encode()).hexdigest()

    def get_object_hash(self, obj: BaseModel) -> str:
        return self._get_content_hash(obj)