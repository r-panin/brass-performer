from .game_state_manager import GameStateManager
from ...schema import ParameterAction, Player, ActionContext, CardType, ResourceAction, ResourceAmounts, ResolveShortfallAction, BuildSelection, SellSelection, NetworkSelection, DevelopSelection
from collections import defaultdict
from .services.event_bus import EventBus, StateChangeEvent
from deepdiff import DeepDiff
from copy import deepcopy

class StateChanger:

    def __init__(self, state_manager:GameStateManager, event_bus:EventBus):
        self.state_manager = state_manager
        self.event_bus = event_bus

    @property
    def state(self):
        return self.state_manager.current_state
    
    def apply_action(self, action:ParameterAction, player:Player):
        initial_state = deepcopy(self.state)
        if action.card_id is not None:
            card = player.hand.pop(action.card_id)
            if card.value != 'wild':
                self.state.discard.append(card)
            else:
                self.state.wild_deck.append(card)

        if isinstance(action, ResourceAction):
            market_amounts = defaultdict(int)
            for resource in action.resources_used:
                if resource.building_slot_id is not None:
                    building = self.state.get_building_slot(resource.building_slot_id).building_placed
                    building.resource_count -= 1
                    if building.resource_count == 0:
                        building.flipped = True
                        owner = self.state.players[building.owner]
                        owner.income_points += building.income
                        owner.recalculate_income()

                elif resource.merchant_slot_id is not None:
                    merchant = self.state.get_merchant_slot(resource.merchant_slot_id)
                    merchant.beer_available = False

                else:
                    market_amounts[resource.resource_type] += 1

            market_cost = 0
            for rtype, amount in market_amounts.items():
                market_cost += self.state.market.purchase_resource(rtype, amount)
            base_cost = self.get_resource_amounts(action, player).money
            spent = base_cost + market_cost
            player.bank -= spent
            player.money_spent += spent

        if self.state_manager.action_context is ActionContext.PASS:
            return

        elif self.state_manager.action_context is ActionContext.LOAN:
            player.income -= 3
            player.bank += 30
            player.recalculate_income(keep_points=False)
            return

        elif self.state_manager.action_context is ActionContext.SCOUT:
            for card_id in action.card_id:
                self.state.discard.append(player.hand[card_id])
                player.hand.pop(card_id)
            city_joker = next(j for j in self.state.wild_deck if j.card_type == CardType.CITY)
            ind_joker = next(j for j in self.state.wild_deck if j.card_type == CardType.INDUSTRY)
            player.hand[city_joker.id] = city_joker
            player.hand[ind_joker.id] = ind_joker
            return
        
        elif self.state_manager.action_context is ActionContext.DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building.id)

        elif self.state_manager.action_context is ActionContext.GLOUCESTER_DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building.id)
            self.state_manager.exit_gloucester_develop()

        elif self.state_manager.action_context is ActionContext.NETWORK:
            self.state.links[action.link_id].owner = player.color

        elif self.state_manager.action_context is ActionContext.SELL:
            building = self.state.get_building_slot(action.slot_id).building_placed
            building.flipped = True
            owner = self.state.players[building.owner]
            owner.income_points += building.income
            for resource in action.resources_used:
                if resource.merchant_slot_id is not None:
                    slot = self.state.get_merchant_slot(resource.merchant_slot_id)
                    self._award_merchant(slot.city, player)
                    slot.beer_available = False
            owner.recalculate_income()

        elif self.state_manager.action_context is ActionContext.BUILD:
            building = player.get_lowest_level_building(action.industry)
            building.slot_id = action.slot_id
            self.state.get_building_slot(action.slot_id).building_placed = player.available_buildings.pop(building.id)
        
        diff = DeepDiff(initial_state.model_dump(), self.state.model_dump())
        self.event_bus.publish(StateChangeEvent(
            actor=player.color,
            diff=diff
        ))

    def _award_merchant(self, city_name:str, player:Player) -> None:
        match city_name:
            case "Warrington":
                player.bank += 5
            case "Nottingham":
                player.victory_points += 3
            case "Shrewsbury":
                player.victory_points += 4
            case "Oxford":
                player.income_points += 2
            case "Gloucester": # fug
                self.state_manager.enter_gloucester_develop()


    def resolve_shortfall(self, action:ResolveShortfallAction, player:Player) -> None:
        initial_state = deepcopy(self.state)
        if action.slot_id:
            slot = self.state.get_building_slot(action.slot_id)
            rebate = slot.building_placed.cost['money'] // 2
            player.bank += rebate
            slot.building_placed = None
        else:
            player.victory_points += player.bank
            player.bank = 0
        diff = DeepDiff(initial_state.model_dump(), self.state.model_dump())
        self.event_bus.publish(StateChangeEvent(
            actor=player.color,
            diff=diff
        ))
        return
    
    def get_resource_amounts(self, action:ResourceAction, player:Player) -> ResourceAmounts:
        if isinstance(action, BuildSelection):
            building = player.get_lowest_level_building(action.industry)
            return building.get_cost()
        elif isinstance(action, SellSelection):
            building = self.state.get_building_slot(action.slot_id).building_placed
            return ResourceAmounts(beer=building.sell_cost)
        elif isinstance(action, NetworkSelection):
            return self.state.get_link_cost(subaction_count=self.state_manager.subaction_count)
        elif isinstance(action, DevelopSelection):
            return self.state.get_develop_cost()
        else:
            raise ValueError("Unknown resource action")
