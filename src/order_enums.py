from enum import Enum

class OrderSource(Enum):
    ONCHAIN = 0
    OFFCHAIN = 1

class OrderState(Enum):
    OPEN = 0
    FILLED = 1
    CANCELED = 2
