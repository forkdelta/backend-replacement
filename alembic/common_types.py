from enum import Enum
from sqlalchemy import LargeBinary, Numeric
from sqlalchemy.dialects.postgresql import UUID

UINT256_DIGITS = 78
SA_TYPE_ADDR = LargeBinary(20)
SA_TYPE_TXHASH = LargeBinary(32)
SA_TYPE_SIG = LargeBinary(32)
SA_TYPE_VALUE = Numeric(precision=UINT256_DIGITS, scale=0)

class TransferType(Enum):
    DEPOSIT = 0
    WITHDRAW = 1

class OrderSource(Enum):
    ONCHAIN = 0
    OFFCHAIN = 1

class OrderState(Enum):
    OPEN = 0
    FILLED = 1
    CANCELED = 2
