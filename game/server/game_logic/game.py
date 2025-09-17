from ...schema import BoardState, ResourceStrategy, ResourceType, ResourceAmounts, BuildStart, SellStart, NetworkStart, DevelopStart, ScoutStart, LoanStart, PassStart, ResolveShortfallAction, ActionContext, Player, ActionProcessResult, PlayerColor, Building, Card, LinkType, City, BuildingSlot, IndustryType, MetaActions, EndOfTurnAction, ValidationResult, Link, MerchantType, MerchantSlot, Market, GameStatus, SellSelection, ScoutSelection, BuildSelection, DevelopSelection, NetworkSelection, ParameterAction, PlayerState, Action, CommitAction, MetaAction, ParameterAction, ExecutionResult, CardType
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
from collections import defaultdict, Counter
import itertools



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
        ActionContext.END_OF_TURN: (EndOfTurnAction,),
        ActionContext.SHORTFALL: (ResolveShortfallAction,)
    }
    INDUSTRY_RESOURCE_OPTIONS:Dict[IndustryType, set[tuple[ResourceType]]] = {
        IndustryType.BOX: {(ResourceType.COAL), (ResourceType.IRON), (ResourceType.COAL, ResourceType.COAL), (), (ResourceType.COAL, ResourceType.IRON), (ResourceType.IRON, ResourceType.IRON)},
        IndustryType.IRON: {(ResourceType.COAL)},
        IndustryType.COAL: {(), (ResourceType.IRON)},
        IndustryType.BREWERY: {(ResourceType.IRON)},
        IndustryType.COTTON: {(), (ResourceType.COAL), (ResourceType.COAL, ResourceType.IRON)},
        IndustryType.POTTERY: {(ResourceType.IRON), (ResourceType.COAL), (ResourceType.COAL, ResourceType.COAL)}
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

    def _build_wild_deck(self) -> List[Card]:
        INDUSTRY_START_ID = 65
        CITY_OFFSET = 4
        NUM_WILD_CARDS = 4
        out = []
        for base_id in range(INDUSTRY_START_ID, INDUSTRY_START_ID + NUM_WILD_CARDS):
            out.append(Card(id=base_id, card_type=CardType.INDUSTRY, value='wild'))
            out.append(Card(id=base_id+CITY_OFFSET, card_type=CardType.CITY, value='wild'))
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
            next_state = self._prepare_next_turn(self.state)
            if self.status == GameStatus.COMPLETE:
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

        elif action_context is ActionContext.NETWORK:
            self.state.links[action.link_id].owner = player.color

        elif action_context is ActionContext.SELL:
            building = self.state.get_building_slot(action.slot_id).building_placed
            building.flipped = True
            owner = self.state.players[building.owner]
            owner.income_points += building.income
            owner.recalculate_income()

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

    def _prepare_next_turn(self, state:BoardState) -> BoardState:
        state.turn_order.pop()
        state.actions_left = 2
        if not state.turn_order:
            state = self._prepare_next_round(state)
        return state

    def _prepare_next_round(self, state:BoardState) -> BoardState:
        state.turn_order = sorted(state.players, key=lambda k: state.players[k].money_spent)

        if all(len(p.hand) == 0 for p in state.players.values()) and len(state.deck) == 0:
            if state.era == LinkType.CANAL:
                state = self._prepare_next_era(state)
            elif state.era == LinkType.RAIL:
                state = self._conclude_game(state)

        for player in state.players.values():
            player.bank += player.income
            
        
        if any(player.bank < 0 for player in self.state.players.values()):
            self.state_manager.enter_shortfall()

            if state.deck:
                while len(player.hand) < 8:
                    card = state.deck.pop()
                    player.hand[card.id] = card

        return state
    
    def _prepare_next_era(self, state:BoardState) -> BoardState:
        self.state.deck = self._build_initial_deck(len(self.state.players))
        random.shuffle(self.state.deck)

        for link in self.state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    self.state.players[link.owner].victory_points += self.state.cities[city_name].get_link_vps()
                link.owner = None

        for building in self.state.iter_placed_buildings():
            if building.flipped:
                self.state.players[building.owner].victory_points += building.victory_points
            if building.level == 1:
                self.state.get_building_slot(building.slot_id).building_placed = None

        state.era = LinkType.RAIL

        return state

    def _conclude_game(self, state:BoardState) -> BoardState:
        for link in state.links.values():
            if link.owner is not None:
                for city_name in link.cities:
                    state.players[link.owner].victory_points += state.cities[city_name].get_link_vps()

        for building in state.iter_placed_buildings():
            if building.flipped:
                state.players[building.owner].victory_points += building.victory_points
        
        self.status = GameStatus.COMPLETE
        return state 

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
    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False, message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def is_player_to_move(self, color:PlayerColor):
        if self.state_manager.action_context is ActionContext.SHORTFALL:
            if self.state.players[color].bank < 0:
                return True
            return False
        
        if self.state.turn_order[0] != color:
            return False
        return True
        
    def get_action_space(self, color:PlayerColor) -> Dict[str, List[Action]]:
        player = self.state.players[color]
        valid_action_types = self.get_expected_params(color)
        out = defaultdict(list)
        for action in valid_action_types:
            match action:
                case "BuildStart":
                    out[action].append(BuildStart())
                case "SellStart":
                    out[action].append(SellStart())
                case "NetworkStart":
                    out[action].append(NetworkStart())
                case "DevelopStart":
                    out[action].append(DevelopStart())
                case "ScoutStart":
                    out[action].append(ScoutStart())
                case "LoanStart":
                    out[action].append(LoanStart())
                case "PassStart":
                    out[action].append(PassStart())
                case "BuildSelection":
                    out[action] = self.get_valid_build_actions(self.state, player)
                case "SellSelection":
                    out[action] = self.get_valid_sell_actions(self.state, player)

    def get_valid_build_actions(self, state: BoardState, player: Player) -> List[BuildSelection]: # oh boy
        out = []
        cards = player.hand.values()
        slots = [slot for city in state.cities.values() for slot in city.slots.values() if not slot.building_placed]
        industries = list(IndustryType)

        iron_buildings = state.get_player_iron_sources()
        iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=building.slot_id) for building in iron_buildings]
        iron_amounts = {building.slot_id: building.resource_count for building in iron_buildings}
        total_iron_available = sum(iron_amounts.values())

        market_iron = ResourceSource(resource_type=ResourceType.IRON)
        market_coal = ResourceSource(resource_type=ResourceType.COAL)

        network = state.get_player_network(player.color)

        for card in cards:
            for slot in slots:
                market_coal_available = state.market_access_exists(slot.city)
                
                # Получаем ВСЕ источники угля с приоритетами
                coal_buildings = state.get_player_coal_sources(city_name=slot.city)
                coal_sources = []
                coal_secondary_sources = []
                coal_amounts = {}
                secondary_coal_amounts = {}
                
                for building, priority in coal_buildings:
                    if priority == 0:  # Primary sources
                        coal_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                        coal_amounts[building.slot_id] = building.resource_count
                    else:  # Secondary sources
                        coal_secondary_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                        secondary_coal_amounts[building.slot_id] = building.resource_count

                primary_coal_available = sum(coal_amounts.values())
                secondary_coal_available = sum(secondary_coal_amounts.values())

                for industry in industries:
                    if industry not in slot.industry_type_options:
                        continue
                        
                    if card.card_type == CardType.CITY:
                        if slot.city != card.value and card.value != 'wild':
                            continue
                        if "brewery" in slot.city:
                            continue
                    
                    if card.card_type == CardType.INDUSTRY:
                        if card.value != industry.value and card.value != 'wild':
                            continue
                        if slot.city not in [city.name for city in network]:
                            continue

                    building = player.get_lowest_level_building(industry)
                    coal_required = building.cost['coal']
                    iron_required = building.cost['iron']
                    
                    base_cost = building.cost['money']
                    if player.bank < base_cost:
                        continue

                    # Формируем варианты источников угля в порядке приоритета
                    coal_options = []
                    # Сначала используем primary sources
                    coal_options.extend(coal_sources)
                    
                    # Если primary недостаточно, добавляем secondary
                    if primary_coal_available < coal_required:
                        coal_options.extend(coal_secondary_sources)
                    
                    # Если всё ещё недостаточно и есть доступ к рынку, добавляем market
                    if (primary_coal_available + secondary_coal_available < coal_required and 
                        market_coal_available):
                        coal_options.append(market_coal)

                    # Генерируем комбинации для угля
                    if coal_required > 0:
                        coal_combinations = itertools.combinations_with_replacement(coal_options, coal_required)
                    else:
                        coal_combinations = [()]

                    # Для железа оставляем без изменений
                    iron_options = []
                    if iron_required > 0:
                        iron_options.extend(iron_sources)
                        if total_iron_available < iron_required or not iron_sources:
                            iron_options.append(market_iron)
                        
                        iron_combinations = itertools.combinations_with_replacement(iron_options, iron_required)
                    else:
                        iron_combinations = [()]
                    
                    for coal_comb, iron_comb in itertools.product(coal_combinations, iron_combinations):
                        resources_used = list(coal_comb) + list(iron_comb)
                        
                        coal_used = {}
                        iron_used = {}
                        market_coal_count = 0
                        market_iron_count = 0
                        valid = True
                        
                        for resource in resources_used:
                            if resource.resource_type == ResourceType.COAL:
                                if resource.building_slot_id:
                                    # Проверяем как primary, так и secondary источники
                                    if resource.building_slot_id in coal_amounts:
                                        coal_used[resource.building_slot_id] = coal_used.get(resource.building_slot_id, 0) + 1
                                        if coal_used[resource.building_slot_id] > coal_amounts[resource.building_slot_id]:
                                            valid = False
                                            break
                                    elif resource.building_slot_id in secondary_coal_amounts:
                                        coal_used[resource.building_slot_id] = coal_used.get(resource.building_slot_id, 0) + 1
                                        if coal_used[resource.building_slot_id] > secondary_coal_amounts[resource.building_slot_id]:
                                            valid = False
                                            break
                                else:
                                    market_coal_count += 1
                                    
                            elif resource.resource_type == ResourceType.IRON:
                                if resource.building_slot_id:
                                    iron_used[resource.building_slot_id] = iron_used.get(resource.building_slot_id, 0) + 1
                                    if iron_used[resource.building_slot_id] > iron_amounts[resource.building_slot_id]:
                                        valid = False
                                        break
                                else:
                                    market_iron_count += 1
                        
                        primary_coal_ids = coal_amounts.keys()
                        used_ids = [r.building_slot_id for r in resources_used]
                        if not primary_coal_ids in used_ids and primary_coal_ids:
                            continue

                        if not valid:
                            continue
                        
                        if market_coal_count > 0 and not market_coal_available:
                            continue
                            
                        coal_cost = state.market.calculate_coal_cost(market_coal_count)
                        iron_cost = state.market.calculate_iron_cost(market_iron_count)
                        if player.bank < base_cost + coal_cost + iron_cost:
                            continue
                        
                        out.append(BuildSelection(
                            slot_id=slot.id,
                            card_id=card.id,
                            industry=industry,
                            resources_used=resources_used
                        ))
        
        data_strings = sorted(action.model_dump_json() for action in out)
        return [BuildSelection.model_validate_json(data) for data in data_strings]

    def get_valid_sell_actions(self, state:BoardState, player:Player) -> List[SellSelection]:
        out = []
        cards = player.hand.values()
        slots = [
                slot 
                for city in state.cities.values() 
                for slot in city.slots.values() 
                if slot.building_placed is not None and slot.building_placed.is_sellable()
            ] 

        for slot in slots:
            beer_buildings = state.get_player_beer_sources(player.color, city_name=slot.city)
            beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=building.slot_id) for building in beer_buildings]
            beer_amounts = {b.slot_id: b.resource_count for b in beer_buildings}
            beer_required = slot.building_placed.sell_cost
            if beer_required:
                beer_combinations = itertools.combinations_with_replacement(beer_sources, beer_required)
            else:
                beer_combinations = [()]
            for beer_combo in beer_combinations:
                beer_used = defaultdict(int)
                valid = True
                for resource in beer_combo:
                    beer_used[resource.building_slot_id] += 1
                    if beer_used[resource.building_slot_id] > beer_amounts[resource.building_slot_id]

        data_strings = sorted(action.model_dump_json() for action in out)
        return [SellSelection.model_validate_json(data) for data in data_strings]

    def _get_theoretically_valid_build_actions(self) -> List[BuildSelection]:
        '''Gets all build action parameter permutations that could in theory be valid under a specific game state'''
        out = []

        '''Build cards'''
        cards = self._build_initial_deck(4)
        jokers = self._build_wild_deck()
        cards.append(next(joker for joker in jokers if joker.card_type == CardType.CITY))
        cards.append(next(joker for joker in jokers if joker.card_type == CardType.INDUSTRY))

        '''Build slots'''
        slots = [slot for city in self.state.cities.values() for slot in city.slots.values()]

        '''Build industries'''
        industries = set(IndustryType)

        '''Build resources'''
        iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=slot.id) for slot in slots if IndustryType.IRON in slot.industry_type_options]
        iron_sources.append(ResourceSource(resource_type=ResourceType.IRON))
        coal_sources = [ResourceSource(resource_type=ResourceType.COAL, building_slot_id=slot.id) for slot in slots if IndustryType.COAL in slot.industry_type_options]
        coal_sources.append(ResourceSource(resource_type=ResourceType.COAL))

        for card in cards:
            for slot in slots:
                # Фильтруем источники ресурсов для текущего слота
                coal_filtered = [src for src in coal_sources if src.building_slot_id != slot.id]
                iron_filtered = [src for src in iron_sources if src.building_slot_id != slot.id]
                
                for industry in industries:
                    if industry not in slot.industry_type_options:
                        continue
                    if card.card_type == CardType.CITY:
                        if slot.city != card.value and card.value != 'wild':
                            continue
                        if "brewery" in slot.city:
                            continue
                    if card.card_type == CardType.INDUSTRY:
                        if card.value != industry.value and card.value != 'wild':
                            continue
                    
                    for option in self.INDUSTRY_RESOURCE_OPTIONS[industry]:
                        resource_counts = Counter(option)
                        combinations_per_resource = {}
                        
                        for resource, count in resource_counts.items():
                            if resource == ResourceType.COAL:
                                available = coal_filtered
                            elif resource == ResourceType.IRON:
                                available = iron_filtered
                            else:
                                available = []
                                
                            combinations_per_resource[resource] = self._remove_duplicates(list(
                                itertools.product(available)
                            ))
                        
                        for source_combinations in itertools.product(*combinations_per_resource.values()):
                            resources_used = []
                            for tuple_sources in source_combinations:
                                resources_used.extend(tuple_sources)
                            
                            out.append(BuildSelection(
                                slot_id=slot.id,
                                card_id=card.id,
                                industry=industry,
                                resources_used=resources_used
                            ))
        data_strings = sorted(action.model_dump_json() for action in out)
        return [BuildSelection.model_validate_json(data) for data in data_strings]

    def _remove_duplicates(self, lst):
        seen = set()
        result = []
        for sublist in lst:
            key = tuple(sorted(item.model_dump_json() for item in sublist))
            if key not in seen:
                seen.add(key)
                result.append(sublist)
        return result
    

if __name__ == '__main__':
    game = Game()
    game.start(4, ['white', 'red', 'yellow', 'purple'])
    print(game.get_valid_build_actions(state=game.state, player=game.state.players[game.state.turn_order[0]]))
#    print(game._get_theoretically_valid_build_actions()[0:5])