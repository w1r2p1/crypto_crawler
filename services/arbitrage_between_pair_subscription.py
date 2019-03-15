import argparse
import threading
from Queue import Queue as queue

from data_access.message_queue import get_message_queue
from data_access.priority_queue import get_priority_queue

from core.arbitrage_core import compute_new_min_cap_from_tickers, search_for_arbitrage
from core.expired_order import add_orders_to_watch_list
from dao.deal_utils import init_deals_with_logging_speedy
from enums.deal_type import DEAL_TYPE

from data.BalanceState import dummy_balance_init

from dao.balance_utils import get_updated_balance_arbitrage
from dao.order_book_utils import get_order_book
from dao.ticker_utils import get_ticker_for_arbitrage
from dao.socket_utils import get_subcribtion_by_exchange

from data.ArbitrageConfig import ArbitrageConfig
from data.OrderBook import OrderBook

from data_access.classes.ConnectionPool import ConnectionPool
from data_access.memory_cache import get_cache
from data.MarketCap import MarketCap

from debug_utils import print_to_console, LOG_ALL_ERRORS, set_logging_level, CAP_ADJUSTMENT_TRACE_LOG_FILE_NAME, \
    set_log_folder, SOCKET_ERRORS_LOG_FILE_NAME

from enums.exchange import EXCHANGE
from enums.status import STATUS
from enums.sync_stages import ORDER_BOOK_SYNC_STAGES

from utils.currency_utils import get_currency_pair_name_by_exchange_id
from utils.exchange_utils import get_exchange_name_by_id
from utils.file_utils import log_to_file
from utils.key_utils import load_keys
from utils.time_utils import get_now_seconds_utc, sleep_for

from logging_tools.arbitrage_between_pair_logging import log_dont_supported_currency, log_balance_expired_errors, \
    log_reset_stage_successfully, log_init_reset, log_reset_final_stage, log_cant_update_volume_cap, \
    log_finishing_syncing_order_book, log_all_order_book_synced, log_order_book_update_failed_pre_sync, \
    log_order_book_update_failed_post_sync, log_one_of_subscriptions_failed

from constants import NO_MAX_CAP_LIMIT, BALANCE_EXPIRED_THRESHOLD

from deploy.classes.CommonSettings import CommonSettings

from services.sync_stage import get_stage, set_stage

import os


