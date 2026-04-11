from typing import Any, Dict
from core.s3 import S3Interface

class StateManager:
    def __init__(self, bucket_name: str, filename: str = "bot_state.json") -> None:
        self.filename: str = filename
        self.s3: S3Interface = S3Interface(bucket_name)
        self.state: Dict[str, Any] = self.s3.load_json(filename)

    def save(self) -> None:
        self.s3.save_json(self.filename, self.state)

    def get(self, coin: str, key: str, default: Any = 0) -> Any:
        return self.state.get(f"{coin}_{key}", default)

    def set(self, coin: str, key: str, value: Any) -> None:
        self.state[f"{coin}_{key}"] = value
        self.save()

    def clear(self, coin: str) -> None:
        for k in [k for k in self.state if k.startswith(f"{coin}_")]:
            del self.state[k]
        self.save()
