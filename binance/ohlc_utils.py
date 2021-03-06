from binance.constants import BINANCE_GET_OHLC
from binance.error_handling import is_error

from data.candle import Candle

from utils.debug_utils import should_print_debug, print_to_console, LOG_ALL_DEBUG, ERROR_LOG_FILE_NAME
from utils.file_utils import log_to_file

from data_access.internet import send_request

from enums.status import STATUS


def get_ohlc_binance_url(currency, date_start, date_end, period):
    date_start_ms = 1000 * date_start
    # https://api.binance.com/api/v1/klines?symbol=XMRETH&interval=15m&startTime=
    final_url = BINANCE_GET_OHLC + currency + "&interval=" + period + "&startTime=" + str(date_start_ms)

    if should_print_debug():
        print_to_console(final_url, LOG_ALL_DEBUG)

    return final_url


def get_ohlc_binance_result_processor(json_response, currency, date_start, date_end):
    """
    [
        1499040000000,      // Open time
        "0.01634790",       // Open
        "0.80000000",       // High
        "0.01575800",       // Low
        "0.01577100",       // Close
        "148976.11427815",  // Volume
        1499644799999,      // Close time
        "2434.19055334",    // Quote asset volume
        308,                // Number of trades
        "1756.87402397",    // Taker buy base asset volume
        "28.46694368",      // Taker buy quote asset volume
        "17928899.62484339" // Can be ignored
    ]
    """
    result_set = []

    if is_error(json_response):
        msg = "get_ohlc_binance_result_processor - error response - {er}".format(er=json_response)
        log_to_file(msg, ERROR_LOG_FILE_NAME)

        return result_set

    for record in json_response:
        result_set.append(Candle.from_binance(record, currency))

    return result_set


def get_ohlc_binance(currency, date_start, date_end, period):
    result_set = []

    final_url = get_ohlc_binance_url(currency, date_start, date_end, period)

    err_msg = "get_ohlc_binance called for {pair} at {timest}".format(pair=currency, timest=date_start)
    error_code, json_responce = send_request(final_url, err_msg)

    if error_code == STATUS.SUCCESS:
        result_set = get_ohlc_binance_result_processor(json_responce, currency, date_start, date_end)

    return result_set
