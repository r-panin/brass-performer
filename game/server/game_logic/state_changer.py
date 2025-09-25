from ...schema import City, Action, Player, ActionType, ActionContext, CardType, ResourceAction, ResourceAmounts, BuildAction, SellAction, NetworkAction, DevelopAction, IndustryType, Building, ResourceType
from collections import defaultdict
from .services.event_bus import EventBus, StateChangeEvent
from deepdiff import DeepDiff
from copy import deepcopy
from .turn_manager import TurnManager
from .services.board_state_service import BoardStateService

class StateChanger:

    SINGULAR_ACTION_TYPES = (ActionType.BUILD, ActionType.LOAN, ActionType.PASS, ActionType.SCOUT)
    DOUBLE_ACTION_TYPES = (ActionType.DEVELOP, ActionType.NETWORK)
    MULTIPLE_ACTION_TYPES = (ActionType.SELL, ActionType.SHORTFALL)

    def __init__(self, starting_state:BoardStateService, event_bus:EventBus=None):
        self.event_bus = event_bus
        self.turn_manager = TurnManager(starting_state.state, event_bus)

    def apply_action(self, action:Action, state_service:BoardStateService, player:Player):
        # Готовимся слать дифф
        
        # Убираем карту если есть
        if action.card_id is not None and isinstance(action.card_id, int):
            card = player.hand.pop(action.card_id)
            if card.value != 'wild':
                state_service.state.discard.append(card)

        # Обрабатываем выбор ресурсов
        if isinstance(action, ResourceAction):
            market_amounts = defaultdict(int)
            for resource in action.resources_used:
                if resource.building_slot_id is not None:
                    building = state_service.get_building_slot(resource.building_slot_id).building_placed
                    building.resource_count -= 1
                    if building.resource_count == 0:
                        if building.industry_type is IndustryType.COAL:
                            state_service.invalidate_coal_cache()
                        elif building.industry_type is IndustryType.IRON:
                            state_service.invalidate_iron_cache()
                        building.flipped = True
                        owner = state_service.state.players[building.owner]
                        owner.income_points += building.income
                        state_service.recalculate_income(owner)

                elif resource.merchant_slot_id is not None:
                    merchant = state_service.get_merchant_slot(resource.merchant_slot_id)
                    merchant.beer_available = False

                else:
                    market_amounts[resource.resource_type] += 1

            market_cost = 0
            for rtype, amount in market_amounts.items():
                market_cost += state_service.purchase_resource(rtype, amount)
            base_cost = self._get_resource_amounts(state_service, action, player).money
            spent = base_cost + market_cost
            player.bank -= spent
            player.money_spent += spent

        # Изменения специфичные для действий
        if action.action is ActionType.PASS:
            pass # lmao

        elif action.action is ActionType.LOAN:
            player.income -= 3
            player.bank += 30
            state_service.recalculate_income(player, keep_points=False)

        elif action.action is ActionType.SCOUT:
            for card_id in action.card_id:
                state_service.state.discard.append(player.hand[card_id])
                player.hand.pop(card_id)
            city_joker = next(j for j in state_service.state.wilds if j.card_type == CardType.CITY)
            ind_joker = next(j for j in state_service.state.wilds if j.card_type == CardType.INDUSTRY)

            player.hand[city_joker.id] = city_joker
            player.hand[ind_joker.id] = ind_joker
        
        elif action.action is ActionType.DEVELOP:
            building = state_service.get_lowest_level_building(player.color, action.industry)
            player.available_buildings.pop(building.id)
            state_service.state.action_context = ActionContext.DEVELOP
            state_service.update_lowest_buildings(player.color)

        elif action.action is ActionType.NETWORK:
            state_service.state.links[action.link_id].owner = player.color
            state_service.state.action_context = ActionContext.NETWORK
            state_service.invalidate_connectivity_cache()
            state_service.invalidate_networks_cache()

        elif action.action is ActionType.SELL:
            building = state_service.get_building_slot(action.slot_id).building_placed
            building.flipped = True
            owner = state_service.state.players[building.owner]
            owner.income_points += building.income
            for resource in action.resources_used:
                if resource.merchant_slot_id is not None:
                    slot = state_service.get_merchant_slot(resource.merchant_slot_id)
                    self._award_merchant(state_service, slot.city, player)
                    slot.beer_available = False
            state_service.recalculate_income(player)
            state_service.state.action_context = ActionContext.SELL

        elif action.action is ActionType.BUILD:
            building = state_service.get_lowest_level_building(player.color, action.industry)
            building.slot_id = action.slot_id
            state_service.get_building_slot(action.slot_id).building_placed = player.available_buildings.pop(building.id)
            self._sell_to_market(state_service, building)
            state_service.update_lowest_buildings(player.color)
            if building.industry_type is IndustryType.COAL:
                state_service.invalidate_coal_cache()
            elif building.industry_type is IndustryType.IRON:
                state_service.invalidate_iron_cache()
            state_service.invalidate_networks_cache()

        elif action.action is ActionType.SHORTFALL:
            if action.slot_id:
                slot = state_service.get_building_slot(action.slot_id)
                rebate = slot.building_placed.cost['money'] // 2
                player.bank += rebate
                slot.building_placed = None
            else:
                player.victory_points += player.bank
                player.bank = 0
            if state_service.in_shortfall():
                state_service.state.action_context = ActionContext.SHORTFALL
            else:
                state_service.state.action_context = ActionContext.MAIN
            
        if not action.action is ActionType.SHORTFALL:
            state_service.subaction_count += 1
        
        if action.action is ActionType.COMMIT:
            self._commit_action(state_service)

        # определяем actioncontext
        if action.action in self.SINGULAR_ACTION_TYPES:
            self._commit_action(state_service)
        elif action.action in self.DOUBLE_ACTION_TYPES and state_service.subaction_count > 1:
            if state_service.state.action_context is ActionContext.GLOUCESTER_DEVELOP:
                state_service.state.action_context = ActionContext.SELL
            else:
                self._commit_action(state_service)

        if state_service.state.actions_left == 0:
            state = self.turn_manager.prepare_next_turn(state_service)
        

    def _commit_action(self, state_service:BoardStateService):
        state_service.state.action_context = ActionContext.MAIN
        state_service.state.actions_left -= 1
        state_service.subaction_count = 0

    def _sell_to_market(self, state_service:BoardStateService, building:Building) -> None:
        if building.industry_type not in (IndustryType.COAL, IndustryType.IRON):
            return
        if building.industry_type is IndustryType.COAL and not state_service.market_access_exists(state_service.get_building_slot(building.slot_id).city):
            return
        rt = ResourceType(building.industry_type)
        sold_amount = min(building.resource_count, state_service.sellable_amount(rt))
        if sold_amount <= 0 :
            return
        profit = state_service.sell_resource(ResourceType(building.industry_type), sold_amount)
        state_service.state.players[building.owner].bank += profit
        building.resource_count -= sold_amount

    def _award_merchant(self, state_service:BoardStateService, city_name:str, player:Player) -> None:
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
                state_service.state.action_context = ActionContext.GLOUCESTER_DEVELOP

    
    def _get_resource_amounts(self, state_service:BoardStateService, action:ResourceAction, player:Player) -> ResourceAmounts:
        if isinstance(action, BuildAction):
            building = state_service.get_lowest_level_building(player.color, action.industry)
            return building.get_cost()
        elif isinstance(action, SellAction):
            building = state_service.get_building_slot(action.slot_id).building_placed
            return ResourceAmounts(beer=building.sell_cost)
        elif isinstance(action, NetworkAction):
            return state_service.get_link_cost(subaction_count=state_service.subaction_count)
        elif isinstance(action, DevelopAction):
            return state_service.get_develop_cost()
        else:
            raise ValueError("Unknown resource action")

