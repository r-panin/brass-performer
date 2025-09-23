from ...schema import BoardState, Action, Player, ActionType, ActionContext, CardType, ResourceAction, ResourceAmounts, BuildAction, SellAction, NetworkAction, DevelopAction, IndustryType, Building, ResourceType
from collections import defaultdict
from .services.event_bus import EventBus, StateChangeEvent
from deepdiff import DeepDiff
from copy import deepcopy
from .turn_manager import TurnManager
import logging

class StateChanger:

    SINGULAR_ACTION_TYPES = (ActionType.BUILD, ActionType.LOAN, ActionType.PASS, ActionType.SCOUT)
    DOUBLE_ACTION_TYPES = (ActionType.DEVELOP, ActionType.NETWORK)
    MULTIPLE_ACTION_TYPES = (ActionType.SELL, ActionType.SHORTFALL)

    def __init__(self, starting_state, event_bus:EventBus=None):
        self.event_bus = event_bus
        self.turn_manager = TurnManager(starting_state, event_bus)

    def apply_action(self, action:Action, state:BoardState, player:Player):
        # Готовимся слать дифф
        logging.debug(f"=============================================")
        logging.debug(f"Action start action count: {state.actions_left}")
        logging.debug(f'Received action {action} from player {player.color}')
        if self.event_bus:
            initial_state = deepcopy(state)

        # Убираем карту если есть
        if action.card_id is not None and isinstance(action.card_id, int):
            card = player.hand.pop(action.card_id)
            logging.debug(f'Player {player.color} removed a card {action.card_id} during the action {type(action)} during turn {self.turn_manager.round_count}')
            if card.value != 'wild':
                state.discard.append(card)

        # Обрабатываем выбор ресурсов
        if isinstance(action, ResourceAction):
            market_amounts = defaultdict(int)
            for resource in action.resources_used:
                if resource.building_slot_id is not None:
                    building = state.get_building_slot(resource.building_slot_id).building_placed
                    building.resource_count -= 1
                    if building.resource_count == 0:
                        building.flipped = True
                        owner = state.players[building.owner]
                        owner.income_points += building.income
                        owner.recalculate_income()

                elif resource.merchant_slot_id is not None:
                    merchant = state.get_merchant_slot(resource.merchant_slot_id)
                    merchant.beer_available = False

                else:
                    market_amounts[resource.resource_type] += 1

            market_cost = 0
            for rtype, amount in market_amounts.items():
                market_cost += state.market.purchase_resource(rtype, amount)
            base_cost = self._get_resource_amounts(state, action, player).money
            spent = base_cost + market_cost
            player.bank -= spent
            player.money_spent += spent

        # Изменения специфичные для действий
        if action.action is ActionType.PASS:
            pass # lmao

        elif action.action is ActionType.LOAN:
            player.income -= 3
            player.bank += 30
            player.recalculate_income(keep_points=False)

        elif action.action is ActionType.SCOUT:
            for card_id in action.card_id:
                state.discard.append(player.hand[card_id])
                logging.debug(f'Player {player.color} removed a card {action.card_id} during the action {type(action)} during turn {self.turn_manager.round_count}')
                player.hand.pop(card_id)
            city_joker = next(j for j in state.wilds if j.card_type == CardType.CITY)
            ind_joker = next(j for j in state.wilds if j.card_type == CardType.INDUSTRY)

            player.hand[city_joker.id] = city_joker
            player.hand[ind_joker.id] = ind_joker
        
        elif action.action is ActionType.DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building.id)
            state.action_context = ActionContext.DEVELOP

        elif action.action is ActionType.NETWORK:
            state.links[action.link_id].owner = player.color
            state.action_context = ActionContext.NETWORK

        elif action.action is ActionType.SELL:
            building = state.get_building_slot(action.slot_id).building_placed
            building.flipped = True
            owner = state.players[building.owner]
            owner.income_points += building.income
            for resource in action.resources_used:
                if resource.merchant_slot_id is not None:
                    slot = state.get_merchant_slot(resource.merchant_slot_id)
                    self._award_merchant(state, slot.city, player)
                    slot.beer_available = False
            owner.recalculate_income()
            state.action_context = ActionContext.SELL

        elif action.action is ActionType.BUILD:
            building = player.get_lowest_level_building(action.industry)
            building.slot_id = action.slot_id
            state.get_building_slot(action.slot_id).building_placed = player.available_buildings.pop(building.id)
            self._sell_to_market(state, building)

        elif action.action is ActionType.SHORTFALL:
            logging.debug('Entering shortfall')
            if action.slot_id:
                logging.info("Manual shortfall resolution")
                slot = state.get_building_slot(action.slot_id)
                rebate = slot.building_placed.cost['money'] // 2
                player.bank += rebate
                slot.building_placed = None
                logging.info(f"AFTER CHANGE: Player vp: {player.victory_points}, bank: {player.bank}")
            else:
                logging.info("Automatic shortfall resolution")
                logging.info(f"BEFORE CHANGE: Player vp: {player.victory_points}, bank: {player.bank}")
                player.victory_points += player.bank
                player.bank = 0
                logging.info(f"AFTER CHANGE: Player vp: {player.victory_points}, bank: {player.bank}")
            if state.in_shortfall():
                state.action_context = ActionContext.SHORTFALL
            else:
                state.action_context = ActionContext.MAIN
            
        if not action.action is ActionType.SHORTFALL:
            state.subaction_count += 1
        
        if action.action is ActionType.COMMIT:
            self._commit_action(state)

        logging.debug(f"Subaction count: {state.subaction_count}")
        # определяем actioncontext
        if action.action in self.SINGULAR_ACTION_TYPES:
            self._commit_action(state)
        elif action.action in self.DOUBLE_ACTION_TYPES and state.subaction_count > 1:
            if state.action_context is ActionContext.GLOUCESTER_DEVELOP:
                state.action_context = ActionContext.SELL
            else:
                self._commit_action(state)

        if state.actions_left == 0:
            state = self.turn_manager.prepare_next_turn(state)
        
        if self.event_bus:
            diff = DeepDiff(initial_state.model_dump(), state.model_dump())
            self.event_bus.publish(StateChangeEvent(
                actor=player.color,
                diff=diff
            ))
        logging.debug(f"Action end action count: {state.actions_left}")
        logging.debug(f"=============================================")

    def _commit_action(self, state:BoardState):
        logging.debug(f"Committing action")
        state.action_context = ActionContext.MAIN
        state.actions_left -= 1
        state.subaction_count = 0

    def _sell_to_market(self, state:BoardState, building:Building) -> None:
        if building.industry_type not in (IndustryType.COAL, IndustryType.IRON):
            return
        if building.industry_type is IndustryType.COAL and not state.market_access_exists(state.get_building_slot(building.slot_id).city):
            return
        rt = ResourceType(building.industry_type)
        sold_amount = min(building.resource_count, state.market.sellable_amount(rt))
        if sold_amount <= 0 :
            return
        profit = state.market.sell_resource(ResourceType(building.industry_type), sold_amount)
        state.players[building.owner].bank += profit
        building.resource_count -= sold_amount

    def _award_merchant(self, state:BoardState, city_name:str, player:Player) -> None:
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
                state.action_context = ActionContext.GLOUCESTER_DEVELOP

    
    def _get_resource_amounts(self, state:BoardState, action:ResourceAction, player:Player) -> ResourceAmounts:
        if isinstance(action, BuildAction):
            building = player.get_lowest_level_building(action.industry)
            return building.get_cost()
        elif isinstance(action, SellAction):
            building = state.get_building_slot(action.slot_id).building_placed
            return ResourceAmounts(beer=building.sell_cost)
        elif isinstance(action, NetworkAction):
            return state.get_link_cost(subaction_count=state.subaction_count)
        elif isinstance(action, DevelopAction):
            return state.get_develop_cost()
        else:
            raise ValueError("Unknown resource action")
