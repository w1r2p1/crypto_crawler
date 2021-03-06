import multiprocessing

from decimal import Decimal
from enums.currency import CURRENCY
from enums.currency_pair import CURRENCY_PAIR

#
#   Please note that routine below may trigger some trades
#               which may lead to money loss
#               Do NOT enable it without understanding of consequences
#
YES_I_KNOW_WHAT_AM_I_DOING = False


SECONDS_IN_WEEK = 604800
SECONDS_IN_DAY = 86400

HTTP_TIMEOUT_SECONDS = 25
HTTP_TIMEOUT_ORDER_BOOK_ARBITRAGE = 3
DEAL_MAX_TIMEOUT = 10

HTTP_SUCCESS = 200

ZERO_BALANCE = 0.0
ARBITRAGE_CURRENCY = CURRENCY.values()
ARBITRAGE_PAIRS = CURRENCY_PAIR.values()

BASE_CURRENCY = [CURRENCY.BITCOIN, CURRENCY.ETH, CURRENCY.USDT]

# FIXME NOTE read it from settings
BITCOIN_ALARM_THRESHOLD = 0.1
ETHERIUM_ALARM_THRESHOLD = 1.0
USDT_ALARM_THRESHOLD = 1000.0
BASE_CURRENCIES_BALANCE_THRESHOLD = {
    CURRENCY.BITCOIN: BITCOIN_ALARM_THRESHOLD,
    CURRENCY.ETH: ETHERIUM_ALARM_THRESHOLD,
    CURRENCY.USDT: USDT_ALARM_THRESHOLD
}

MIN_VOLUME_COEFFICIENT = {
    CURRENCY.BITCOIN: Decimal(0.004),
    CURRENCY.ETH: Decimal(0.04),
    CURRENCY.USDT: Decimal(40)
}

MAX_VOLUME_COEFFICIENT = Decimal(0.9)

CACHE_HOST = "0.0.0.0"
CACHE_PORT = 6379

CORE_NUM = multiprocessing.cpu_count()
POOL_SIZE = 8 * CORE_NUM

# FIXME NOTE: arbitrage_core
# This is indexes for comparison bid\ask within order books
# yeap, global constants is very bad
FIRST = 0
LAST = 0

NO_MAX_CAP_LIMIT = 0
NO_MIN_CAP_LIMIT = 0

DECIMAL_ZERO = Decimal(0.0)

START_OF_TIME = -1

FLOAT_POINT_PRECISION = Decimal("0.00000001")
MIN_VOLUME_ORDER_BOOK = 0.00001

API_KEY_PATH = "./secret_keys"

#
#   Hey, curious reader - don't worry too much about it - VMs are destroyed already :)
#

DB_HOST = "orders.cervsj06c8zw.us-west-1.rds.amazonaws.com"
DB_PORT = 5432
DB_NAME = "crypto"


#
#           Various timeout, in seconds
#

BALANCE_EXPIRED_THRESHOLD = 60
BALANCE_POLL_TIMEOUT = 3
BALANCE_HEALTH_CHECK_TIMEOUT = 180

ORDER_BOOK_POLL_TIMEOUT = 300

MIN_CAP_UPDATE_TIMEOUT = 900
BALANCE_UPDATE_TIMEOUT = 1
HEARTBEAT_TIMEOUT = 60
ORDER_EXPIRATION_TIMEOUT = 15
