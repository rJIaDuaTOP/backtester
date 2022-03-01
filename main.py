import pandas as pd
import numpy as np
from mmutils import size_per_level_calculator, size_tp_level, initialize_orders
from mmutils import MovingAverage
import time
class Backtester:
    __slots__ = ('lob_data', 'trades_data', 'events', 'trades', 'orders', 'place_timeout', 'cancel_timeout',
                 'delay', 'initial_capital', 'position', 'position_usdt', 'profit', 'precision', 'maxpose',
                 'price_precision', 'flsu', 'levels', 'best_bid', 'best_ask', 'mid', 'risk', 'price_inc',
                 'spread_window', 'ma_mid', 'price_long_tp', 'price_short_tp',
                 'pnl', 'tp_timer', 'tp_move_cancel', 'take_profit', 'place', 'cancel')
    def __init__(self,first_level_size_usd,
                 lob_data, trades_data, place_timeout, precision, price_precision,
                 cancel_timeout, delay, levels, price_increment,take_profit, tp_timer, tp_move, spread_window=50,
                 initial_capital=1000.0, maxpose = 2000, orders={}):
        self.lob_data = lob_data
        self.trades_data = trades_data
        self.events = []
        self.trades = []
        self.orders = orders
        self.place_timeout = place_timeout
        self.cancel_timeout = cancel_timeout
        self.delay = delay
        self.initial_capital = initial_capital
        self.position = 0
        self.position_usdt = 0
        self.profit = 0
        self.precision = precision
        self.maxpose = maxpose
        self.price_precision = price_precision
        self.flsu = first_level_size_usd
        self.levels = levels
        self.best_bid = 0
        self.best_ask = 0
        self.mid = 0
        self.risk = 0
        self.price_inc = price_increment
        self.spread_window = spread_window
        self.ma_mid = MovingAverage(self.spread_window)
        self.price_long_tp = 0
        self.price_short_tp = 0
        self.pnl = 0
        self.tp_timer = tp_timer
        self.tp_move_cancel = tp_move
        self.take_profit = take_profit
        self.place = ()
        self.cancel = []

    def prepare_dataset(self):
        cols = ['time']
        trade_cols = ['time', 'price', 'volume']
        event_cols = ['time', 'label']
        for i in range(10):
            cols.append('bp' + str(i + 1))
            cols.append('b' + str(i + 1))
        for i in range(10):
            cols.append('ap' + str(i + 1))
            cols.append('a' + str(i + 1))

        lob_data = pd.read_csv(self.lob_data, header=None, names=cols)
        lob_data.insert(1, 'label', ['lob'] * len(lob_data))
        trades_data = pd.read_csv(self.trades_data, header=None, names=trade_cols)
        trades_data.insert(1,'label',['trade'] * len(trades_data))
        final_data = pd.concat([lob_data.set_index('time'), trades_data.set_index('time')], axis=0,
                               ignore_index=False).sort_index().reset_index()
        final_data = final_data.values.tolist()
        start_timestamp = final_data[0][0]
        end_timestamp = final_data[-1][0]
        current_timestamp = start_timestamp
        current_timestamp_place = start_timestamp
        current_timestamp_cancel = start_timestamp
        new_event_que = []
        while current_timestamp < end_timestamp:
            if current_timestamp_place < end_timestamp:
                current_timestamp_place = current_timestamp_place + self.place_timeout
                events = [[current_timestamp_place + self.place_timeout, 'place'],
                          [current_timestamp_place + self.place_timeout + self.delay, 'placed']]
                new_event_que.extend(events)
            if current_timestamp_cancel < end_timestamp:
                current_timestamp_cancel = current_timestamp_cancel + self.cancel_timeout
                events = [[current_timestamp_cancel + self.cancel_timeout, 'cancel'],
                          [current_timestamp_cancel + self.cancel_timeout + self.delay, 'canceled']]
                new_event_que.extend(events)
            current_timestamp = min(current_timestamp_place, current_timestamp_cancel)
        final_data.extend(new_event_que)
        final_data = (sorted(final_data, key=lambda x: x[0]))
        self.lob_data = []
        self.trades_data = []
        return final_data

    def run(self) -> float:

        print('preparing DATASET')
        data = Backtester.prepare_dataset(self)
        print('prepared DATASET')
        print('starting run loop')
        while len(data) > 0:
            print('start' + str(time.time()))
            print(len(data))
            event = data.pop(0)
            print(event[1])
            if event[1] == 'lob':
                self.best_bid = event[20]
                self.best_ask = event[22]
                self.mid = (event[22]+event[20])/2
                self.ma_mid.next(self.mid)
                self.risk = (1 - np.std(self.ma_mid.que) / self.mid)
                ba_spread_bps = self.best_ask/self.best_bid - 1
                size_per_level_calculator(levels=self.levels,orders=self.orders,
                                          level_size_factor=1.1, midprice=self.mid, risk_adjustment = self.risk, maxpose=self.maxpose,
                                          first_level_size_usd = self.flsu, precision=self.precision, position=self.position)
            elif event[1] == 'trade':
                if self.position == 0:
                    if event[2] < self.orders[1]['order_price_buy'] and self.orders[1]['wait_buy']==1:
                        self.position+=self.orders[1]['size_buy']
                        self.position_usdt+=self.orders[1]['size_buy']*self.orders[1]['order_price_buy']
                        self.price_long_tp = self.orders[1]['order_price_buy']*(1+self.take_profit)
                        self.orders[1]['wait_buy'] = 0
                        print('filled first level buy')
                        print(self.position)

                        for i in range (2,self.levels + 1):
                            if event[2] < self.orders[i]['order_price_buy'] and self.orders[i]['wait_buy']==1:
                                print(f'filled {i} level buy')
                                self.position += self.orders[i]['size_buy']
                                self.position_usdt += self.orders[i]['size_buy'] * self.orders[i]['order_price_buy']
                                self.price_long_tp = (self.position_usdt/self.position)*(1+self.take_profit)
                                self.orders[i]['wait_buy'] = 0
                                print(self.position)

                    if event[2] > self.orders[1]['order_price_sell'] and self.orders[1]['wait_sell']==1:
                        self.position-=self.orders[1]['size_sell']
                        self.position_usdt -= self.orders[1]['size_sell'] * self.orders[1]['order_price_sell']
                        self.price_short_tp = self.orders[1]['order_price_sell'] * (1 - self.take_profit)
                        self.orders[1]['wait_sell'] = 0
                        print('filled first level sell')
                        print(self.position)

                        for i in range (2,self.levels + 1):
                            if event[2] < self.orders[i]['order_price_sell'] and self.orders[i]['wait_sell']==1:
                                print(f'filled {i} level sell')
                                self.position -= self.orders[i]['size_sell']
                                self.position_usdt -= self.orders[i]['size_sell'] * self.orders[i]['order_price_sell']
                                self.price_short_tp = (self.position_usdt/self.position) * (1 - self.take_profit)
                                self.orders[i]['wait_sell'] = 0
                                print(self.position)

                if self.position > 0:
                    if event[2] < self.orders[1]['order_price_buy'] and self.orders[1]['wait_buy'] == 1:
                        self.position += self.orders[1]['size_buy']
                        self.position_usdt += self.orders[1]['size_buy'] * self.orders[1]['order_price_buy']
                        self.price_long_tp = (self.position_usdt / self.position) * (1 + self.take_profit)
                        self.orders[1]['wait_buy'] = 0
                        print('filled additional buy')
                        print(self.position)

                        for i in range(2, self.levels + 1):
                            if event[2] < self.orders[i]['order_price_buy'] and self.orders[i]['wait_buy'] == 1:
                                print(f'filled {i} level buy')
                                self.position += self.orders[i]['size_buy']
                                self.position_usdt += self.orders[i]['size_buy'] * self.orders[i]['order_price_buy']
                                self.price_long_tp = (self.position_usdt / self.position) * (1 + self.take_profit)
                                self.orders[i]['wait_buy'] = 0
                                print(self.position)

                    if event[2] > self.orders[1]['order_price_sell'] and self.orders[1]['wait_sell'] == 1:
                        self.position -= self.orders[1]['size_sell']
                        self.position_usdt -= self.orders[1]['size_sell'] * self.orders[1]['order_price_sell']
                        self.pnl += self.take_profit * self.orders[1]['size_sell'] * self.orders[1][
                            'order_price_sell']
                        self.orders[1]['wait_sell'] = 0
                        print('filled tp level sell')
                        print(self.position)

                        for i in range(2, self.levels + 1):
                            if event[2] < self.orders[i]['order_price_sell'] and self.orders[i]['wait_sell'] == 1:
                                print(f'filled {i} tp level sell')
                                self.position -= self.orders[i]['size_sell']
                                self.pnl += self.take_profit * self.orders[i]['size_sell'] * self.orders[i][
                                    'order_price_sell']
                                self.position_usdt -= self.orders[i]['size_sell'] * self.orders[i]['order_price_sell']
                                self.orders[i]['wait_sell'] = 0
                                print(self.position)
                        if self.position == 0:
                            self.position_usdt = 0
                            self.price_long_tp = 0
                            self.price_short_tp = 0
                            print('flip from long to flat')
                        if self.position < 0:
                            self.price_short_tp = (self.position_usdt / self.position) * (1 - self.take_profit)
                            print('flip from long to short')
                        if self.position > 0:
                            pass

                if self.position < 0:
                    if event[2] > self.orders[1]['order_price_sell'] and self.orders[1]['wait_sell'] == 1:
                        self.position -= self.orders[1]['size_sell']
                        self.position_usdt -= self.orders[1]['size_sell'] * self.orders[1]['order_price_sell']
                        self.price_short_tp = (self.position_usdt / self.position) * (1 - self.take_profit)
                        self.orders[1]['wait_sell'] = 0
                        print('filled additional sell')
                        print(self.position)

                        for i in range(2,self.levels + 1):
                            if event[2] < self.orders[i]['order_price_sell'] and self.orders[i]['wait_sell'] == 1:
                                print(f'filled {i} level sell')
                                self.position -= self.orders[i]['size_sell']
                                self.position_usdt -= self.orders[i]['size_sell'] * self.orders[i]['order_price_sell']
                                self.price_short_tp = (self.position_usdt / self.position) * (1 - self.take_profit)
                                self.orders[i]['wait_sell'] = 0
                                print(self.position)

                    if event[2] < self.orders[1]['order_price_buy'] and self.orders[1]['wait_buy'] == 1:
                        self.position += self.orders[1]['size_buy']
                        self.position_usdt += self.orders[1]['size_buy'] * self.orders[1]['order_price_buy']
                        self.pnl += self.take_profit * self.orders[1]['size_buy'] * self.orders[1]['order_price_buy']
                        self.orders[1]['wait_buy'] = 0
                        print('filled tp level buy')
                        print(self.position)

                        for i in range(2, self.levels + 1):
                            if event[2] < self.orders[i]['order_price_buy'] and self.orders[i]['wait_buy'] == 1:
                                print(f'filled {i} tp level buy')
                                self.position += self.orders[i]['size_buy']
                                self.pnl += self.take_profit * self.orders[i]['size_buy'] * self.orders[i]['order_price_buy']
                                self.position_usdt += self.orders[i]['size_buy'] * self.orders[i]['order_price_buy']
                                self.orders[i]['wait_buy'] = 0
                                print(self.position)

                        if self.position == 0:
                            self.position_usdt = 0
                            self.price_long_tp = 0
                            self.price_short_tp = 0
                            print('flip from short to flat')
                        if self.position < 0:
                            pass
                        if self.position > 0:
                            self.price_long_tp = (self.position_usdt / self.position) * (1 + self.take_profit)
                            print('flip from short to long')

            elif event[1] == 'place':
                if self.position == 0:
                    if self.orders[self.levels]["wait_buy"] == 0:
                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_buy = self.best_bid - self.orders[self.levels]["safe_steps"] - np.std(self.ma_mid.que) - f_spread_adj
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_buy"] = 0
                        self.orders[self.levels]["order_price_buy"] = price_buy
                        self.orders[self.levels]['cancel_flag_buy'] = 0
                        self.place = (self.levels,'wait_buy')
                        continue
                    if self.orders[self.levels]["wait_sell"] == 0:
                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_sell = self.best_ask + self.orders[self.levels]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_sell"] = 0
                        self.orders[self.levels]["order_price_sell"] = price_sell
                        self.orders[self.levels]['cancel_flag_sell'] = 0
                        self.place = (self.levels, 'wait_sell')
                        continue

                    for i in range(1, self.levels):

                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_buy = self.best_bid - self.orders[i]["safe_steps"] - np.std(self.ma_mid.que) - f_spread_adj
                        price_sell = self.best_ask + self.orders[i]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj

                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)

                        waits_buy = [self.orders[j]["wait_buy"] for j in range(i + 1, 6)]
                        waits_sell = [self.orders[j]["wait_sell"] for j in range(i + 1, 6)]
                        if np.sum(waits_buy) == len(waits_buy) and self.orders[i]["wait_buy"] == 0:
                            self.orders[i]["timer_buy"] = 0
                            self.orders[i]["order_price_buy"] = price_buy
                            self.orders[i]['cancel_flag_buy'] = 0
                            self.place=(i,'wait_buy')
                            break

                        if np.sum(waits_sell) == len(waits_sell) and self.orders[i]["wait_sell"] == 0:
                            self.orders[i]["timer_sell"] = 0
                            self.orders[i]["order_price_sell"] = price_sell
                            self.orders[i]['cancel_flag_sell'] = 0
                            self.place = (i, 'wait_sell')
                            break
                if self.position > 0:
                    if self.orders[1]["wait_sell"] == 0:
                        self.orders[1]['size_ftx_sell'] = size_tp_level(first_level_size_usd=self.flsu,midprice=self.mid,
                                                                        precision=self.precision,position=self.position )
                        price_sell = max(self.mid, self.price_long_tp)
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)
                        self.orders[1]["timer_sell"] = 0
                        self.orders[1]["order_price_sell"] = price_sell
                        self.orders[1]['cancel_flag_sell'] = 0
                        self.place = (1, 'wait_sell')
                        continue

                    if self.orders[self.levels]["wait_buy"] == 0 and abs(self.position) < self.maxpose:

                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_buy = self.best_bid - self.orders[self.levels]["safe_steps"] - np.std(self.ma_mid.que) - f_spread_adj
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_buy"] = 0
                        self.orders[self.levels]["order_price_buy"] = price_buy
                        self.orders[self.levels]['cancel_flag_buy'] = 0
                        self.place = (self.levels, 'wait_buy')
                        continue

                    if self.orders[self.levels]["wait_sell"] == 0:
                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_sell = self.best_ask + self.orders[self.levels]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_sell"] = 0
                        self.orders[self.levels]["order_price_sell"] = price_sell
                        self.orders[self.levels]['cancel_flag_sell'] = 0
                        self.place=(self.levels,'wait_sell')

                    for i in range(1, self.levels):

                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_buy = self.best_bid - self.orders[i]["safe_steps"] - np.std(self.ma_mid.que) - f_spread_adj
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                        waits_buy = [self.orders[j]["wait_buy"] for j in range(i + 1, 6)]

                        if np.sum(waits_buy) == len(waits_buy) and self.orders[i]["wait_buy"] == 0:
                            self.orders[i]["timer_buy"] = 0
                            self.orders[i]["order_price_buy"] = price_buy
                            self.orders[i]['cancel_flag_buy'] = 0
                            self.place = (i, 'wait_buy')
                            break
                        if i > 1:
                            price_sell = max(self.best_ask, self.price_long_tp + self.orders[i]["safe_steps"]) + np.std(
                                self.ma_mid.que) + f_spread_adj
                            price_sell = round(self.price_inc * round(price_sell / self.price_inc),
                                               self.price_precision)
                            waits_sell = [self.orders[j]["wait_sell"] for j in range(i + 1, 6)]

                            if np.sum(waits_sell) == len(waits_sell) and self.orders[i]["wait_sell"] == 0:
                                self.orders[i]["timer_sell"] = 0
                                self.orders[i]["order_price_sell"] = price_sell
                                self.orders[i]['cancel_flag_sell'] = 0
                                self.place = (i, 'wait_sell')
                                break

                if self.position < 0:
                    if self.orders[1]["wait_buy"] == 0:
                        self.orders[1]['size_ftx_buy'] = size_tp_level(first_level_size_usd=self.flsu,
                                                                        midprice=self.mid,
                                                                        precision=self.precision,
                                                                        position=self.position)
                        price_buy = min(self.mid, self.price_short_tp)
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                        self.orders[1]["timer_buy"] = 0
                        self.orders[1]["order_price_buy"] = price_buy
                        self.orders[1]['cancel_flag_buy'] = 0
                        self.place = (1, 'wait_buy')
                        continue

                    if self.orders[self.levels]["wait_sell"] == 0 and abs(self.position) < self.maxpose:
                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_sell = self.best_ask + self.orders[self.levels]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_sell"] = 0
                        self.orders[self.levels]["order_price_sell"] = price_sell
                        self.orders[self.levels]['cancel_flag_sell'] = 0
                        self.place = (self.levels, 'wait_sell')
                        continue

                    if self.orders[self.levels]["wait_buy"] == 0:
                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc),
                                             self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_buy = self.best_bid - self.orders[self.levels]["safe_steps"] - np.std(
                            self.ma_mid.que) - f_spread_adj
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)

                        self.orders[self.levels]["timer_buy"] = 0
                        self.orders[self.levels]["order_price_buy"] = price_buy
                        self.orders[self.levels]['cancel_flag_buy'] = 0
                        self.place = (self.levels, 'wait_buy')
                        continue

                    for i in range(1, self.levels):

                        f_spread = self.best_ask - self.best_bid
                        f_spread_adj = f_spread / 2
                        f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                        # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                        # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                        # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)

                        price_sell = self.best_ask + self.orders[self.levels]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc), self.price_precision)
                        waits_sell = [self.orders[j]["wait_sell"] for j in range(i + 1, 6)]

                        if np.sum(waits_sell) == len(waits_sell) and self.orders[i]["wait_sell"] == 0:
                            self.orders[i]["timer_sell"] = 0
                            self.orders[i]["order_price_sell"] = price_sell
                            self.orders[i]['cancel_flag_sell'] = 0
                            self.place = (i, 'wait_sell')
                            break
                        if i > 1:
                            price_buy = min(self.best_bid, self.price_short_tp - self.orders[i]["safe_steps"]) - np.std(
                                self.ma_mid.que) - f_spread_adj
                            price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                            waits_buy = [self.orders[j]["wait_buy"] for j in range(i + 1, 6)]

                            if np.sum(waits_buy) == len(waits_buy) and self.orders[i]["wait_buy"] == 0:
                                self.orders[i]["timer_buy"] = 0
                                self.orders[i]["order_price_buy"] = price_buy
                                self.orders[i]['cancel_flag_buy'] = 0
                                self.place = (i, 'wait_buy')
                                break

            elif event[1] == 'placed':
                if self.place != 0:
                    print('placed '+str(self.place[0])+' '+str(self.place[1]))
                    self.orders[self.place[0]][self.place[1]] = 1
                    self.place = 0
                else:
                    pass
            elif event[1] == 'cancel':
                for i in range(1, self.levels+1):
                    if self.orders[i]["wait_buy"] == 1:
                        self.orders[i]["timer_buy"] += 1
                    if self.orders[i]["wait_sell"] == 1:
                        self.orders[i]["timer_sell"] += 1
                f_spread = self.best_ask - self.best_bid
                f_spread_adj = f_spread / 2
                f_spread_adj = round(self.price_inc * round(f_spread_adj / self.price_inc), self.price_precision)

                # f_imb = (self.best_bid - self.best_ask) / (self.best_bid + self.best_ask)
                # f_imb_adj = (f_imb * f_spread) / 2  # take half to be lower or equal than midprice
                # f_imb_adj = round(self.price_inc * round(f_imb_adj / self.price_inc), self.price_precision)
                if self.position == 0:
                        for i in range(1, self.levels + 1):
                            price_buy = self.best_bid - self.orders[i]["safe_steps"] - np.std(
                                self.ma_mid.que) - f_spread_adj
                            price_sell = self.best_ask + self.orders[i]["safe_steps"] + np.std(
                                self.ma_mid.que) + f_spread_adj

                            price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                            price_sell = round(self.price_inc * round(price_sell / self.price_inc),
                                               self.price_precision)
                            if self.orders[i]['wait_buy'] == 1:
                                if (self.orders[i]["timer_buy"] > self.orders[i]["timer_cancel"]) * \
                                        (abs(1 - price_buy / self.orders[i]["order_price_buy"]) > self.orders[i]["move_cancellation"])\
                                        and self.orders[i]["cancel_flag_buy"] == 0:
                                    print(f'cancel {i} buy')
                                    self.orders[i]["timer_buy"] = 0
                                    self.orders[i]['cancel_flag_buy'] = 1
                                    self.cancel.append([i,'wait_buy'])
                            if self.orders[i]['wait_sell'] == 1:
                                if (self.orders[i]["timer_sell"] > self.orders[i]["timer_cancel"]) * \
                                        (abs(1 - price_sell / self.orders[i]["order_price_sell"]) > self.orders[i]["move_cancellation"]) \
                                        and self.orders[i]["cancel_flag_sell"] == 0:
                                    print(f'cancel {i} sell')
                                    self.orders[i]["timer_sell"] = 0
                                    self.orders[i]['cancel_flag_sell'] = 1
                                    self.cancel.append([i, 'wait_sell'])
                                    self.cancel.append([i, 'wait_sell'])
                if self.position > 0:
                    for i in range(1, self.levels + 1):
                        price_buy = self.best_bid - self.orders[i]["safe_steps"] - np.std(
                            self.ma_mid.que) - f_spread_adj
                        if i == 1:
                            price_sell = max(self.mid, self.price_long_tp) + np.std(self.ma_mid.que) + f_spread_adj
                            size_ftx_sell = size_tp_level(first_level_size_usd=self.flsu,midprice=self.mid,precision=self.precision, position=self.position)
                        if i > 1:
                            price_sell = (max(self.best_ask, self.price_long_tp + self.orders[i]["safe_steps"]) + np.std(self.ma_mid.que) + f_spread_adj)
                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc),self.price_precision)

                        if self.orders[i]['wait_buy'] == 1:
                            if (self.orders[i]["timer_buy"] > self.orders[i]["timer_cancel"]) * \
                                    (abs(1 - price_buy / self.orders[i]["order_price_buy"]) > self.orders[i][
                                        "move_cancellation"]) \
                                    and self.orders[i]["cancel_flag_buy"] == 0:
                                print(f'cancel {i} buy')
                                self.orders[i]["timer_buy"] = 0
                                self.orders[i]['cancel_flag_buy'] = 1
                                self.cancel.append([i, 'wait_buy'])
                        if self.orders[i]['wait_sell'] == 1:
                            if i > 1:
                                if (self.orders[i]["timer_sell"] > self.orders[i]["timer_cancel"]) * \
                                        (abs(1 - price_sell / self.orders[i]["order_price_sell"]) > self.orders[i][
                                            "move_cancellation"]) \
                                        and self.orders[i]["cancel_flag_sell"] == 0:
                                    print(f'cancel {i} sell')
                                    self.orders[i]["timer_sell"] = 0
                                    self.orders[i]['cancel_flag_sell'] = 1
                                    self.cancel.append([i, 'wait_sell'])
                            if i == 1:
                                if (self.orders[i]["timer_sell"] > self.tp_timer) * \
                                        (abs(1 - price_sell / self.orders[i]["order_price_sell"]) > self.tp_move_cancel) or \
                                        ((self.orders[i]["timer_sell"] > 1)*(size_ftx_sell>self.orders[1]['size_sell'])) \
                                        and self.orders[i]["cancel_flag_sell"] == 0:
                                    print(f'cancel tp sell')
                                    self.orders[1]["timer_sell"] = 0
                                    self.orders[1]['cancel_flag_sell'] = 1
                                    self.cancel.append([i, 'wait_sell'])
                if self.position < 0:
                    for i in range(1, self.levels + 1):
                        if i == 1:
                            price_buy = self.best_bid - self.orders[i]["safe_steps"] - np.std(self.ma_mid.que) - f_spread_adj
                            size_ftx_buy = size_tp_level(first_level_size_usd=self.flsu,midprice=self.mid,precision=self.precision, position=self.position)
                        if i > 1:
                            price_buy = (min(self.best_bid, self.price_short_tp - self.orders[i]["safe_steps"]) - np.std(
                                    self.ma_mid.que) - f_spread_adj)
                        price_sell = self.best_ask + self.orders[i]["safe_steps"] + np.std(self.ma_mid.que) + f_spread_adj

                        price_buy = round(self.price_inc * round(price_buy / self.price_inc), self.price_precision)
                        price_sell = round(self.price_inc * round(price_sell / self.price_inc),self.price_precision)

                        if self.orders[i]['wait_buy'] == 1:
                            if i>1:
                                if (self.orders[i]["timer_buy"] > self.orders[i]["timer_cancel"]) * \
                                        (abs(1 - price_buy / self.orders[i]["order_price_buy"]) > self.orders[i]["move_cancellation"])\
                                        and self.orders[i]["cancel_flag_buy"] == 0:
                                    print(f'cancel {i} buy')
                                    self.orders[i]["timer_buy"] = 0
                                    self.orders[i]['cancel_flag_buy'] = 1
                                    self.cancel.append([i,'wait_buy'])
                            if i == 1:
                                if (self.orders[i]["timer_buy"] > self.tp_timer) * \
                                        (abs(1 - price_buy / self.orders[i]["order_price_buy"]) > self.tp_move_cancel) or \
                                        ((self.orders[i]["timer_buy"] > 1)*(size_ftx_buy>self.orders[1]['size_buy'])) \
                                        and self.orders[i]["cancel_flag_buy"] == 0:
                                    print(f'cancel tp buy')
                                    self.orders[1]["timer_buy"] = 0
                                    self.orders[1]['cancel_flag_buy'] = 1
                                    self.cancel.append([i,'wait_buy'])
                        if self.orders[i]['wait_sell'] == 1:
                            if (self.orders[i]["timer_sell"] > self.orders[i]["timer_cancel"]) * \
                                    (abs(1 - price_sell / self.orders[i]["order_price_sell"]) > self.orders[i]["move_cancellation"]) \
                                    and self.orders[i]["cancel_flag_sell"] == 0:
                                print(f'cancel {i} sell')
                                self.orders[i]["timer_sell"] = 0
                                self.orders[i]['cancel_flag_sell'] = 1
                                self.cancel.append([i, 'wait_sell'])
                                self.cancel.append([i, 'wait_sell'])
            elif event[1] == 'canceled':
                if self.cancel:
                    item = self.cancel.pop(0)
                    print('cancel '+str(item[0])+' '+str(item[1]))
                    self.orders[item[0]][item[1]] = 0
            print('finish' + str(time.time()))
        return self.pnl

a = Backtester(lob_data='AXS_orderbook.csv', trades_data='AXS_trades.csv', maxpose=5000, place_timeout=167, cancel_timeout=90,
               delay=30, levels=5, initial_capital=1000.0, first_level_size_usd=50,price_increment=0.001,
               price_precision=3, precision=1,take_profit=0.001,
               tp_timer=100,tp_move=0.0005,
               orders=initialize_orders(safe_steps=[2,20,55,85,120],move_cancellations=[0.0004,0.0006,0.0010,0.0012,0.0015]))


print(a.run())
