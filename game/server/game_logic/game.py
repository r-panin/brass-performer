from ...schema import BoardState, ActionContext, Player, ActionProcessResult, PlayerColor, Building, Card, LinkType, City, BuildingSlot, IndustryType, MetaActions, EndOfTurnAction, ValidationResult, Link, MerchantType, MerchantSlot, Market, GameStatus, SellSelection, ScoutSelection, BuildSelection, DevelopSelection, NetworkSelection, ParameterAction, PlayerState, Action, CommitAction, MetaAction, ParameterAction, ExecutionResult, CardType
from typing import List, Dict
import random
from pathlib import Path
import json
from uuid import uuid4
import logging
import copy
from .validation_service import ActionValidationService
from ...schema import ResourceAction, AutoResourceSelection, ResourceSource



class Game:
    RES_PATH = Path(r'game\server\res')
    BUILDING_ROSTER_PATH = Path(RES_PATH / 'building_table.json')
    CARD_LIST_PATH = Path(RES_PATH / 'card_list.json')
    CITIES_LIST_PATH = Path(RES_PATH / 'cities_list.json')
    MERCHANTS_TOKENS_PATH = Path(RES_PATH /'merchant_tokens.json')
    LINKS_PATH = Path(RES_PATH / 'city_links.json')
    logging.basicConfig(level=logging.INFO)
    ACTION_CONTEXT_MAP = {
        ActionContext.MAIN: (MetaActions),
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
    SINGLE_ACTION_CONTEXTS = {ActionContext.BUILD, ActionContext.PASS, ActionContext.SCOUT, ActionContext.LOAN}
    DOUBLE_ACTION_CONTEXTS = {ActionContext.NETWORK, ActionContext.DEVELOP}
    MULTIPLE_ACTION_CONTEXTS = {ActionContext.SELL}
    def __repr__(self) -> str:
        # Основная информация об игре
        game_info = f"Game(id={self.id[:8]}..., players={len(self.state.players)}, era={self.state.era.value})"
        
        # Информация о игроках
        players_info = "\nPlayers:"
        for i, player in enumerate(self.state.players):
            players_info += f"\n  {i+1}. {player.color.value}: {player.bank}£, {player.income} income, {player.victory_points} VP, {len(player.hand)} cards, {len(player.available_buildings)} buildings"
        
        # Информация о городах
        cities_info = f"\nCities: {len(self.state.cities)} total"
        
        # Города с коммивояжерами
        merchant_cities = [city for city in self.state.cities if city.is_merchant]
        cities_info += f", {len(merchant_cities)} with merchants"
        
        # Примеры городов (3 случайных)
        if self.state.cities:
            sample_cities = random.sample(self.state.cities, min(3, len(self.state.cities)))
            cities_info += "\nSample cities:"
            for city in sample_cities:
                merchant_status = "with merchant" if city.is_merchant else "without merchant"
                
                # Детали слотов (разные для обычных городов и городов с коммивояжерами)
                if city.is_merchant:
                    # Для городов с коммивояжерами показываем merchant_slots
                    slot_details = ", ".join([
                        f"[{(slot.merchant_type)}]" 
                        for slot in city.merchant_slots
                    ])
                    slot_type = "Merchant slots"
                elif hasattr(city, 'slots') and city.slots:
                    # Для обычных городов показываем обычные slots
                    slot_details = ", ".join([
                        f"[{', '.join([industry.value for industry in slot.industry_type_options])}]" 
                        for slot in city.slots
                    ])
                    slot_type = "Building slots"
                else:
                    slot_details = "no slots"
                    slot_type = "Slots"        
                # Детали связей
                link_details = {}
                for link in city.links:
                    for linked_city in link.cities:
                        if linked_city != city.name:  # Исключаем текущий город
                            if linked_city not in link_details:
                                link_details[linked_city] = []
                            link_details[linked_city].append(link.type.value)
                
                # Форматируем информацию о связях
                connections = ", ".join([
                    f"{city_name} ({', '.join(link_types)})" 
                    for city_name, link_types in link_details.items()
                ])
                
                cities_info += f"\n  - {city.name} ({merchant_status})"
                cities_info += f"\n    {slot_type}: {slot_details}"
                cities_info += f"\n    Links: {connections}"
        
        # Информация о связях (общая статистика)
        link_types = {}
        for city in self.state.cities:
            for link in city.links:
                link_type = link.type.value
                link_types[link_type] = link_types.get(link_type, 0) + 1
        
        links_info = "\nLink statistics:"
        for link_type, count in link_types.items():
            links_info += f"\n  {link_type}: {count} connections"
        
        # Информация о коммивояжерах
        merchants_info = ""
        if merchant_cities:
            merchants_info = "\nMerchants in cities:"
            for city in merchant_cities:
                merchants_info += f"\n  - {city.name}"
        
        return game_info + players_info + cities_info + links_info + merchants_info

    def __init__(self):
        self.id = str(uuid4())
        self.status = GameStatus.CREATED
        self.available_colors = copy.deepcopy(list(PlayerColor))
        random.shuffle(self.available_colors)
        self.validation_service = ActionValidationService()
        self.action_context = ActionContext.MAIN

    def start(self, player_count:int, players_colors: List[PlayerColor]):
        self.state = self._create_initial_state(player_count, players_colors)
        self.turn_state = self.state.model_copy(deep=True)

    def _create_initial_state(self, player_count: int, player_colors: List[PlayerColor]) -> BoardState:
        
        self.deck = self._build_initial_deck(player_count)

        players = {color: self._create_player(color) for color in player_colors}

        cities = self._create_cities(player_count)

        links = self._create_links()

        market = self._create_starting_market()

        self.status = GameStatus.ONGOING
        
        current_turn = random.choice(list(players.keys()))

        actions_left = 1

        discard = []

        wild_deck = self._build_wild_deck()


        #burn initial cards
        for _ in players:
            self.deck.pop()

        return BoardState(cities=cities, players=players, deck=self.deck, market=market, era=LinkType.CANAL, current_turn=current_turn, actions_left=actions_left, discard=discard, wild_deck=wild_deck, links=links)
    
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
                era_exclusion=building.get('era_exclusion')
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
        
        return [
            card
            for base_id in range(INDUSTRY_START_ID, INDUSTRY_START_ID + NUM_WILD_CARDS)
            for card in (
                Card(id=base_id, card_type=CardType.INDUSTRY, value='wild'),
                Card(id=base_id + CITY_OFFSET, card_type=CardType.CITY, value='wild'),
            )
        ]
 
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
    
    def get_player_state(self, color:PlayerColor) -> PlayerState:
        return PlayerState(
            common_state=self.state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state.players[color].hand.values()}
        )

    def process_action(self, action:Action, color:PlayerColor) -> ActionProcessResult:
        if not self.is_player_to_move(color):
            return ActionProcessResult(processed=False, message=f"Attempted move by {color}, current turn is {self.state.current_turn}", awaiting={}, current_context=self.action_context)
        
        if isinstance(action, MetaAction):
            if self.action_context is not ActionContext.MAIN:
                return ActionProcessResult(processed=False, message="Cannot submit a meta action outside of main context", awaiting=self.get_expected_params(), current_context=self.action_context)
            
            self.action_state = self.turn_state.model_copy(deep=True)
            self.action_context = ActionContext(action.action)
            self.action_state.subaction_count = 0
            return ActionProcessResult(processed=True, message=f"Entered {self.action_context}", awaiting=self.get_expected_params(), current_context=self.action_context)

        elif isinstance(action, ParameterAction):
            if not hasattr(self, 'action_state'):
                return ActionProcessResult(
                processed=False,
                message="No active transaction. Start with meta action",
                awaiting=self.get_expected_params(), current_context=self.action_context
            )

            player = self.action_state.players[color]

            if action is ResourceAction:
                if action.resources_used is AutoResourceSelection:
                    action.resources_used = self._select_resources(action, player)

            validation_result = self.validation_service.validate_action(action, self.action_state, player, self.action_context)
            if not validation_result.is_valid:
                return ActionProcessResult(processed=False, message=validation_result.message, awaiting=self.get_expected_params(), current_context=self.action_context)
            
            self._apply_action(action, self.action_state, player)

            self.action_state.subaction_count += 1
            if self.action_state.subaction_count > 1 and self.action_context in self.SINGLE_ACTION_CONTEXTS:
                self.action_context = ActionContext.AWAITING_COMMIT
            elif self.action_state.subaction_count > 2 and self.action_context in self.DOUBLE_ACTION_CONTEXTS:
                self.action_context = ActionContext.AWAITING_COMMIT

            return ActionProcessResult(processed=True, provisional_state=self.action_state, awaiting=self.get_expected_params(), current_context=self.action_context)
            
        elif isinstance(action, CommitAction):
            if action.commit:

                if self.action_state.subaction_count == 0:
                    return ActionProcessResult(processed=False, message="No changes to state, nothing to commit", awaiting=self.get_expected_params(), current_context=self.action_context)
                
                self.turn_state = self.action_state.model_copy(deep=True)

                self.turn_state.actions_left -= 1
                if self.turn_state.actions_left > 0:
                    self.action_context = ActionContext.MAIN

                else:
                    self.action_context = ActionContext.END_OF_TURN

            else:
                self.action_context = ActionContext.MAIN
                return ActionProcessResult(processed=True, message=f'Unstaging action, returned to action context {self.action_context}', awaiting=self.get_expected_params(), current_context=self.action_context)

        elif isinstance(action, EndOfTurnAction):
            if action.end_turn:
                self.state = self.turn_state.model_copy(deep=True)
                self.pass_turn()
                return ActionProcessResult(processed=True, end_of_turn=True, awaiting={})
            
            else:
                self.turn_state = self.state
                self.action_context = ActionContext.MAIN
                return ActionProcessResult(processed=True, message='Reverted to turn start', provisional_state=self.turn_state.hide_state(), awaiting={}, current_context=self.action_context)
            
        else:
            # I couldn't see this coming
            return ActionProcessResult(processed=False, message="wowsers", awaiting={'W': ('T', 'F')}, current_context=self.action_context)
    
    def _apply_action(self, state:BoardState, action:ParameterAction, player:Player):
        pass

    def _select_resources(self, action:ResourceAction, player:Player) -> List[ResourceSource]:
        pass

    def get_expected_params(self) -> Dict[str, List[str]]:
        classes = self.ACTION_CONTEXT_MAP[self.action_context]
        out = {}

        for cls in classes:
            fields = cls.model_fields.keys()
            if self.action_context not in (ActionContext.MAIN, ActionContext.AWAITING_COMMIT, ActionContext.END_OF_TURN):
                if self.action_state.subaction_count > 0 and 'card_id' in fields:
                    fields.remove('card_id')
                elif self.action_state.subaction_count == 0 and cls.__name__ == 'CommitAction':
                    continue  # Пропускаем CommitAction если нет изменений
            out[cls.__name__] = fields
        
        return out

    
    def validate_action_context(self, action_context, action) -> ValidationResult:
            allowed_actions = self.ACTION_CONTEXT_MAP.get(action_context)
            is_allowed = isinstance(action, allowed_actions) if allowed_actions else False
            if not is_allowed:
                return ValidationResult(is_valid=False, message=f'Action is not appropriate for context {action_context}')
            return ValidationResult(is_valid=True)

    def is_player_to_move(self, color:PlayerColor):
        if self.state.current_turn != color:
            return False
        return True
        

if __name__ == '__main__':
    game = Game(4)
    print(game)