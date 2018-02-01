from collections import defaultdict

from data.OrderBook import OrderBook, ORDER_BOOK_INSERT_BIDS, ORDER_BOOK_INSERT_ASKS, ORDER_BOOK_TYPE_NAME
from data.Trade import Trade
from data.Candle import Candle

from data_access.postgres_connection import PostgresConnection
from utils.time_utils import get_date_time_from_epoch
from utils.file_utils import log_to_file

from debug_utils import print_to_console, LOG_ALL_ERRORS, ERROR_LOG_FILE_NAME
from constants import START_OF_TIME


def init_pg_connection(_db_host="192.168.1.106", _db_port=5432, _db_name="postgres"):
    # FIXME NOTE hardcoding is baaad Dmitry! pass some config
    pg_conn = PostgresConnection(db_host=_db_host, db_port=_db_port, db_name=_db_name, db_user="postgres",
                                 db_password="postgres")
    pg_conn.connect()
    return pg_conn


def insert_data(some_object, pg_conn, dummy_flag):
    # NOTE commit should be after all inserts! ONCE
    cur = pg_conn.get_cursor()

    PG_INSERT_QUERY = some_object.insert_query
    args_list = some_object.get_pg_arg_list()

    """
        args_list = re.split(';', every_line)
        args_list = [x.replace('\"','') for x in args_list]
        args_list[0] = int(args_list[0])
    """

    try:
        cur.execute(PG_INSERT_QUERY, args_list)
    except Exception, e:
        print PG_INSERT_QUERY, args_list
        msg = "insert data failed for Query: {query} Args: {args} Exception: {excp}".format(query=PG_INSERT_QUERY,
                                                                                            args=args_list,
                                                                                            excp=str(e))
        print_to_console(msg, LOG_ALL_ERRORS)
        log_to_file(msg, ERROR_LOG_FILE_NAME)

    # Yeap, this crap I am not the biggest fun of!
    if dummy_flag:
        try:
            res = cur.fetchone()
            order_book_id = res[0]

            for ask in some_object.ask:
                cur.execute(ORDER_BOOK_INSERT_ASKS, (order_book_id, ask.price, ask.volume))

            for bid in some_object.bid:
                cur.execute(ORDER_BOOK_INSERT_BIDS, (order_book_id, bid.price, bid.volume))
        except Exception, e:
            msg = "Insert data failed for order book exactly. Exception: {excp}".format(excp=str(e))
            print_to_console(msg, LOG_ALL_ERRORS)
            log_to_file(msg, ERROR_LOG_FILE_NAME)


def load_to_postgres(array, pattern_name, pg_conn):

    dummy_flag = (pattern_name == ORDER_BOOK_TYPE_NAME)
    for entry in array:
        if entry is not None:
            insert_data(entry, pg_conn, dummy_flag)

    pg_conn.commit()


def save_alarm_into_pg(src_ticker, dst_ticker, pg_conn):
    cur = pg_conn.get_cursor()

    PG_INSERT_QUERY = "insert into alarms(src_exchange_id, dst_exchange_id, src_pair_id, dst_pair_id, src_ask_price, dst_bid_price, timest, date_time) " \
                      "values(%s, %s, %s, %s, %s, %s, %s, %s);"
    args_list = (
        src_ticker.exchange_id,
        dst_ticker.exchange_id,
        src_ticker.pair_id,
        dst_ticker.pair_id,
        src_ticker.ask,
        dst_ticker.bid,
        src_ticker.timest,
        get_date_time_from_epoch(src_ticker.timest)
    )

    try:
        cur.execute(PG_INSERT_QUERY, args_list)
    except Exception, e:
        msg = "save_alarm_into_pg insert data failed :( Exception: {excp}. Args: {args}".format(excp=str(e), args=args_list)
        print_to_console(msg, LOG_ALL_ERRORS)
        log_to_file(msg, ERROR_LOG_FILE_NAME)

    pg_conn.commit()


def get_time_entries(pg_conn):
    time_entries = []

    select_query = "select distinct timest from order_book order by timest asc"
    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        time_entries.append(long(row[0]))

    return time_entries


def get_order_book_asks(pg_conn, order_book_id):
    order_books_asks = []

    select_query = "select id, order_book_id, price, volume from order_book_ask where order_book_id = " + str(order_book_id)
    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        order_books_asks.append(row)

    return order_books_asks


def get_order_book_bids(pg_conn, order_book_id):
    order_books_bids = []

    select_query = "select id, order_book_id, price, volume from order_book_bid where order_book_id = " + str(order_book_id)
    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        order_books_bids.append(row)

    return order_books_bids


def get_order_book_by_time(pg_conn, timest):
    order_books = defaultdict(list)

    select_query = "select id, pair_id, exchange_id, timest from order_book where timest = " + str(timest)
    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        order_book_id = row[0]

        order_book_asks = get_order_book_asks(pg_conn, order_book_id)
        order_book_bids = get_order_book_bids(pg_conn, order_book_id)

        order_books[int(row[2])].append(OrderBook.from_row(row, order_book_asks, order_book_bids))

    return order_books


