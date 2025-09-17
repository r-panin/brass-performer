from .validation_service import ActionValidationService
from ...schema import Action, PlayerColor, ActionProcessResult, MetaAction, MetaActions, ResourceAmounts, DevelopSelection, ScoutSelection, ParameterAction, CommitAction, ActionContext, ResourceAction, AutoResourceSelection, EndOfTurnAction, GameStatus, ResolveShortfallAction, BoardState, Player, CardType, ResourceSource, ResourceStrategy, NetworkSelection, BuildSelection, SellSelection, ValidationResult, LinkType
from .game_state_manager import GamePhase, GameStateManager
import random
from collections import defaultdict
from typing import List, Dict, get_args
from .turn_manager import TurnManager


class ActionProcessor():
    ACTION_CONTEXT_MAP = {
        ActionContext.MAIN: get_args(MetaActions),
        ActionContext.AWAITING_COMMIT: (CommitAction,),
        ActionContext.BUILD: (BuildSelection,),
        ActionContext.DEVELOP: (DevelopSelection, CommitAction),
        ActionContext.NETWORK: (NetworkSelection, CommitAction),
        ActionContext.PASS: (ParameterAction,),
        ActionContext.SCOUT: (ScoutSelection,),
        ActionContext.SELL: (SellSelection, CommitAction),
        ActionContext.LOAN: (ParameterAction,),
        ActionContext.END_OF_TURN: (EndOfTurnAction,),
        ActionContext.SHORTFALL: (ResolveShortfallAction,),
        ActionContext.GLOUCESTER_DEVELOP: (DevelopSelection,)
    }

    def __init__(self, state_manager:GameStateManager):
        self.state_manager = state_manager
        self.validation_service = ActionValidationService()
        self.turn_manager = TurnManager()

    @property
    def state(self):
        return self.state_manager.current_state
    
    def is_player_to_move(self, color:PlayerColor):
        if self.state_manager.action_context is ActionContext.SHORTFALL:
            if self.state.players[color].bank < 0:
                return True
            return False
        
        if self.state.turn_order[0] != color:
            return False
        return True
    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False, message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def process_action(self, action: Action, color: PlayerColor) -> ActionProcessResult:
        # Проверяем, может ли игрок делать ход
        if not self.is_player_to_move(color):
            return ActionProcessResult(
                processed=False,
                message=f"Attempted move by {color}, current turn is {self.state.turn_order[0]}",
                awaiting={},
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )

        context_validateion = self.validate_action_context(self.state_manager.action_context, action)
        if not context_validateion.is_valid:
            return ActionProcessResult(
                processed=False,
                message=f"Attempted action {type(action)}, which current context {self.state_manager.action_context} forbids",
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )
        
        # Обрабатываем действие в зависимости от типа
        if isinstance(action, MetaAction):
            return self._process_meta_action(action, color)
        elif isinstance(action, ParameterAction):
            return self._process_parameter_action(action, color)
        elif isinstance(action, CommitAction):
            return self._process_commit_action(action, color)
        elif isinstance(action, EndOfTurnAction):
            return self._process_end_of_turn_action(action, color)
        elif isinstance(action, ResolveShortfallAction):
            return self._process_resolve_shortfall_action(action, color)
        else:
            return ActionProcessResult(
                processed=False, 
                message="Unknown action type", 
                awaiting={'W': ('T', 'F')}, 
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )

    def _process_meta_action(self, action: MetaAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase != GamePhase.MAIN:
            return ActionProcessResult(
                processed=False,
                message="Cannot submit a meta action outside of main context",
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )
        
        try:
            self.state_manager.start_transaction(ActionContext(action.action))
            return ActionProcessResult(
                processed=True,
                message=f"Entered {self.state_manager.action_context}",
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                provisional_state=self.state_manager.get_provisional_state(),
                hand=self.state.players[color].hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )

    def _process_parameter_action(self, action: ParameterAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase != GamePhase.TRANSACTION:
            return ActionProcessResult(
                processed=False,
                message="No active transaction. Start with meta action",
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )
        
        player = self.state.players[color]
        
        # Автоматический выбор ресурсов, если нужно
        if isinstance(action, ResourceAction) and action.resources_used is AutoResourceSelection:
            action.resources_used = self._select_resources(action, player)
        
        # Валидация действия
        validation_result = self.validation_service.validate_action(
            action, 
            self.state, 
            player,
            self.state_manager.action_context
        )
        
        if not validation_result.is_valid:
            return ActionProcessResult(
                processed=False,
                message=validation_result.message,
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )
        
        # Применяем действие
        self._apply_action(self.state, action, player, self.state_manager.action_context)
        
        # Обновляем состояние
        try:
            self.state_manager.add_subaction()
            return ActionProcessResult(
                processed=True,
                provisional_state=self.state_manager.get_provisional_state(),
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )

    def _process_commit_action(self, action: CommitAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase not in (GamePhase.TRANSACTION, GamePhase.AWAITING_COMMIT):
            return ActionProcessResult(
                processed=False,
                message="No active transaction to commit",
                awaiting=self.get_expected_params(color),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )
        
        if action.commit:
            if self.state_manager.subaction_count == 0:
                return ActionProcessResult(
                    processed=False,
                    message="No changes to state, nothing to commit",
                    awaiting=self.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )
            
            try:
                self.state_manager.commit_transaction()
                
                # Обновляем количество оставшихся действий
                self.state.actions_left -= 1
                
                if self.state.actions_left > 0:
                    # Продолжаем ход
                    return ActionProcessResult(
                        processed=True,
                        message="Changes committed",
                        provisional_state=self.state_manager.get_provisional_state(),
                        awaiting=self.get_expected_params(color),
                        current_context=self.state_manager.action_context,
                        hand=self.state.players[color].hand
                    )
                else:
                    # Завершаем ход
                    self.state_manager.end_turn()
                    return ActionProcessResult(
                        processed=True,
                        message="Changes committed, confirm end of turn",
                        provisional_state=self.state_manager.get_provisional_state(),
                        awaiting=self.get_expected_params(color),
                        current_context=self.state_manager.action_context,
                        hand=self.state.players[color].hand,
                    )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )
        else:
            # Откатываем транзакцию
            try:
                self.state_manager.rollback_transaction()
                return ActionProcessResult(
                    processed=True,
                    message='Transaction rolled back',
                    provisional_state=self.state_manager.get_provisional_state(),
                    awaiting=self.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.get_expected_params(color),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )

    def _process_end_of_turn_action(self, action: EndOfTurnAction, color: PlayerColor) -> ActionProcessResult:
        if action.end_turn:
            # Завершаем ход и переходим к следующему игроку
            next_state = self.turn_manager.prepare_next_turn(self.state)
            if self.turn_manager.concluded:
                return ActionProcessResult(processed=True, end_of_turn=True, awaiting={}, hand=self.state.players[color].hand,
                        provisional_state=self.state_manager.get_provisional_state(), end_of_game=True)
            self.state_manager.start_new_turn(next_state)
            return ActionProcessResult(processed=True, end_of_turn=True, awaiting={}, hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state())
        else:
            # Откатываемся к началу хода
            self.state_manager.rollback_turn()
            return ActionProcessResult(
                processed=True, 
                message='Reverted to turn start', 
                provisional_state=self.state_manager.get_provisional_state(), 
                awaiting={}, 
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand
            )
        
    def _process_resolve_shortfall_action(self, action:ResolveShortfallAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase is not GamePhase.SHORTFALL:
            return ActionProcessResult(
                processed=False,
                awaiting=self.get_expected_params(color),
                provisional_state=self.state_manager.get_provisional_state(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                message="Action is only allowed within shortfall context"
            )
        
        player = self.state.players[color]
        validation = self._validate_shortfall_action(self, action, player)
        if not validation.is_valid:
            return ActionProcessResult(
                processed=False,
                provisional_state=self.state_manager.get_provisional_state(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                message=validation.message,
                awaiting=self.get_expected_params(color)
            )

        self._resolve_shortfall(action, player)
        if not self._in_shortfall():
            self.state_manager.exit_shortfall()
     
    def _apply_action(self, state:BoardState, action:ParameterAction, player:Player, action_context:ActionContext):
        if action.card_id is not None:
            card = player.hand.pop(action.card_id)
            if card.value != 'wild':
                state.discard.append(card)
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

        if action_context is ActionContext.PASS:
            return

        elif action_context is ActionContext.LOAN:
            player.income -= 3
            player.bank += 30
            player.recalculate_income(keep_points=False)
            return

        elif action_context is ActionContext.SCOUT:
            for card_id in action.additional_card_cost:
                state.discard.append(player.hand[card_id])
                player.hand.pop(card_id)
            city_joker = next(j for j in self.state.wild_deck if j.card_type == CardType.CITY)
            ind_joker = next(j for j in self.state.wild_deck if j.card_type == CardType.INDUSTRY)
            player.hand[city_joker.id] = city_joker
            player.hand[ind_joker.id] = ind_joker
            return
        
        elif action_context is ActionContext.DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building.id)

        elif action_context is ActionContext.GLOUCESTER_DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building.id)
            self.state_manager.exit_gloucester_develop()

        elif action_context is ActionContext.NETWORK:
            self.state.links[action.link_id].owner = player.color

        elif action_context is ActionContext.SELL:
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

        elif action_context is ActionContext.BUILD:
            building = player.get_lowest_level_building(action.industry)
            building.slot_id = action.slot_id
            self.state.get_building_slot(action.slot_id).building_placed = player.available_buildings.pop(building.id)

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


    def _resolve_shortfall(self, action:ResolveShortfallAction, player:Player) -> None:
        if action.slot_id:
            slot = self.state.get_building_slot(action.slot_id)
            rebate = slot.building_placed.cost['money'] // 2
            player.bank += rebate
            slot.building_placed = None
        else:
            player.victory_points += player.bank
            player.bank = 0
        return

    def _validate_shortfall_action(self, action:ResolveShortfallAction, player:Player) -> ValidationResult:
        if player.bank >= 0:
            return ValidationResult(is_valid=False, message=f'Player {player.color} is not in shortfall')
        if not action.slot_id:
            for building in self.state.iter_placed_buildings():
                if building.owner == player.color:
                    return ValidationResult(is_valid=False, message=f'Player {player.color} has building in slot {building.slot_id}, sell it first')
        return ValidationResult(is_valid=True)

    def _in_shortfall(self):
        if any(player.bank < 0 for player in self.state.players.values()):
            return True
        return False

    def get_expected_params(self, color:PlayerColor) -> Dict[str, List[str]]:
        if not self.is_player_to_move(color):
            return {}
        classes = self.ACTION_CONTEXT_MAP[self.state_manager.action_context]
        out = {}
        for cls in classes:
            fields = list(cls.model_fields.keys())
            if self.state_manager.action_context not in (ActionContext.MAIN, ActionContext.AWAITING_COMMIT, ActionContext.END_OF_TURN):
                if self.state_manager.has_subaction() and 'card_id' in fields:
                    fields.remove('card_id')
            out[cls.__name__] = fields
        return out
    
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