class ArbitrageListener:
    def __init__(self, cfg, app_settings):

        self._init_settings(cfg)
        self._init_infrastructure(app_settings)
        self.reset_arbitrage_state()

        while True:
            if self.buy_subscription.is_running() and self.sell_subscription.is_running():
                sleep_for(1)
            else:
                # We will NOT issue a reset till any pending process still running
                while self.buy_subscription.is_running() or self.sell_subscription.is_running():
                    sleep_for(1)
                self.reset_arbitrage_state()

    def reset_arbitrage_state(self):

        local_timeout = 1

        while True:
            sleep_for(local_timeout)

            sleep_for(local_timeout)

            log_init_reset()

            set_stage(ORDER_BOOK_SYNC_STAGES.RESETTING)

            self.update_balance_run_flag = False
            self.update_min_cap_run_flag = False

            self.clear_queue(self.sell_exchange_updates)
            self.clear_queue(self.buy_exchange_updates)

            self._init_arbitrage_state()            # Spawn balance & cap threads, no blocking
            self.subscribe_to_order_book_update()   # Spawn order book subscription threads, no blocking
            self.sync_order_books()                 # Spawn order book sync threads, BLOCKING till they finished

            log_reset_final_stage()

            if get_stage() != ORDER_BOOK_SYNC_STAGES.AFTER_SYNC:

                self.shutdown_subscriptions()

                log_to_file("reset_arbitrage_state - cant sync order book, lets try one more time!", SOCKET_ERRORS_LOG_FILE_NAME)

                while self.buy_subscription.is_running() or self.sell_subscription.is_running():
                    sleep_for(1)

                local_timeout += 1

            else:
                break

        log_reset_stage_successfully()

    def _init_settings(self, cfg):
        self.buy_exchange_id = cfg.buy_exchange_id
        self.sell_exchange_id = cfg.sell_exchange_id
        self.pair_id = cfg.pair_id
        self.log_file_name = cfg.log_file_name

        self.threshold = cfg.threshold
        self.reverse_threshold = cfg.reverse_threshold
        self.balance_threshold = cfg.balance_threshold

        self.cap_update_timeout = cfg.cap_update_timeout
        self.balance_update_timeout = cfg.balance_update_timeout

    def _init_infrastructure(self, app_settings):
        self.priority_queue = get_priority_queue(host=app_settings.cache_host, port=app_settings.cache_port)
        self.msg_queue = get_message_queue(host=app_settings.cache_host, port=app_settings.cache_port)
        self.local_cache = get_cache(host=app_settings.cache_host, port=app_settings.cache_port)
        self.processor = ConnectionPool(pool_size=2)

        self.sell_exchange_updates = queue()
        self.buy_exchange_updates = queue()

        buy_subscription_constructor = get_subcribtion_by_exchange(self.buy_exchange_id)
        sell_subscription_constructor = get_subcribtion_by_exchange(self.sell_exchange_id)

        self.buy_subscription = buy_subscription_constructor(pair_id=self.pair_id, on_update=self.on_order_book_update)
        self.sell_subscription = sell_subscription_constructor(pair_id=self.pair_id, on_update=self.on_order_book_update)

    def _init_arbitrage_state(self):
        self.init_deal_cap()
        self.init_balance_state()
        self.init_order_books()

        self.sell_order_book_synced = False
        self.buy_order_book_synced = False

        set_stage(ORDER_BOOK_SYNC_STAGES.BEFORE_SYNC)

    def init_deal_cap(self):
        self.deal_cap = MarketCap(self.pair_id, get_now_seconds_utc())
        self.deal_cap.update_max_volume_cap(NO_MAX_CAP_LIMIT)
        self.update_min_cap_run_flag = True
        # TODO FIXME UNCOMMENT self.subscribe_cap_update()

    def update_min_cap(self):
        log_to_file("Subscribing for updating cap updates", SOCKET_ERRORS_LOG_FILE_NAME)
        while self.update_min_cap_run_flag:
            # FIXME - to method
            cur_timest_sec = get_now_seconds_utc()
            tickers = get_ticker_for_arbitrage(self.pair_id, cur_timest_sec,
                                               [self.buy_exchange_id, self.sell_exchange_id], self.processor)
            new_cap = compute_new_min_cap_from_tickers(self.pair_id, tickers)

            if new_cap > 0:
                msg = "Updating old cap {op}".format(op=str(self.deal_cap))
                log_to_file(msg, CAP_ADJUSTMENT_TRACE_LOG_FILE_NAME)

                self.deal_cap.update_min_volume_cap(new_cap, cur_timest_sec)

                msg = "New cap {op}".format(op=str(self.deal_cap))
                log_to_file(msg, CAP_ADJUSTMENT_TRACE_LOG_FILE_NAME)

            else:
                log_cant_update_volume_cap(self.pair_id, self.buy_exchange_id, self.sell_exchange_id, self.log_file_name)

            tt = self.cap_update_timeout
            while tt:
                sleep_for(1)
                tt -= 1

        log_to_file("Exit from updating cap updates", SOCKET_ERRORS_LOG_FILE_NAME)

    def init_balance_state(self):
        self.balance_state = dummy_balance_init(timest=0, default_volume=100500, default_available_volume=100500)
        self.update_balance_run_flag = False
        # TODO FIXME UNCOMMENT self.subscribe_balance_update()

    def init_order_books(self):
        cur_timest_sec = get_now_seconds_utc()
        self.order_book_sell = OrderBook(pair_id=self.pair_id, timest=cur_timest_sec, sell_bids=[], buy_bids=[], exchange_id=self.sell_exchange_id)
        self.order_book_buy = OrderBook(pair_id=self.pair_id, timest=cur_timest_sec, sell_bids=[], buy_bids=[], exchange_id=self.buy_exchange_id)

    def update_from_queue(self, exchange_id, order_book, queue):
        while True:

            if not self.buy_subscription.is_running() or not self.sell_subscription.is_running():
                return STATUS.FAILURE

            try:
                order_book_update = queue.get(block=False)
            except:
                order_book_update = None

            if order_book_update is None:
                break

            if STATUS.SUCCESS != order_book.update(exchange_id, order_book_update):
                return STATUS.FAILURE

            queue.task_done()

        return STATUS.SUCCESS

    def clear_queue(self, queue):
        while True:

            try:
                order_book_update = queue.get(block=False)
            except:
                order_book_update = None

            if order_book_update is None:
                break

            queue.task_done()

    def sync_sell_order_book(self):
        if self.sell_exchange_id in [EXCHANGE.BINANCE, EXCHANGE.BITTREX]:
            self.order_book_sell = get_order_book(self.sell_exchange_id, self.pair_id)

            if self.order_book_sell is None:
                return STATUS.FAILURE

            self.order_book_sell.sort_by_price()

            if STATUS.FAILURE == self.update_from_queue(self.sell_exchange_id, self.order_book_sell, self.sell_exchange_updates):
                self.sell_order_book_synced = False

                return STATUS.FAILURE

        log_finishing_syncing_order_book("SELL")

        self.sell_order_book_synced = True

    def sync_buy_order_book(self):
        if self.buy_exchange_id in [EXCHANGE.BINANCE, EXCHANGE.BITTREX]:
            self.order_book_buy = get_order_book(self.buy_exchange_id, self.pair_id)

            if self.order_book_buy is None:
                return STATUS.FAILURE

            self.order_book_buy.sort_by_price()

            if STATUS.FAILURE == self.update_from_queue(self.buy_exchange_id, self.order_book_buy, self.buy_exchange_updates):
                self.buy_order_book_synced = False
                return STATUS.FAILURE

        log_finishing_syncing_order_book("BUY")

        self.buy_order_book_synced = True

    def sync_order_books(self):

        # DK NOTE: Those guys will endup by themselves

        msg = "sync_order_books - stage status is {}".format(get_stage())
        log_to_file(msg, SOCKET_ERRORS_LOG_FILE_NAME)

        sync_sell_order_book_thread = threading.Thread(target=self.sync_sell_order_book, args=())
        sync_sell_order_book_thread.daemon = True
        sync_sell_order_book_thread.start()

        sync_buy_order_book_thread = threading.Thread(target=self.sync_buy_order_book, args=())
        sync_buy_order_book_thread.daemon = True
        sync_buy_order_book_thread.start()

        # Wait for both thread be finished
        sync_sell_order_book_thread.join()
        sync_buy_order_book_thread.join()

        if self.sell_order_book_synced and self.buy_order_book_synced:
            set_stage(ORDER_BOOK_SYNC_STAGES.AFTER_SYNC)

        log_all_order_book_synced()

    def subscribe_cap_update(self):

        cap_update_thread = threading.Thread(target=self.update_min_cap, args=())
        cap_update_thread.daemon = True
        cap_update_thread.start()

    def update_balance(self):

        while self.update_balance_run_flag:
            cur_timest_sec = get_now_seconds_utc()
            self.balance_state = get_updated_balance_arbitrage(cfg, self.balance_state, self.local_cache)

            if self.balance_state.expired(cur_timest_sec, self.buy_exchange_id, self.sell_exchange_id,
                                          BALANCE_EXPIRED_THRESHOLD):
                log_balance_expired_errors(cfg, self.msg_queue, self.balance_state)

                assert False

            sleep_for(self.balance_update_timeout)

    def subscribe_balance_update(self):
        balance_update_thread = threading.Thread(target=self.update_balance, args=())
        balance_update_thread.daemon = True
        balance_update_thread.start()

    def subscribe_to_order_book_update(self):

        buy_subscription_thread = threading.Thread(target=self.buy_subscription.subscribe, args=())
        buy_subscription_thread.daemon = True
        buy_subscription_thread.start()

        sell_subscription_thread = threading.Thread(target=self.sell_subscription.subscribe, args=())
        sell_subscription_thread.daemon = True
        sell_subscription_thread.start()

    def shutdown_subscriptions(self):
        self.sell_subscription.disconnect()
        self.buy_subscription.disconnect()

    def _print_top10_buy_bids_asks(self, exchange_id):

        bids = self.order_book_buy.bid[:10]
        asks = self.order_book_buy.ask[:10]

        os.system('clear')

        print get_exchange_name_by_id(self.buy_exchange_id), "Current number of threads: ", threading.active_count(), \
            "Last update from: ", get_exchange_name_by_id(exchange_id), "at", get_now_seconds_utc()
        print "BIDS:"
        for b in bids:
            print b

        print "ASKS"
        for a in asks:
            print a

    def on_order_book_update(self, exchange_id, order_book_updates):
        """
        :param exchange_id:
        :param order_book_updates:  parsed OrderBook or OrderBookUpdates according to exchange specs
        :param stage:               whether BOTH orderbook synced or NOT
        :return:
        """

        print "Got update for", get_exchange_name_by_id(exchange_id), "Current number of threads: ", threading.active_count()

        curent_stage = get_stage()

        if not self.buy_subscription.is_running() or not self.sell_subscription.is_running():

            log_one_of_subscriptions_failed(self.buy_subscription.is_running(), self.sell_subscription.is_running(), curent_stage)

            self.shutdown_subscriptions()

            return

        if order_book_updates is None:
            print "Order book update is NONE! for", get_exchange_name_by_id(exchange_id)
            return

        if curent_stage == ORDER_BOOK_SYNC_STAGES.BEFORE_SYNC:

            print "Syncing in progress ..."

            if exchange_id == self.buy_exchange_id:
                if self.buy_order_book_synced:
                    order_book_update_status = self.order_book_buy.update(exchange_id, order_book_updates)
                    if order_book_update_status == STATUS.FAILURE:

                        log_order_book_update_failed_pre_sync("BUY", exchange_id, order_book_updates)

                        self.shutdown_subscriptions()

                else:
                    self.buy_exchange_updates.put(order_book_updates)
            else:
                if self.sell_order_book_synced:
                    order_book_update_status = self.order_book_sell.update(exchange_id, order_book_updates)
                    if order_book_update_status == STATUS.FAILURE:

                        log_order_book_update_failed_pre_sync("SELL", exchange_id, order_book_updates)

                        self.shutdown_subscriptions()

                else:
                    self.sell_exchange_updates.put(order_book_updates)

        elif curent_stage == ORDER_BOOK_SYNC_STAGES.AFTER_SYNC:

            print "Update after syncing...", get_exchange_name_by_id(exchange_id)

            if exchange_id == self.buy_exchange_id:
                order_book_update_status = self.order_book_buy.update(exchange_id, order_book_updates)
                if order_book_update_status == STATUS.FAILURE:

                    log_order_book_update_failed_post_sync(exchange_id, order_book_updates)

                    self.shutdown_subscriptions()

                    return

            else:
                order_book_update_status = self.order_book_sell.update(exchange_id, order_book_updates)
                if order_book_update_status == STATUS.FAILURE:

                    log_order_book_update_failed_post_sync(exchange_id, order_book_updates)

                    self.shutdown_subscriptions()

                    return

            # assert(self.order_book_sell.is_valid())
            # assert(self.order_book_buy.is_valid())

            self._print_top10_buy_bids_asks(exchange_id)

            # DK NOTE: only at this stage we are ready for searching for arbitrage

            # for mode_id in [DEAL_TYPE.ARBITRAGE, DEAL_TYPE.REVERSE]:
            #   method = search_for_arbitrage if mode_id == DEAL_TYPE.ARBITRAGE else adjust_currency_balance
            #   active_threshold = self.threshold if mode_id == DEAL_TYPE.ARBITRAGE else self.reverse_threshold

            # FIXME NOTE: order book expiration check

            # init_deals_with_logging_speedy
            # FIXME NOTE: src dst vs buy sell
            # status_code, deal_pair = search_for_arbitrage(self.order_book_sell, self.order_book_buy,
            #                                               self.threshold,
            #                                               self.balance_threshold,
            #                                               init_deals_with_logging_speedy,
            #                                               self.balance_state, self.deal_cap,
            #                                               type_of_deal=DEAL_TYPE.ARBITRAGE,
            #                                               worker_pool=self.processor,
            #                                               msg_queue=self.msg_queue)

            # add_orders_to_watch_list(deal_pair, self.priority_queue)

            # self.deal_cap.update_max_volume_cap(NO_MAX_CAP_LIMIT)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Constantly poll two exchange for order book for particular pair "
                                                 "and initiate sell\\buy deals for arbitrage opportunities")

    parser.add_argument('--threshold', action="store", type=float, required=True)
    parser.add_argument('--balance_threshold', action="store", type=float, required=True)
    parser.add_argument('--reverse_threshold', action="store", type=float, required=True)
    parser.add_argument('--sell_exchange_id', action="store", type=int, required=True)
    parser.add_argument('--buy_exchange_id', action="store", type=int, required=True)
    parser.add_argument('--pair_id', action="store", type=int, required=True)
    parser.add_argument('--deal_expire_timeout', action="store", type=int, required=True)

    parser.add_argument('--cfg', action="store", required=True)

    results = parser.parse_args()

    cfg = ArbitrageConfig(results.sell_exchange_id, results.buy_exchange_id,
                          results.pair_id, results.threshold,
                          results.reverse_threshold, results.balance_threshold,
                          results.deal_expire_timeout,
                          results.cfg)

    app_settings = CommonSettings.from_cfg(results.cfg)

    set_logging_level(app_settings.logging_level_id)
    set_log_folder(app_settings.log_folder)
    load_keys(app_settings.key_path)

    # to avoid time-consuming check in future - validate arguments here
    for exchange_id in [results.sell_exchange_id, results.buy_exchange_id]:
        pair_name = get_currency_pair_name_by_exchange_id(cfg.pair_id, exchange_id)
        if pair_name is None:
            log_dont_supported_currency(cfg, exchange_id, cfg.pair_id)
            exit()

    ArbitrageListener(cfg, app_settings)
