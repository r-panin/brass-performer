from ...schema import BoardState, ResourceStrategy, ResourceAmounts, ResourceType, ActionContext, Player, ActionProcessResult, PlayerColor, Building, Card, LinkType, City, BuildingSlot, IndustryType, MetaActions, EndOfTurnAction, ValidationResult, Link, MerchantType, MerchantSlot, Market, GameStatus, SellSelection, ScoutSelection, BuildSelection, DevelopSelection, NetworkSelection, ParameterAction, PlayerState, Action, CommitAction, MetaAction, ParameterAction, ExecutionResult, CardType
from typing import List, Dict, get_args
import random
from pathlib import Path
import json
from uuid import uuid4
import logging
import copy
from .validation_service import ActionValidationService
from ...schema import ResourceAction, AutoResourceSelection, ResourceSource
from .game_state_manager import GameStateManager, GamePhase
from collections import defaultdict



class Game:
    RES_PATH = Path(r'game\server\res')
    BUILDING_ROSTER_PATH = Path(RES_PATH / 'building_table.json')
    CARD_LIST_PATH = Path(RES_PATH / 'card_list.json')
    CITIES_LIST_PATH = Path(RES_PATH / 'cities_list.json')
    MERCHANTS_TOKENS_PATH = Path(RES_PATH /'merchant_tokens.json')
    LINKS_PATH = Path(RES_PATH / 'city_links.json')
    logging.basicConfig(level=logging.INFO)
    ACTION_CONTEXT_MAP = {
        ActionContext.MAIN: get_args(MetaAction),
        ActionContext.AWAITING_COMMIT: (CommitAction,),
        ActionContext.BUILD: (BuildSelection,),
        ActionContext.DEVELOP: (DevelopSelection, CommitAction),
        ActionContext.NETWORK: (NetworkSelection, CommitAction),
        ActionContext.PASS: (ParameterAction,),
        ActionContext.SCOUT: (ScoutSelection,),
        ActionContext.SELL: (SellSelection, CommitAction),
        ActionContext.LOAN: (ParameterAction,),
        ActionContext.END_OF_TURN: (EndOfTurnAction,)
    }

    @property
    def state(self) -> BoardState:
        return self.state_manager.current_state

    def __init__(self):
        self.id = str(uuid4())
        self.status = GameStatus.CREATED
        self.available_colors = copy.deepcopy(list(PlayerColor))
        random.shuffle(self.available_colors)
        self.validation_service = ActionValidationService()
        logging.basicConfig(level=logging.DEBUG)

    def start(self, player_count:int, players_colors: List[PlayerColor]):
        self.state_manager = GameStateManager(self._create_initial_state(player_count, players_colors))

    def _create_initial_state(self, player_count: int, player_colors: List[PlayerColor]) -> BoardState:
        
        self.deck = self._build_initial_deck(player_count)

        players = {color: self._create_player(color) for color in player_colors}

        cities = self._create_cities(player_count)

        links = self._create_links()

        market = self._create_starting_market()

        self.status = GameStatus.ONGOING
        
        turn_order = player_colors
        random.shuffle(turn_order)

        actions_left = 1

        discard = []

        wild_deck = self._build_wild_deck()

        #burn initial cards
        for _ in players:
            self.deck.pop()

        return BoardState(cities=cities, players=players, deck=self.deck, market=market, era=LinkType.CANAL, turn_order=turn_order, actions_left=actions_left, discard=discard, wild_deck=wild_deck, links=links)
    
    def _build_initial_building_roster(self, player_color:PlayerColor) -> Dict[str, Building]:
        out = {}
        with open(self.BUILDING_ROSTER_PATH) as openfile:
            building_json:List[dict] = json.load(openfile)
        for building in building_json:
            building = Building(
                id=building['id'],
                industry_type=building['industry'],
                level=building['level'],
                city=str(),
                owner=player_color,
                flipped=False,
                cost=building['cost'],
                resource_count=building.get('resource_count', 0),
                victory_points=building['vp'],
                sell_cost=building.get('sell_cost'),
                is_developable=building.get('developable', True),
                link_victory_points=building['conn_vp'],
                era_exclusion=building.get('era_exclusion'),
                income=building['income']
            )
            out[building.id] = building
        return out

    def _create_player(self, color:PlayerColor) -> Player:
        return Player(
            hand={card.id: card for card in [self.deck.pop() for _ in range(8)]},
            available_buildings=self._build_initial_building_roster(color),
            color=color,
            bank=17,
            income=0,
            income_points=10,
            victory_points=0
        )
    
    def _build_initial_deck(self, player_count:int) -> List[Card]:
        out:List[Card] = []
        with open(self.CARD_LIST_PATH) as cardfile:
            cards_data = json.load(cardfile)
        for card_data in cards_data:
            if card_data['player_count'] <= player_count:
                logging.debug(f"processing card data {card_data}")
                card = Card(
                    id=card_data["id"],
                    card_type=CardType(card_data["card_type"]),
                    value=card_data["value"]
                )
                logging.debug(f"appending card{card}")
                out.append(card)
        random.shuffle(out)
        return out

    def _build_wild_deck(self) -> List[tuple[Card]]:
        INDUSTRY_START_ID = 65
        CITY_OFFSET = 4
        NUM_WILD_CARDS = 4
        out = []
        for base_id in range(INDUSTRY_START_ID, INDUSTRY_START_ID + NUM_WILD_CARDS):
            out.append((Card(id=base_id, card_type=CardType.INDUSTRY, value='wild'),
                        Card(id=base_id+CITY_OFFSET, card_type=CardType.CITY, value='wild')))
        return out  

    def _create_cities(self, player_count:int) -> Dict[str, City]:
        '''
        Базовая генерация городов без связей
        '''
        out:Dict[str, City] = {}
        with open(self.CITIES_LIST_PATH) as cityfile:
            cities_data:dict = json.load(cityfile)

        with open(self.MERCHANTS_TOKENS_PATH) as merchantsfile:
            tokens_data = json.load(merchantsfile)
        tokens = []
        for token_data in tokens_data:
            if token_data['player_count'] <= player_count:
                tokens.append(MerchantType(token_data['type']))
        random.shuffle(tokens)

        for city_data in cities_data:
            city_name = city_data['name']
            logging.debug(f'creating city {city_name}')
            logging.debug(f'merchant player count: {city_data["player_count"]}') if 'player_count' in city_data.keys() else logging.debug('not a merchant')
            slots=[BuildingSlot(
                    id=slot['id'],
                    city=city_name,
                    industry_type_options=[IndustryType(industry) for industry in slot['industry_type_options']]
                ) for slot in city_data['building_slots']] if 'building_slots' in city_data.keys() else []
            is_merchant = city_data.get('merchant', False)
            if is_merchant:
                mslots = {}
                city_player_count = city_data['player_count']
                if player_count >= city_player_count:
                    merchant_slot_types = [tokens.pop() for _ in range(len(city_data['merchant_slots']))]
                else:
                    merchant_slot_types = [mslot['merchant_type'] for mslot in city_data["merchant_slots"]] 
                for slot in city_data['merchant_slots']:
                    mslots[slot['id']] = (MerchantSlot(
                        id=slot['id'],
                        city=city_name,
                        merchant_type=merchant_slot_types.pop()
                    ))
            city = (City(
                name=city_name,
                slots={slot.id: slot for slot in slots},
                is_merchant=city_data.get('merchant', False),
                merchant_min_players=city_data.get('player_count'),
                merchant_slots=mslots if is_merchant else None
            ))
            out[city_name] = city

        return out


    def _create_links(self) -> List[Link]:
        out:Dict[int, Link] = {}
        with open(self.LINKS_PATH) as linksfile:
            links_data:dict = json.load(linksfile) 
        for link_data in links_data:
            out[link_data["id"]] = Link(
                id=link_data['id'],
                type=link_data['transport'],
                cities=link_data['cities']
            )
        return out
    
    def _create_starting_market(self) -> Market:
        coal_count = 13
        iron_count = 8
        market = Market(coal_count=coal_count, iron_count=iron_count, coal_cost=0, iron_cost=0)
        market.update_market_costs()
        return market
    
    def get_player_state(self, color:PlayerColor, state:BoardState=None) -> PlayerState:
        if state is None:
            state = self.state
        return PlayerState(
            common_state=state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state.players[color].hand.values()}
        )

    def process_action(self, action: Action, color: PlayerColor) -> ActionProcessResult:
        print(f'RECEIVED ACTION OF TYPE {type(action)}')
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
        
        # Обрабатываем действие в зависимости от типа
        if isinstance(action, MetaAction):
            return self._process_meta_action(action, color)
        elif isinstance(action, ParameterAction):
            return self._process_parameter_action(action, color)
        elif isinstance(action, CommitAction):
            return self._process_commit_action(action, color)
        elif isinstance(action, EndOfTurnAction):
            return self._process_end_of_turn_action(action, color)
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
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )
        
        try:
            self.state_manager.start_transaction(ActionContext(action.action))
            return ActionProcessResult(
                processed=True,
                message=f"Entered {self.state_manager.action_context}",
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                provisional_state=self.state_manager.get_provisional_state(),
                hand=self.state.players[color].hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
            )

    def _process_parameter_action(self, action: ParameterAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase != GamePhase.TRANSACTION:
            return ActionProcessResult(
                processed=False,
                message="No active transaction. Start with meta action",
                awaiting=self.get_expected_params(),
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
                awaiting=self.get_expected_params(),
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
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )
        except ValueError as e:
            return ActionProcessResult(
                processed=False,
                message=str(e),
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                hand=player.hand
            )

    def _process_commit_action(self, action: CommitAction, color: PlayerColor) -> ActionProcessResult:
        if self.state_manager.phase not in (GamePhase.TRANSACTION, GamePhase.AWAITING_COMMIT):
            return ActionProcessResult(
                processed=False,
                message="No active transaction to commit",
                awaiting=self.get_expected_params(),
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand,
                provisional_state=self.state_manager.get_provisional_state()
            )
        
        if action.commit:
            if self.state_manager._state.subaction_count == 0:
                return ActionProcessResult(
                    processed=False,
                    message="No changes to state, nothing to commit",
                    awaiting=self.get_expected_params(),
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
                        awaiting=self.get_expected_params(),
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
                        awaiting=self.get_expected_params(),
                        current_context=self.state_manager.action_context,
                        hand=self.state.players[color].hand,
                    )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.get_expected_params(),
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
                    awaiting=self.get_expected_params(),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                )
            except ValueError as e:
                return ActionProcessResult(
                    processed=False,
                    message=str(e),
                    awaiting=self.get_expected_params(),
                    current_context=self.state_manager.action_context,
                    hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state()
                )

    def _process_end_of_turn_action(self, action: EndOfTurnAction, color: PlayerColor) -> ActionProcessResult:
        if action.end_turn:
            # Завершаем ход и переходим к следующему игроку
            next_state = self._prepare_next_turn()
            self.state_manager.start_new_turn(next_state)
            return ActionProcessResult(processed=True, end_of_turn=True, awaiting={}, hand=self.state.players[color].hand,
                    provisional_state=self.state_manager.get_provisional_state())
        else:
            # Откатываемся к началу хода
            self.state_manager.rollback_transaction()
            return ActionProcessResult(
                processed=True, 
                message='Reverted to turn start', 
                provisional_state=self.state_manager.get_provisional_state(), 
                awaiting={}, 
                current_context=self.state_manager.action_context,
                hand=self.state.players[color].hand
            )
     
    def _apply_action(self, state:BoardState, action:ParameterAction, player:Player, action_context:ActionContext):
        if action.card_id is not None:
            state.discard.append(player.hand[action.card_id])
            player.hand.pop(action.card_id)

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
            for rtype, amount in market_amounts:
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
            jokers = self.action_state.wild_deck.pop()
            for joker in jokers:
                player.hand[joker.id] = joker
            return
        
        elif action_context is ActionContext.DEVELOP:
            building = player.get_lowest_level_building(action.industry)
            player.available_buildings.pop(building)

        elif action_context is ActionContext.NETWORK:
            self.state.links[action.link_id].owner = player.color

        elif action_context is ActionContext.SELL:
            building = self.state.get_building_slot(action.slot_id).building_placed
            building.flipped = True
            owner = self.state.players[building.owner]
            owner.income += building.income

        elif action_context is ActionContext.BUILD:
            building = player.get_lowest_level_building(action.industry)
            building.slot_id = action.slot_id
            self.state.get_building_slot(action.slot_id).building_placed = player.available_buildings.pop(building.id)

    def _select_resources(self, action:ResourceAction, player:Player) -> List[ResourceSource]:
        amounts = self.get_resource_amounts(action, player)
        out = []
        if action.resources_used.strategy is ResourceStrategy.MERCHANT_FIRST:
            merchant_first = True
            strategy = action.resources_used.then
        else:
            strategy = action.resources_used.strategy

        if isinstance(action, (BuildSelection, SellSelection)):
            action_city = self.state.get_building_slot(action.slot_id).city
            link_id = None
        elif isinstance(action, NetworkSelection):
            action_city = None
            link_id = action.link_id

        if amounts.iron:
            iron_buildings = self.state.get_player_iron_sources()
            with_scores = [(building,
                            self.calculate_resource_score(building, strategy))
                            for building in iron_buildings]
            with_scores.sort(key=lambda x: x[1], reverse=True)
            taken_iron = 0


        if amounts.coal:
            coal_buildings = self.state.get_player_coal_sources(city_name=action_city, link_id=link_id)

        if amounts.beer:
            beer_buildings = self.state.get_player_beer_sources(city_name=action_city, link_id=link_id)
        # TODO

    def _prepare_next_turn(self) -> BoardState:
        pass

    def _prepare_next_round(self) -> BoardState:
        pass

    def calcualte_resource_score(self, building:Building, strategy:ResourceStrategy, color) -> float:
        match type(strategy):
            case ResourceStrategy.MAXIMIZE_INCOME:
                return building.income / building.resource_count if building.owner == color else -(building.income / building.resource_count)
            case ResourceStrategy.MAXIMIZE_VP:
                vp_score = building.victory_points if building.owner == color else -building.victory_points
                city = self.state.get_building_slot(building.slot_id).city
                for link in self.state.links.values():
                    if city in link.cities:
                        if link.owner == color:
                            vp_score += building.link_victory_points
                        elif link.owner is not None:
                            vp_score -= building.link_victory_points
                return vp_score
        return 0 

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

    def get_expected_params(self) -> Dict[str, List[str]]:
        classes = self.ACTION_CONTEXT_MAP[self.state_manager.action_context]
        out = {}

        for cls in classes:
            fields = list(cls.model_fields.keys())
            if self.state_manager.action_context not in (ActionContext.MAIN, ActionContext.AWAITING_COMMIT, ActionContext.END_OF_TURN):
                if self.state_manager.has_subaction() and 'card_id' in fields:
                    fields.remove('card_id')
            out[cls.__name__] = fields
        
        return out

    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False, message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def is_player_to_move(self, color:PlayerColor):
        if self.state.turn_order[0] != color:
            return False
        return True
        

if __name__ == '__main__':
    game = Game(4)
    print(game)