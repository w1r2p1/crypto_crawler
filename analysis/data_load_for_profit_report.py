from enums.exchange import EXCHANGE
from binance.constants import BINANCE_CURRENCY_PAIRS
from binance.market_utils import get_trades_history_binance
from binance.currency_utils import get_currency_pair_to_binance

from poloniex.order_history import get_order_history_poloniex
from bittrex.order_history import get_order_history_bittrex
from binance.order_history import get_order_history_binance

from poloniex.currency_utils import get_currency_pair_from_poloniex, get_currency_pair_to_poloniex
from binance.currency_utils import get_currency_pair_from_binance
from bittrex.currency_utils import get_currency_pair_to_bittrex

from utils.key_utils import get_key_by_exchange
from utils.time_utils import sleep_for
from utils.currency_utils import CURRENCY_PAIR

from data.Trade import Trade
from dao.db import save_order_into_pg, is_order_present_in_order_history, get_last_binance_trade, \
    is_trade_present_in_trade_history

from collections import defaultdict
from constants import START_OF_TIME

from enums.status import STATUS

from tqdm import tqdm


def fetch_trades_history_to_db(pg_conn, start_time, end_time):
    load_recent_binance_orders_to_db(pg_conn, start_time)
    load_recent_binance_trades_to_db(pg_conn, start_time, end_time)
    load_recent_poloniex_trades_to_db(pg_conn, start_time)
    load_recent_bittrex_trades_to_db(pg_conn, start_time)


def wrap_with_progress_bar(descr, input_array, functor, *args, **kwargs):
    for entry in tqdm(input_array, desc=descr):
        functor(entry, *args, **kwargs)


def get_recent_binance_orders():
    key = get_key_by_exchange(EXCHANGE.BINANCE)

    binance_order = []
    limit = 500
    for pair_name in BINANCE_CURRENCY_PAIRS:

        err_code, orders_by_pair = get_order_history_binance(key, pair_name, limit)

        print "Get data for ", pair_name
        while err_code == STATUS.FAILURE:
            sleep_for(2)
            err_code, orders_by_pair = get_order_history_binance(key, pair_name, limit)

        binance_order += orders_by_pair
        sleep_for(1)

    return binance_order


def save_to_pg_adapter(order, pg_conn, unique_only, unique_predicate, table_name, init_arbitrage_id):

    order.arbitrage_id = init_arbitrage_id
    if unique_only:
        if unique_predicate(pg_conn, order, table_name):
            return

    save_order_into_pg(order, pg_conn, table_name)


def load_recent_binance_orders_to_db(pg_conn, start_time, unique_only=True):
    binance_orders = get_recent_binance_orders()

    binance_orders = [x for x in binance_orders if x.create_time >= start_time]

    wrap_with_progress_bar("Loading recent binance orders to db...", binance_orders, save_to_pg_adapter, pg_conn,
                           unique_only, is_order_present_in_order_history, init_arbitrage_id=-10,
                           table_name="binance_order_history")


def receive_binance_trade_batch(key, pair_name, limit, last_order_id):
    trades_by_pair = []

    error_code, json_document = get_trades_history_binance(key, pair_name, limit, last_order_id)

    while error_code != STATUS.SUCCESS:
        print "receive_trade_batch: got error responce - Reprocessing"
        sleep_for(2)
        error_code, trades = get_trades_history_binance(key, pair_name, limit, last_order_id)

    for entry in json_document:
        trades_by_pair.append(Trade.from_binance_history(entry, pair_name))

    return trades_by_pair


