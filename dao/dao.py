from utils.time_utils import get_now_seconds

#
#       FIXME NOTE
#
#   Reconsider imports below
#

from bittrex.constants import BITTREX_CURRENCIES
from kraken.constants import KRAKEN_CURRENCIES
from poloniex.constants import POLONIEX_CURRENCIES

from bittrex.ticker_utils import get_ticker_bittrex
from kraken.ticker_utils import get_ticker_kraken
from poloniex.ticker_utils import get_ticker_poloniex

from bittrex.ohlc_utils import get_ohlc_bittrex
from kraken.ohlc_utils import get_ohlc_kraken
from poloniex.ohlc_utils import get_ohlc_poloniex

from bittrex.order_book_utils import get_order_book_bittrex
from kraken.order_book_utils import get_order_book_kraken
from poloniex.order_book_utils import get_order_book_poloniex

from bittrex.history_utils import get_history_bittrex
from kraken.history_utils import get_history_kraken
from poloniex.history_utils import get_history_poloniex

from bittrex.market_utils import add_buy_order_bittrex, add_sell_order_bittrex, cancel_order_bittrex, show_balance_bittrex
from kraken.market_utils import add_buy_order_kraken, add_sell_order_kraken, cancel_order_kraken, show_balance_kraken
from poloniex.market_utils import add_buy_order_poloniex, add_sell_order_poloniex, cancel_order_poloniex, show_balance_poloniex

from constants import POLONIEX_EXCHANGE, KRAKEN_EXCHANGE, BITTREX_EXCHANGE

from enums.exchange import EXCHANGE
from utils.key_utils import get_key_by_exchange

from collections import defaultdict


def get_ticker():

    timest = get_now_seconds()

    bittrex_tickers = {}
    for currency in BITTREX_CURRENCIES:
        ticker = get_ticker_bittrex(currency, timest)
        if ticker is not None:
            bittrex_tickers[ticker.pair_id] = ticker

    kraken_tickers = {}
    for currency in KRAKEN_CURRENCIES:
        ticker = get_ticker_kraken(currency, timest)
        if ticker is not None:
            kraken_tickers[ticker.pair_id] = ticker

    poloniex_tickers = {}
    for currency in POLONIEX_CURRENCIES:
        ticker = get_ticker_poloniex(currency, timest)
        if ticker is not None:
            poloniex_tickers[ticker.pair_id] = ticker

    return bittrex_tickers, kraken_tickers, poloniex_tickers


def get_ohlc():
    all_ohlc = []

    date_end = get_now_seconds()
    date_start = date_end

    for currency in BITTREX_CURRENCIES:
        period = "thirtyMin"
        all_ohlc += get_ohlc_bittrex(currency, date_end, date_start, period)

    for currency in KRAKEN_CURRENCIES:
        period = 15
        all_ohlc += get_ohlc_kraken(currency, date_end, date_start, period)

    for currency in POLONIEX_CURRENCIES:
        period = 14400
        all_ohlc += get_ohlc_poloniex(currency, date_end, date_start, period)

    return all_ohlc


def get_order_book():
    
    all_order_book = defaultdict(list)

    timest = get_now_seconds()

    for currency in POLONIEX_CURRENCIES:
        order_book = get_order_book_poloniex(currency, timest)
        if order_book is not None:
            all_order_book[POLONIEX_EXCHANGE] = order_book

    for currency in KRAKEN_CURRENCIES:
        order_book = get_order_book_kraken(currency, timest)
        if order_book is not None:
            all_order_book[KRAKEN_EXCHANGE] = order_book

    for currency in BITTREX_CURRENCIES:
        order_book = get_order_book_bittrex(currency, timest)
        if order_book is not None:
            all_order_book[BITTREX_EXCHANGE] = order_book

    return all_order_book


def get_history(prev_time, now_time):
    all_history = []

    for currency in POLONIEX_CURRENCIES:
        all_history += get_history_poloniex(currency, prev_time, now_time)

    for currency in KRAKEN_CURRENCIES:
        all_history += get_history_kraken(currency, prev_time, now_time)

    for currency in BITTREX_CURRENCIES:
        all_history += get_history_bittrex(currency, prev_time, now_time)

    return all_history


# FIXME currency_utils opposite method to convert pair_id to exchange specific strings
# FIXME 2 exchange as ENUMS not strings for key utils

def buy_by_exchange(trade):
    key = get_key_by_exchange(trade.exchange_id)
    if trade.exchange_id == EXCHANGE.BITTREX:
        add_buy_order_bittrex(key, trade.pair_id, trade.price, trade.volume)
    elif trade.exchange_id == EXCHANGE.KRAKEN:
        add_buy_order_kraken(key, trade.pair_id, trade.price, trade.volume)
    elif trade.exchange_id == EXCHANGE.BITTREX:
        add_buy_order_poloniex(key, trade.pair_id, trade.price, trade.volume)
    else:
        print "buy_by_exchange - Unknown exchange! ", trade


def sell_by_exchange(trade):
    key = get_key_by_exchange(trade.exchange_id)
    if trade.exchange_id == EXCHANGE.BITTREX:
        add_sell_order_bittrex(key, trade.pair_id, trade.price, trade.volume)
    elif trade.exchange_id == EXCHANGE.KRAKEN:
        add_sell_order_kraken(key, trade.pair_id, trade.price, trade.volume)
    elif trade.exchange_id == EXCHANGE.BITTREX:
        add_sell_order_poloniex(key, trade.pair_id, trade.price, trade.volume)
    else:
        print "sell_by_exchange - Unknown exchange! ", trade


def cancel_by_exchange(trade):
    # FIXME
    pass

def show_balance_by_exchange():
    # FIXME
    pass