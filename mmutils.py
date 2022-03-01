from collections import deque


class MovingAverage:
    def __init__(self, size):
        self.que = deque([])
        self.size = size
        self.total = 0.0

    def next(self, val):
        # write your code here
        if len(self.que) < self.size:
            self.total += val
            self.que.appendleft(val)
            return None
        else:
            self.total -= self.que.pop()
            self.que.appendleft(val)
            self.total += val
            return self.total / len(self.que)


def size_per_level_calculator(levels, level_size_factor, first_level_size_usd,
                              risk_adjustment, maxpose, midprice, orders, precision, position):
    min_size = first_level_size_usd / midprice
    min_size = round(min_size, precision)
    if position == 0:
        for i in range(1, levels + 1):
            orders[i]["safe_steps"] = orders[i]["safe_steps_bps"] * midprice / 10000
            if i == 1:
                orders[i]["size_buy"] = min_size
                orders[i]["size_sell"] = min_size
            else:
                if midprice > 0 and maxpose > 1:
                    min_size = 0.03 * i * maxpose * risk_adjustment
                    min_size = round(min_size, precision)
                    orders[i]["size_buy"] = min_size
                    orders[i]["size_sell"] = min_size
                else:
                    orders[i]["size_buy"] = min_size * level_size_factor * i
                    orders[i]["size_sell"] = min_size * level_size_factor * i
    else:
        for i in range(2, levels + 1):
            orders[i]["safe_steps"] = orders[i]["safe_steps_bps"] * midprice / 10000
            if midprice > 0 and maxpose > 1:
                min_size = 0.03 * i * maxpose * risk_adjustment
                min_size = round(min_size, precision)
                orders[i]["size_buy"] = min_size
                orders[i]["size_sell"] = min_size
            else:
                orders[i]["size_buy"] = min_size * level_size_factor * i
                orders[i]["size_sell"] = min_size * level_size_factor * i

def size_tp_level(first_level_size_usd,midprice,precision, position):
    min_size = first_level_size_usd / midprice
    min_size = round(min_size, precision)
    if position > 0:
        return round(max(position / 2, min(position, min_size)), precision)
    if position < 0:
        return round(max(-position / 2, min(-position, min_size)), precision)

def initialize_orders(safe_steps,move_cancellations):
    return {
        1: {
            "wait_sell": 0,
            "wait_buy": 0,
            "timer_buy": 0,
            "timer_sell": 0,
            "id_buy": 0,
            "id_sell": 0,
            "size_buy": 0,
            "size_sell": 0,
            "order_price_sell": 0,
            "order_price_buy": 0,
            "move_cancellation": move_cancellations[0],
            "timer_cancel": 3,
            "safe_steps_bps": safe_steps[0],
            "safe_steps": 0,
            "cancel_flag_buy": 0,
            "cancel_flag_sell": 0,
            "remaining_size_buy": 0,
            "remaining_size_sell": 0,
        },
        2: {
            "wait_sell": 0,
            "wait_buy": 0,
            "timer_buy": 0,
            "timer_sell": 0,
            "id_buy": 0,
            "id_sell": 0,
            "size_buy": 0,
            "size_sell": 0,
            "order_price_sell": 0,
            "order_price_buy": 0,
            "move_cancellation": move_cancellations[1],
            "timer_cancel": 6,
            "safe_steps_bps": safe_steps[1],
            "safe_steps": 0,
            "cancel_flag_buy": 0,
            "cancel_flag_sell": 0,
            "remaining_size_buy": 0,
            "remaining_size_sell": 0,
        },
        3: {
            "wait_sell": 0,
            "wait_buy": 0,
            "timer_buy": 0,
            "timer_sell": 0,
            "id_buy": 0,
            "id_sell": 0,
            "size_buy": 0,
            "size_sell": 0,
            "order_price_sell": 0,
            "order_price_buy": 0,
            "move_cancellation": move_cancellations[2],
            "timer_cancel": 30,
            "safe_steps_bps": safe_steps[2],
            "safe_steps": 0,
            "cancel_flag_buy": 0,
            "cancel_flag_sell": 0,
            "remaining_size_buy": 0,
            "remaining_size_sell": 0,
        },
        4: {
            "wait_sell": 0,
            "wait_buy": 0,
            "timer_buy": 0,
            "timer_sell": 0,
            "id_buy": 0,
            "id_sell": 0,
            "size_buy": 0,
            "size_sell": 0,
            "order_price_sell": 0,
            "order_price_buy": 0,
            "move_cancellation": move_cancellations[3],
            "timer_cancel": 50,
            "safe_steps_bps": safe_steps[3],
            "safe_steps": 0,
            "cancel_flag_buy": 0,
            "cancel_flag_sell": 0,
            "remaining_size_buy": 0,
            "remaining_size_sell": 0,
        },
        5: {
            "wait_sell": 0,
            "wait_buy": 0,
            "timer_buy": 0,
            "timer_sell": 0,
            "id_buy": 0,
            "id_sell": 0,
            "size_buy": 0,
            "size_sell": 0,
            "order_price_sell": 0,
            "order_price_buy": 0,
            "move_cancellation": move_cancellations[4],
            "timer_cancel": 70,
            "safe_steps_bps": safe_steps[4],
            "safe_steps": 0,
            "cancel_flag_buy": 0,
            "cancel_flag_sell": 0,
            "remaining_size_buy": 0,
            "remaining_size_sell": 0,
        },
    }