def get_arbitrage_id(pg_conn):
    cursor = pg_conn.get_cursor()
    select_query = """select nextval('arbitrage_id_seq')"""
    cursor.execute(select_query)

    for row in cursor:
        return long(row[0])

    return None


def save_order_into_pg(order, pg_conn, table_name="orders"):
    cur = pg_conn.get_cursor()

    PG_INSERT_QUERY = "insert into {table_name}(arbitrage_id, exchange_id, trade_type, pair_id, price, volume, executed_volume, deal_id, " \
                      "order_book_time, create_time, execute_time, execute_time_date) " \
                      "values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);".format(table_name=table_name)
    args_list = (
        order.arbitrage_id,
        order.exchange_id,
        order.trade_type,
        order.pair_id,
        order.price,
        order.volume,
        order.executed_volume,
        order.deal_id,
        order.order_book_time,
        order.create_time,
        order.execute_time,
        get_date_time_from_epoch(order.execute_time) if order.execute_time is not None else order.execute_time
    )

    try:
        cur.execute(PG_INSERT_QUERY, args_list)
    except Exception, e:
        msg = "save_order_into_pg insert data failed :( Exception: {excp}. Args: {args}".format(excp=str(e), args=args_list)
        print_to_console(msg, LOG_ALL_ERRORS)
        log_to_file(msg, ERROR_LOG_FILE_NAME)

    pg_conn.commit()


def get_all_orders(pg_conn, table_name="orders", time_start=START_OF_TIME):
    orders = []

    if time_start == START_OF_TIME:
        select_query = """select arbitrage_id, exchange_id, trade_type, pair_id, price, volume, executed_volume, deal_id, 
        order_book_time, create_time, execute_time from {table_name}""".format(table_name=table_name)
    else:
        select_query = """select arbitrage_id, exchange_id, trade_type, pair_id, price, volume, executed_volume, 
        deal_id, order_book_time, create_time, execute_time from {table_name} where create_time >= {create_time}
        """.format(table_name=table_name, create_time=time_start)

    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        orders.append(Trade.from_row(row))

    return orders


def is_order_present_in_order_history(pg_conn, trade, table_name="orders"):
    """
                We can execute history retrieval several times.
                Some exchanges do not have precise mechanism to exclude particular time range.
                It is possible to have multiple trades per order = deal_id.
                As this is arbitrage it mean that all other fields may be the same.
                exchange_id | trade_type | pair_id |   price   |  volume    |   deal_id | timest

                executed_volume

    :param pg_conn:
    :param trade:
    :param table_name:
    :return:
    """

    select_query = """select arbitrage_id, exchange_id, trade_type, pair_id, price, volume, executed_volume, deal_id, 
        order_book_time, create_time, execute_time from {table_name} where deal_id = '{trade_id}'""".format(
        table_name=table_name, trade_id=trade.deal_id)

    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    for row in cursor:
        cur_trade = Trade.from_row(row)
        if abs(cur_trade.executed_volume - trade.executed_volume) < 0.0000001 and \
                cur_trade.create_time == trade.create_time:
            return True

    return False


def is_trade_present_in_trade_history(pg_conn, trade, table_name="trades_history"):
    """
            For every order we can have multiple trades executed.
            In ideal case they all will be connected to the same order_id
            but not all exchange support it - Binance for example.

            Another tricky case python and how it deal with float point number and rounding

            So query below just an approximation to minimize possible duplicates

    :param pg_conn:
    :param trade:
    :param table_name:
    :return:
    """

    select_query = """select * from {table_name} where exchange_id = {exchange_id} and trade_type = {trade_type} and 
    pair_id = {pair_id} and price between {min_price} and {max_price} and volume between {min_volume} and {max_volume} 
    and create_time = {create_time}""".format(table_name=table_name, exchange_id=trade.exchange_id, trade_type=trade.trade_type,
                                            pair_id=trade.pair_id, min_price=trade.price-1.0, max_price=trade.price+1.0,
                                            min_volume=trade.volume-1.0, max_volume=trade.volume+1.0, create_time=trade.create_time)

    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    return cursor.rowcount > 0


def get_next_candidates(pg_conn, predicate):
    """
    :param pg_conn:
    :param predicate: method that should trigger retrieval of pair candles
    :return:
    """

    select_query = "select id, pair_id, exchange_id, open, close, high, low, timest, date_time from candle"

    cursor = pg_conn.get_cursor()

    cursor.execute(select_query)

    prev = None
    for row in cursor:
        cur = Candle.from_row(row)
        if prev is None:
            prev = cur
            continue
        else:
            if predicate(cur.high, prev.low):
                yield cur, prev