def get_recent_binance_trades(pg_conn, start_time, end_time):

    # 1 get the most recent trade_id from db for that date
    last_trade = get_last_binance_trade(pg_conn, start_time, table_name="arbitrage_trades")

    # 2 sequentially query binance

    key = get_key_by_exchange(EXCHANGE.BINANCE)

    last_order_id = last_trade.deal_id if last_trade is not None else 0

    print "last_order_id: ", last_order_id

    limit = 200

    binance_trades_by_pair = {}
    for pair_name in BINANCE_CURRENCY_PAIRS:
        trades_by_pair = []

        pair_id = get_currency_pair_from_binance(pair_name)

        while True:
            recent_trades = receive_binance_trade_batch(key, pair_name, limit, last_order_id)

            if len(recent_trades) == 0:
                break

            # Biggest = Latest - will be first
            recent_trades.sort(key=lambda x: long(x.deal_id), reverse=True)
            trades_by_pair += recent_trades

            if len(recent_trades) < limit:
                break

            if end_time >= recent_trades[0].create_time:

                prev_order_id = last_order_id
                last_order_id = recent_trades[0].deal_id

                if prev_order_id != 0 and prev_order_id == last_order_id:
                    recent_trades.sort(key=lambda x: long(x.deal_id), reverse=False)
                    print "Max", recent_trades[-1:][0].deal_id
                    print "Min", recent_trades[:-1][0].deal_id
                    print "Last order"
                    print recent_trades[:-1][0]

                    print len(trades_by_pair)

                    assert False
            else:
                break

        binance_trades_by_pair[pair_id] = trades_by_pair

    return binance_trades_by_pair


def load_recent_binance_trades_to_db(pg_conn, start_time, end_time, unique_only=True):
    binance_trades_by_pair = get_recent_binance_trades(pg_conn, start_time, end_time)

    for pair_id in binance_trades_by_pair:
        headline = "Loading recent binance trades - {p}".format(p=get_currency_pair_to_binance(pair_id))
        wrap_with_progress_bar(headline, binance_trades_by_pair[pair_id], save_to_pg_adapter, pg_conn,
                               unique_only, is_trade_present_in_trade_history,
                               init_arbitrage_id=-20, table_name="arbitrage_trades")


def get_recent_poloniex_trades(start_time=START_OF_TIME):

    key = get_key_by_exchange(EXCHANGE.POLONIEX)
    error_code, trades = get_order_history_poloniex(key, pair_name='all', time_start=start_time)
    while error_code != STATUS.SUCCESS:
        print "get_recent_poloniex_trades: got error responce - Reprocessing"
        sleep_for(2)
        error_code, trades = get_order_history_poloniex(key, pair_name='all', time_start=start_time)

    poloniex_orders_by_pair = defaultdict(list)
    for trade in trades:
        if trade.create_time >= start_time:
            poloniex_orders_by_pair[trade.pair_id].append(trade)

    return poloniex_orders_by_pair


def load_recent_poloniex_trades_to_db(pg_conn, start_time, unique_only=True):
    poloniex_orders_by_pair = get_recent_poloniex_trades(start_time)

    for pair_id in poloniex_orders_by_pair:
        headline = "Loading poloniex trades - {p}".format(p=get_currency_pair_to_poloniex(pair_id))
        wrap_with_progress_bar(headline, poloniex_orders_by_pair[pair_id], save_to_pg_adapter, pg_conn,
                               unique_only, is_trade_present_in_trade_history,
                               init_arbitrage_id=-20, table_name="arbitrage_trades")


def get_recent_bittrex_trades(start_time=START_OF_TIME):
    key = get_key_by_exchange(EXCHANGE.BITTREX)
    err_code, trades = get_order_history_bittrex(key, pair_name='all')

    while err_code == STATUS.FAILURE:
        print "get_recent_bittrex_trades: got error responce - Reprocessing"
        sleep_for(2)
        err_code, trades = get_order_history_bittrex(key, pair_name='all')

    bittrex_order_by_pair = defaultdict(list)
    for new_trade in trades:
        if new_trade.create_time >= start_time:
            bittrex_order_by_pair[new_trade.pair_id].append(new_trade)

    return bittrex_order_by_pair


def load_recent_bittrex_trades_to_db(pg_conn, start_time, unique_only=True):
    bittrex_order_by_pair = get_recent_bittrex_trades(start_time)

    for pair_id in bittrex_order_by_pair:
        headline = "Loading bittrex trades - {p}".format(p=get_currency_pair_to_bittrex(pair_id))
        wrap_with_progress_bar(headline, bittrex_order_by_pair[pair_id], save_to_pg_adapter, pg_conn,
                               unique_only, is_trade_present_in_trade_history,
                               init_arbitrage_id=-20, table_name="arbitrage_trades")
