import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from rounds.call_market import CallMarket, get_total_quantity
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


class TestCallMarket(unittest.TestCase):

    def basic_group(self):
        group = Group()
        config_settings = dict(
            interest_rate=R
            , margin_ratio=MARGIN_RATIO
            , margin_premium=MARGIN_PREM
            , margin_target_ratio=MARGIN_TARGET)
        session = MagicMock()
        session.config = config_settings
        group.session = session

        return group

    def basic_setup(self, orders=all_orders):
        with patch.object(CallMarket, 'get_last_period_price', return_value=47) as mock_method:
            with patch.object(Order, 'filter', return_value=orders) as filter_mock:
                Order.filter = MagicMock(return_value=orders)
                group = self.basic_group()
                cm = CallMarket(group, NUM_ROUNDS)
        return cm

    def test_init(self):
        # Set up and
        with patch.object(CallMarket, 'get_last_period_price', return_value=47) as mock_method:
            with patch.object(Order, 'filter', return_value=all_orders) as filter_mock:
                group = self.basic_group()

                # Execute
                cm = CallMarket(group, NUM_ROUNDS)

                # assert
                self.assertEqual(cm.num_rounds, NUM_ROUNDS)
                self.assertEqual(cm.group, group)
                self.assertEqual(cm.session, group.session)
                self.assertEqual(cm.bids, [b_10_05, b_10_06, b_11_05, b_11_06])
                self.assertEqual(cm.offers, [o_05_05, o_05_06, o_06_05, o_06_07])
                Order.filter.assert_called_with(group=group)
                self.assertEqual(cm.last_price, 47)
                CallMarket.get_last_period_price.assert_called_with()
                self.assertEqual(cm.interest_rate, R)
                self.assertEqual(cm.margin_ratio, MARGIN_RATIO)
                self.assertEqual(cm.margin_premium, MARGIN_PREM)
                self.assertEqual(cm.margin_target_ratio, MARGIN_TARGET)

    def test_get_orders_for_group(self):
        with patch.object(Order, 'filter', return_value=all_orders) as filter_mock:
            # Set-up
            cm = self.basic_setup()
            group = cm.group

            # Execute
            bids, offers = cm.get_orders_for_group()

            # Assert
            self.assertEqual(bids, [b_10_05, b_10_06, b_11_05, b_11_06])
            self.assertEqual(offers, [o_05_05, o_05_06, o_06_05, o_06_07])
            Order.filter.assert_called_with(group=cm.group)

    def test_get_orders_for_group_bids(self):
        orders = [b_10_05, b_10_06, b_11_05, b_11_06]
        with patch.object(Order, 'filter', return_value=orders) as filter_mock:
            # Set-up
            cm = self.basic_setup(orders=orders)
            group = cm.group

            # Execute
            bids, offers = cm.get_orders_for_group()

            # Assert
            self.assertEqual(bids, [b_10_05, b_10_06, b_11_05, b_11_06])
            self.assertEqual(offers, [])
            Order.filter.assert_called_with(group=cm.group)

    def test_get_orders_for_group_offers(self):
        orders = [o_05_05, o_05_06, o_06_05, o_06_07]
        with patch.object(Order, 'filter', return_value=orders) as filter_mock:
            # Set-up
            cm = self.basic_setup(orders=orders)
            group = cm.group

            # Execute
            bids, offers = cm.get_orders_for_group()

            # Assert
            self.assertEqual(bids, [])
            self.assertEqual(offers, [o_05_05, o_05_06, o_06_05, o_06_07])
            Order.filter.assert_called_with(group=cm.group)

    def test_get_last_period_price_round_1(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.round_number = 1
        cm.get_fundamental_value = MagicMock(return_value=800)
        group.in_round = MagicMock(return_value=None)

        # Execute
        last_price = cm.get_last_period_price()

        # Assert
        self.assertEqual(last_price, 800)
        cm.get_fundamental_value.assert_called_with()
        group.in_round.assert_not_called()

    def test_get_last_period_price_round_2(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.round_number = 2

        cm.get_fundamental_value = MagicMock(return_value=800)
        last_round_group = self.basic_group()
        last_round_group.round_number = 1
        last_round_group.price = 801.1
        group.in_round = MagicMock(return_value=last_round_group)

        # Execute
        last_price = cm.get_last_period_price()

        # Assert
        self.assertEqual(last_price, 801)
        cm.get_fundamental_value.assert_not_called()
        group.in_round.assert_called_with(1)

    def test_set_up_future_player_last_round(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group

        player = Player(round_number=NUM_ROUNDS)
        player.in_round = MagicMock(return_value=None)

        # Execute
        cm.set_up_future_player(player)

        # Assert
        player.in_round.assert_not_called()

    def test_set_up_future_player_penultimate_round(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group

        player = Player(round_number=NUM_ROUNDS - 1
                        , cash_result=123
                        , shares_result=456
                        , margin_violation=True
                        )
        next_player = Player(round_number=NUM_ROUNDS)
        player.in_round = MagicMock(return_value=next_player)

        # Execute
        cm.set_up_future_player(player, margin_violation=True)

        # Assert
        player.in_round.assert_called_with(NUM_ROUNDS)
        self.assertEqual(next_player.cash, 123)
        self.assertEqual(next_player.shares, 456)
        self.assertTrue(next_player.margin_violation)

    def test_get_dividend(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.session.config.update(dict(div_dist='0.5 0.5', div_amount='40 100'))

        # Execute
        reps = 100000
        s = sum((cm.get_dividend() for i in range(reps)))
        avg = s / reps

        # Assert
        self.assertTrue(abs(avg - 70) < 0.2,
                        msg="Expecting the avgerage dividend to be around 70, instead it was: {}".format(avg))

    def test_get_fundamental_value_r0(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.session.config.update(dict(div_dist='0.5 0.5'
                                         , div_amount='40 100'
                                         , interest_rate=0))

        # Execute
        f = cm.get_fundamental_value()

        # Assert
        self.assertEqual(f, 0)

    def test_get_fundamental_value(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.session.config.update(dict(div_dist='0.5 0.5'
                                         , div_amount='0 100'
                                         , interest_rate=0.1))

        # Execute
        f = cm.get_fundamental_value()

        # Assert
        self.assertEqual(f, 500)

    def test_get_fundamental_value_exp_relevant(self):
        # Set-up
        cm = self.basic_setup()
        group = cm.group
        group.session.config.update(dict(div_dist='0.5 0.5'
                                         , div_amount='40 100'
                                         , interest_rate=0.05))

        # Execute
        f = cm.get_fundamental_value()

        # Assert
        self.assertEqual(f, 1400)