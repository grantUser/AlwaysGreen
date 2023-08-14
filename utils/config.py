import utils.yaml as yaml
from utils.singleton import Singleton


class Config(metaclass=Singleton):
    def __init__(self) -> None:
        self.yaml = yaml.read(".env")

    def get(self, key: str, default=False) -> str | bool:
        return self.yaml.get(key, default)


config = Config()
