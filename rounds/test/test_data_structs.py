import unittest

from rounds.call_market import CallMarket
from rounds.data_structs import DataForPlayer, DataForOrder
from rounds.models import *

BID = OrderType.BID.value
OFFER = OrderType.OFFER.value
NUM_ROUNDS = 5
R = .1
MARGIN_RATIO = .6
MARGIN_PREM = .25
MARGIN_TARGET = .3

b_10_05 = Order(order_type=BID, price=10, quantity=5)
b_10_06 = Order(order_type=BID, price=10, quantity=6)
b_11_05 = Order(order_type=BID, price=11, quantity=5)
b_11_06 = Order(order_type=BID, price=11, quantity=6)

o_05_05 = Order(order_type=OFFER, price=5, quantity=5)
o_05_06 = Order(order_type=OFFER, price=5, quantity=6)
o_06_05 = Order(order_type=OFFER, price=6, quantity=5)
o_06_07 = Order(order_type=OFFER, price=6, quantity=7)

all_orders = [b_10_05, b_10_06, b_11_05, b_11_06, o_05_05, o_05_06, o_06_05, o_06_07]

def basic_player():
    return Player(shares=100, cash=200)


class TestDataForPlayer(unittest.TestCase):

    def test_init(self):
        # set-up
        p = basic_player()

        # Execute
        d4p = DataForPlayer(p)

        # Assert
        self.assertEqual(d4p.player, p)
        self.assertIsNone(d4p.shares_result)
        self.assertIsNone(d4p.shares_transacted)
        self.assertIsNone(d4p.trans_cost)
        self.assertIsNone(d4p.cash_after_trade)
        self.assertIsNone(d4p.dividend_earned)
        self.assertIsNone(d4p.interest_earned)
        self.assertIsNone(d4p.cash_result)
        self.assertFalse(d4p.margin_violation_future)

    def test_get_new_player_pos_net_buy(self):
        # Set-up
        p = basic_player()
        o1 = Order(order_type=BID, quantity_final=1)
        o2 = Order(order_type=BID, quantity_final=2)
        o3 = Order(order_type=OFFER, quantity_final=0)
        o4 = Order(order_type=OFFER, quantity_final=1)
        orders = [o1, o2, o3, o4]
        for o in orders:
            o.player = p

        d4p = DataForPlayer(p)

        # Execute
        d4p.get_new_player_position(orders, 10, R, 15)

        # Assert
        self.assertEqual(d4p.shares_transacted, 2)
        self.assertEqual(d4p.shares_result, 102)
        self.assertEqual(d4p.trans_cost, -30)
        self.assertEqual(d4p.cash_after_trade, 170)
        self.assertEqual(d4p.dividend_earned, 1020)
        self.assertEqual(d4p.interest_earned, 17)
        self.assertEqual(d4p.cash_result, 200 - 30 + 1020 + 17)

    def test_get_new_player_pos_net_sell(self):
        # Set-up
        p = basic_player()
        o1 = Order(order_type=BID, quantity_final=1)
        o2 = Order(order_type=BID, quantity_final=0)
        o3 = Order(order_type=OFFER, quantity_final=2)
        o4 = Order(order_type=OFFER, quantity_final=1)
        orders = [o1, o2, o3, o4]
        for o in orders:
            o.player = p

        d4p = DataForPlayer(p)

        # Execute
        d4p.get_new_player_position(orders, 10, R, 15)

        # Assert
        self.assertEqual(d4p.shares_transacted, -2)
        self.assertEqual(d4p.shares_result, 98)
        self.assertEqual(d4p.trans_cost, 30)
        self.assertEqual(d4p.cash_after_trade, 230)
        self.assertEqual(d4p.dividend_earned, 980)
        self.assertEqual(d4p.interest_earned, 23)
        self.assertEqual(d4p.cash_result, 200 + 30 + 980 + 23)

    def test_get_new_player_pos_no_orders(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)

        # Execute
        d4p.get_new_player_position([], 10, R, 15)

        # Assert
        self.assertEqual(d4p.shares_transacted, 0)
        self.assertEqual(d4p.shares_result, 100)
        self.assertEqual(d4p.trans_cost, 0)
        self.assertEqual(d4p.cash_after_trade, 200)
        self.assertEqual(d4p.dividend_earned, 1000)
        self.assertEqual(d4p.interest_earned, 20)
        self.assertEqual(d4p.cash_result, 200 + 0 + 1000 + 20)

    def test_is_margin_violation_zero_shares(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)
        d4p.cash_result = 10
        d4p.shares_result = 0

        # Execute
        d4p.set_mv_future(MARGIN_RATIO, 60)

        # Assert
        self.assertFalse(d4p.margin_violation_future)

    def test_is_margin_violation_pos_shares(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)
        d4p.cash_result = 100
        d4p.shares_result = 1

        # Execute
        d4p.set_mv_future(MARGIN_RATIO, 60)

        # Assert
        self.assertFalse(d4p.margin_violation_future)

    def test_is_margin_violation_neg_shares_under(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)
        d4p.cash_result = 100
        d4p.shares_result = -1

        # Execute
        d4p.set_mv_future(MARGIN_RATIO, 49)

        # Assert
        self.assertFalse(d4p.margin_violation_future)

    def test_is_margin_violation_neg_shares_over(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)
        d4p.cash_result = 100
        d4p.shares_result = -1

        # Execute
        d4p.set_mv_future(MARGIN_RATIO, 50)

        # Assert
        self.assertFalse(d4p.margin_violation_future)

    def test_get_buy_in_players(self):
        # Set-up
        p1 = Player()
        p1.periods_until_auto_buy = 1
        p2 = Player()
        p2.periods_until_auto_buy = None
        p3 = Player()
        p3.periods_until_auto_buy = 0
        p4 = Player()
        p4.periods_until_auto_buy = 0

        d1 = DataForPlayer(p1)
        d1.margin_violation_future = False
        d2 = DataForPlayer(p2)
        d2.margin_violation_future = True
        d3 = DataForPlayer(p3)
        d3.margin_violation_future = False
        d4 = DataForPlayer(p4)
        d4.margin_violation_future = True

        # Execute / Assert
        self.assertFalse(d1.is_buy_in_required())
        self.assertFalse(d2.is_buy_in_required())
        self.assertFalse(d3.is_buy_in_required())
        self.assertTrue(d4.is_buy_in_required())

    def test_generate_buy_in_order(self):
        # Set-up
        p = basic_player()
        d4p = DataForPlayer(p)
        d4p.shares_result = -10
        d4p.cash_result = 1000

        # Execute
        o = d4p.generate_buy_in_order(60, MARGIN_PREM, MARGIN_TARGET)

        # Assert
        self.assertTrue(o.is_buy_in)
        self.assertEqual(o.order_type, BID)
        self.assertEqual(o.price, 75)
        self.assertEqual(o.quantity, 6)


