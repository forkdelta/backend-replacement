HTTP_PROVIDER_URL = 'http://159.203.19.200:8545/'
WS_PROVIDER_URL = 'ws://159.203.19.200:8546/'

ED_CONTRACT_ADDR = '0x8d12a197cb00d4747a1fe03395095ce2a5cc6819'
with open('etherdelta.abi.json') as f:
    import json
    ED_CONTRACT_ABI = json.load(f)

from os import environ
POSTGRES_HOST = "postgres"
POSTGRES_DB = environ.get("POSTGRES_DB")
POSTGRES_USER = environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = environ.get("POSTGRES_PASSWORD")
