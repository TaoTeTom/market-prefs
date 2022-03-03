import sys
import unittest

from otree import database
from otree.bots.bot import ExpectError

from rounds import *

BUY = -1
SELL = 1


def run_unit_tests():
    suite = unittest.defaultTestLoader.discover('rounds/test')
    print("\n===========================\nRUNNING UNIT TESTS")
    # for s in suite:
    #    for t in s:
    #        for i in t:
    #            print("TEST", i, "\n")

    ttr = unittest.TextTestRunner(stream=sys.stdout)
    ttr.run(suite)
    database.db.rollback()
    print("\n FINISHED UNIT TESTS\n===========================\n\n")


def test_get_orders_for_player(method, id_, expected_num):
    res = method(id_, {'func': 'get_orders_for_player'})

    ret_dict = res.get(id_)
    expect(ret_dict.get('func'), 'order_list')
    orders = ret_dict.get('orders')
    expect(len(orders), expected_num)
    return orders


def test_delete_order(method, player_id, oid):
    method(player_id, {'func': 'delete_order', 'oid': oid})


def run_order_placement_coverage_tests(method):
    # First test errors codes for rejecting order problems
    # test order deletion
    # generate some sell orders for player 1 and delete them.
    test_place_order(method, 2, '1', '12', '6')
    test_place_order(method, 2, '1', '12', '6')

    orders = test_get_orders_for_player(method, 2, 2)
    # we'll delete the sell orders for this player
    for o in orders:
        if o.get('type') == 1:
            test_delete_order(method, 2, o.get('oid'))
    test_get_orders_for_player(method, 2, 0)

    # expecting rejected orders
    test_place_order(method, 2, '2', '50', '10', valid=False, code_expect=OrderErrorCode.BAD_TYPE)
    # test_place_order(method, 2, '1', 'a', '10', valid=False, code_expect=OrderErrorCode.PRICE_NOT_NUM)
    test_place_order(method, 2, '1', '-1', '10', valid=False, code_expect=OrderErrorCode.PRICE_NEGATIVE)
    test_place_order(method, 2, '1', '50', 'a', valid=False, code_expect=OrderErrorCode.QUANT_NOT_NUM)
    test_place_order(method, 2, '1', '50', '-1', valid=False, code_expect=OrderErrorCode.QUANT_NEGATIVE)
    # test_place_order(method, 2, '2', 'a', '-1', valid=False, code_expect=22)
    test_place_order(method, 2, '2', '-1', 'a', valid=False, code_expect=25)


#############################################################################################################
class Actor:
    def __init__(self, name: str):
        self.player = None
        self.rounds = {}
        self.name = name

    def round(self, round_number):
        actor_round = ActorRound(round_number)
        self.rounds[round_number] = actor_round
        return actor_round

    def for_round(self, round_number):
        return self.rounds.get(round_number)


class ActorRound:
    def __init__(self, round_number):
        self.round_number = round_number
        self.orders = []
        self.cash = None
        self.shares = None
        self.expect_values = {}

    # Configure Interface
    def set(self, cash, shares):
        self.cash = cash
        self.shares = shares
        return self

    def buy(self, shares, at=None):
        self._store_order(BUY, shares, at)
        return self

    def sell(self, shares, at=None):
        self._store_order(SELL, shares, at)
        return self

    def expect(self, **kwargs):
        self.expect_values.update(kwargs)
        return self

    # Round Interface
    def do_set(self):
        return self.cash is not None and self.shares is not None

    def expects_any(self):
        return len(self.expect_values.keys()) > 0

    def expects(self, key):
        return key in self.expect_values

    # Helpers
    def _store_order(self, otype, shares, price):
        self.orders.append(dict(otype=otype, shares=shares, price=price))


class MarketTests:
    def __init__(self):
        self.rounds = {}  # round number to MarketRound
        self.part_id_to_actor_name = {}  # participant id to actor name
        self.name_to_player = {}
        self.actor_names = set()  # set of actor names

    # Bot Interface
    def attach_actors(self, players):
        for name, player in zip(self.actor_names, players):
            part_id = player.participant.code
            self.part_id_to_actor_name[part_id] = name
            self.name_to_player[name] = player

    def get_actor_name(self, player):
        part_id = player.participant.code
        name = self.part_id_to_actor_name.get(part_id)

        return name

    def for_round(self, round_number):
        """
        Gets the set of actor-actions for the given round number
        @param round_number: The round number
        @return: MarketRound The market round for the given round number
        """
        return self.rounds.get(round_number)

    def for_player_and_round(self, player, round_number):
        """
        Get the player actions for the given player in the given round
        @param round_number: the given round number
        @param player: the given player
        @return: ActorRound for the player in this round
        """
        mr: MarketRound = self.for_round(round_number)
        if not mr:
            return None

        name = self.get_actor_name(player)
        return mr.actions_for_actor(name)

    def get_num_defined_rounds(self):
        return len(self.rounds.keys())

    # Config Interface
    def round(self, round_number):
        market_round = MarketRound(self, round_number)
        self.rounds[round_number] = market_round
        return market_round