class TestDataForOrder(unittest.TestCase):
    def basic_setup(self):
        g = Group()
        p = basic_player()
        p.group = g
        o = Order(player=p, group=g, order_type=BID, price=10, quantity=5)
        o.quantity_final = 0
        o.id = -999
        return g, o, p

    def test_init_null(self):
        # Setup / Execute
        d4o = DataForOrder()

        # Assert
        self.assertIsNone(d4o.order)
        self.assertIsNone(d4o.id)
        self.assertIsNone(d4o.player)
        self.assertIsNone(d4o.group)
        self.assertIsNone(d4o.order_type)
        self.assertIsNone(d4o.price)
        self.assertIsNone(d4o.quantity)
        self.assertEqual(d4o.quantity_final, 0)
        self.assertFalse(d4o.is_buy_in)

    def test_init_not_null(self):
        # Set up
        g, o, p = self.basic_setup()

        # Execute
        d4o = DataForOrder(o=o)

        # Assert
        self.assertEqual(d4o.order, o)
        self.assertEqual(d4o.id, -999)
        self.assertEqual(d4o.player, p)
        self.assertEqual(d4o.group, g)
        self.assertEqual(d4o.price, 10)
        self.assertEqual(d4o.quantity, 5)
        self.assertEqual(d4o.quantity_final, 0)
        self.assertFalse(d4o.is_buy_in)

    def test_update_order(self):
        # Set up
        g, o, p = self.basic_setup()
        d4o = DataForOrder(o=o)

        # Execute
        d4o.quantity_final = -7777
        d4o.is_buy_in = True
        d4o.update_order()

        # Assert
        self.assertEqual(d4o.order, o)
        self.assertEqual(o.id, -999)
        self.assertEqual(o.player, p)
        self.assertEqual(o.group, g)
        self.assertEqual(o.price, 10)
        self.assertEqual(o.quantity, 5)
        self.assertTrue(o.is_buy_in)
        self.assertEqual(o.quantity_final, -7777)

    def test_update_order_None(self):
        # Setup
        d4o = DataForOrder()
        g, throw_away, p = self.basic_setup()

        d4o.player = p
        d4o.group = g
        d4o.order_type = OFFER
        d4o.price = -54
        d4o.quantity = -55
        d4o.quantity_final = -56
        d4o.is_buy_in = True

        # Execute
        d4o.update_order()
        o = d4o.order

        # Assert
        self.assertIsNotNone(o)
        self.assertEqual(o.player, p)
        self.assertEqual(o.group, g)
        self.assertEqual(o.price, -54)
        self.assertEqual(o.quantity, -55)
        self.assertTrue(o.is_buy_in)
        self.assertEqual(o.quantity_final, -56)

    def test_get_total_quantity(self):
        self.assertEqual(CallMarket.get_total_quantity(all_orders), 45)
        self.assertEqual(CallMarket.get_total_quantity([]), 0)
        self.assertEqual(CallMarket.get_total_quantity(None), 0)
