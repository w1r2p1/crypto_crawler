from debug_utils import print_to_console, LOG_ALL_MARKET_NETWORK_RELATED_CRAP, DEBUG_LOG_FILE_NAME

from utils.exchange_utils import get_exchange_name_by_id
from utils.currency_utils import get_pair_name_by_id
from utils.file_utils import log_to_file
from utils.string_utils import float_to_str

from data_access.message_queue import DEBUG_INFO_MSG

from constants import FIRST, LAST


def log_currency_disbalance_present(src_exchange_id, dst_exchange_id, currency_id, treshold_reverse):
    msg = "We have disbalance! Exchanges {exch1} {exch2} for {pair_id} with {thrs}".format(
        exch1=get_exchange_name_by_id(src_exchange_id),
        exch2=get_exchange_name_by_id(dst_exchange_id),
        pair_id=get_pair_name_by_id(currency_id),
        thrs=treshold_reverse
    )

    print_to_console(msg, LOG_ALL_MARKET_NETWORK_RELATED_CRAP)
    log_to_file(msg, "history_trades.log")


def log_currency_disbalance_heart_beat(src_exchange_id, dst_exchange_id, currency_id, treshold_reverse):
    msg = "No disbalance at Exchanges {exch1} {exch2} for {pair_id} with {thrs}".format(
        exch1=get_exchange_name_by_id(src_exchange_id),
        exch2=get_exchange_name_by_id(dst_exchange_id),
        pair_id=get_pair_name_by_id(currency_id),
        thrs=treshold_reverse
    )
    print_to_console(msg, LOG_ALL_MARKET_NETWORK_RELATED_CRAP)
    log_to_file(msg, DEBUG_LOG_FILE_NAME)


def log_arbitrage_hear_beat(sell_order_book, buy_order_book, difference):
    msg = """check_highest_bid_bigger_than_lowest_ask:
            For pair - {pair_name}
            Exchange1 - {exch1} BID = {bid}
            Exchange2 - {exch2} ASK = {ask}
            DIFF = {diff}""".format(
        pair_name=get_pair_name_by_id(sell_order_book.pair_id),
        exch1=get_exchange_name_by_id(sell_order_book.exchange_id),
        bid=float_to_str(sell_order_book.bid[FIRST].price),
        exch2=get_exchange_name_by_id(buy_order_book.exchange_id),
        ask=float_to_str(buy_order_book.ask[LAST].price),
        diff=difference)
    print_to_console(msg, LOG_ALL_MARKET_NETWORK_RELATED_CRAP)
    log_to_file(msg, DEBUG_LOG_FILE_NAME)


def log_arbitrage_determined_volume_not_enough(sell_order_book, buy_order_book, msg_queue):
    msg = """analyse order book - DETERMINED volume of deal is not ENOUGH {pair_name}:
    first_exchange: {first_exchange} first exchange volume: <b>{vol1}</b>
    second_exchange: {second_exchange} second_exchange_volume: <b>{vol2}</b>""".format(
        pair_name=get_pair_name_by_id(sell_order_book.pair_id),
        first_exchange=get_exchange_name_by_id(sell_order_book.exchange_id),
        second_exchange=get_exchange_name_by_id(buy_order_book.exchange_id),
        vol1=float_to_str(sell_order_book.bid[FIRST].volume),
        vol2=float_to_str(buy_order_book.ask[LAST].volume))
    print_to_console(msg, LOG_ALL_MARKET_NETWORK_RELATED_CRAP)
    log_to_file(msg, DEBUG_LOG_FILE_NAME)
    msg_queue.add_message(DEBUG_INFO_MSG, msg)