class MarketRound:
    def __init__(self, tests: MarketTests, round_number):
        self.tests = tests
        self.round_number = round_number
        self.player_actions = {}  # ActionRounds  - The player actions for a particular round
        self.expect_values = {}

    # Configuration Interface
    def expect(self, **kwargs):
        self.expect_values.update(kwargs)
        return self

    def actor(self, name: str, setup):
        ar = ActorRound(self.round_number)
        # tell the MarketTest object about this
        self.tests.actor_names.add(name)
        self.player_actions[name] = ar
        setup(ar)
        return self

    def finish(self):
        return self.tests

    # Bot Interface
    def actions_for_actor(self, name):
        return self.player_actions.get(name)

    def expects_any(self):
        return len(self.expect_values.keys()) > 0

    def expects(self, key):
        return key in self.expect_values


#############################################################################################################
class ScriptedBot(Bot):
    first_time = True
    number_of_bots_in_round = defaultdict(int)
    errors_by_round = defaultdict(list)

    def play_round(self):
        # The first time we get here, we need to assign players to all the actor objects
        if self.first_time:
            ScriptedBot.first_time = False
            market.attach_actors(self.group.get_players())
            run_unit_tests()

        round_number = self.round_number
        # exit if we are past the defined rounds
        if round_number > market.get_num_defined_rounds() + 1:
            return

        ScriptedBot.number_of_bots_in_round[round_number] += 1
        number_of_bots = len(self.group.get_players())
        num_bots_already_in_round = ScriptedBot.number_of_bots_in_round[round_number]
        last_bot_in_round = number_of_bots == num_bots_already_in_round

        player = self.player
        actor_name = market.get_actor_name(player)
        this_round: ActorRound = market.for_player_and_round(player, round_number)
        last_round: ActorRound = market.for_player_and_round(player, round_number - 1)

        # last round tests are usually to test market results
        if last_round:
            print(f"Player Tests: {actor_name}")
            self.last_round_tests(last_round)

        # market level tests
        # and present all test errors for that round
        last_round_market: MarketRound = market.for_round(round_number - 1)
        if last_round_market and last_bot_in_round:
            print(f"Market-level Tests")
            self.last_round_market_tests(last_round_market)
            self.show_errors()

        # display the round number after finishing off the last round
        if last_bot_in_round:
            print(f"===========\n\tROUND {round_number}")

        # Set up Player for round
        if this_round and this_round.do_set():
            player.cash = this_round.cash
            player.shares = this_round.shares

        yield Market
        if this_round:
            self.after_market_page_tests(actor_name, this_round)

    def last_round_tests(self, actions):
        if not actions.expects_any():
            return

        player = self.player
        for var in vars(player):
            self.test_object_attribute(player, actions, var)

    def after_market_page_tests(self, actor, actions):
        pass

    def init_tests(self):
        pass

    def last_round_market_tests(self, last_round_market: MarketRound):
        if not last_round_market.expects_any():
            return

        if self.round_number > 1:
            group = self.group.in_round(self.round_number - 1)
            for var in vars(group):
                self.test_object_attribute(group, last_round_market, var)

    def test_object_attribute(self, obj, actions, attr):
        if not actions.expects(attr):
            return

        print(f"in round {actions.round_number}: testing: ", attr)
        actual = obj.field_maybe_none(attr)
        expected = actions.expect_values.get(attr)

        # Collect error for this attribute and save it on the object
        error = None
        try:
            expect(actual, expected)
        except ExpectError as err:
            if type(obj) is Group:
                error = f"In round {actions.round_number}: Testing {attr}: {err}"
            if type(obj) is Player:
                actor_name = market.get_actor_name(obj)
                error = f"Round {actions.round_number}: Actor {actor_name}: Testing {attr}: {err}"

        # Save away the error
        if error:
            ScriptedBot.errors_by_round[self.round_number].append(error)

    def show_errors(self):
        errors = ScriptedBot.errors_by_round[self.round_number]
        if errors:
            msg = "\n".join(errors)
            raise ExpectError(msg)


