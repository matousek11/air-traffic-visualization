from abc import ABC

from tensorboard.data.provider import DataProvider

class BlueskyDataProvider(DataProvider, ABC):
    def __init__(self):
        pass