# LIVE METHOD TESTS
def test_place_order(method, id_, type_, price, quant, valid=True, code_expect=None):
    _price = str(price)
    _quant = str(quant)
    _type = str(type_)
    res = method(id_, {'func': 'submit-order', 'data': {'type': _type, 'price': _price, 'quantity': _quant}})
    data = res.get(id_)

    if type(code_expect) is OrderErrorCode:
        code_expect = code_expect.value

    if valid:
        expect(data.get('func'), 'order_confirmed')
        expect(data.get('order_id'), '>', 0)
    else:
        code_actual = data.get('error_code')
        expect(data.get('func'), 'order_rejected')

        expect(code_actual, code_expect)

    return res


def call_live_method(method, **kwargs):
    round_number = kwargs.get('round_number')
    group: Group = kwargs.get('group')

    if round_number > market.get_num_defined_rounds():
        return

    # Run coverage tests in the first round
    if round_number == 1:
        run_order_placement_coverage_tests(method)

    for player in group.get_players():
        ar: ActorRound = market.for_player_and_round(player, round_number)
        for o in ar.orders:
            test_place_order(method, player.id_in_group, o['otype'], o['price'], o['shares'])


#############################################################################################################
market = MarketTests().round(1) \
    .expect(price=500, volume=1) \
    .actor("Buyer", lambda ar: ar.set(1000, 5)
           .buy(1, at=500)
           .expect(cash=500, shares=6, periods_until_auto_buy=-99)) \
    .actor("Seller", lambda ar: ar.set(1000, 5)
           .sell(1, at=500)
           .expect(cash=1500, shares=4, periods_until_auto_buy=-99)) \
    .actor("Treated", lambda ar: ar.set(2000, -2)
           .expect(cash=2000, shares=-2, periods_until_auto_buy=0)) \
    .finish() \
    .round(2) \
    .expect(price=500, volume=0) \
    .actor("Buyer", lambda ar: ar.expect(cash=500, shares=6, periods_until_auto_buy=-99)) \
    .actor("Seller", lambda ar: ar.expect(cash=1500, shares=4, periods_until_auto_buy=-99,
                                          interest_earned=None, dividend_earned=None)) \
    .actor("Treated", lambda ar: ar.expect(cash=2000, shares=-2, periods_until_auto_buy=0)) \
    .finish() \
    .round(3) \
    .expect(price=550, volume=1) \
    .actor("Buyer", lambda ar: ar.expect(cash=500, shares=6, periods_until_auto_buy=-99)) \
    .actor("Seller", lambda ar: ar.sell(1, at=500)
           .expect(cash=2050, shares=3, periods_until_auto_buy=-99)) \
    .actor("Treated", lambda ar: ar.expect(cash=1450, shares=-1, periods_until_auto_buy=-99)) \
    .finish() \
    .round(4) \
    .expect(price=500, volume=1) \
    .actor("Buyer", lambda ar: ar.set(2000, 5)
           .buy(1, at=500)
           .expect(cash=1500, shares=6, periods_until_auto_sell=-99)) \
    .actor("Seller", lambda ar: ar.set(1000, 5)
           .sell(1, at=500)
           .expect(cash=1500, shares=4, periods_until_auto_sell=-99)) \
    .actor("Treated", lambda ar: ar.set(-1000, 4)
           .expect(cash=-1000, shares=4, periods_until_auto_sell=0, periods_until_auto_buy=-99)) \
    .finish() \
    .round(5) \
    .expect(price=500, volume=0) \
    .actor("Buyer", lambda ar: ar.expect(cash=1500, shares=6, periods_until_auto_buy=-99)) \
    .actor("Seller", lambda ar: ar.expect(cash=1500, shares=4, periods_until_auto_buy=-99)) \
    .actor("Treated", lambda ar: ar.expect(cash=-1000, shares=4, periods_until_auto_sell=0)) \
    .finish() \
    .round(6) \
    .expect(price=450, volume=2) \
    .actor("Buyer", lambda ar: ar.buy(4, at=450)
           .expect(cash=600, shares=8, periods_until_auto_sell=-99)) \
    .actor("Seller", lambda ar: ar.expect(cash=1500, shares=4, periods_until_auto_sell=-99)) \
    .actor("Treated", lambda ar: ar.expect(cash=-100, shares=2, periods_until_auto_sell=-99)) \
    .finish()
