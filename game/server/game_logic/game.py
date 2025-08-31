from ...schema import BoardState, Player, PlayerColor, Building, Card, LinkType, City, BuildingSlot, IndustryType, Link, MerchantType, MerchantSlot, Market, GameStatus, PlayerState, Action, ExecutionResult
from typing import List, Dict
import random
from pathlib import Path
import json
from uuid import uuid4
import math
import logging
import copy
from .validation_service import Actionvalidation_service

class Game:
    RES_PATH = Path(r'game\server\res')
    BUILDING_ROSTER_PATH = Path(RES_PATH / 'building_table.json')
    CARD_LIST_PATH = Path(RES_PATH / 'card_list.json')
    CITIES_LIST_PATH = Path(RES_PATH / 'cities_list.json')
    MERCHANTS_TOKENS_PATH = Path(RES_PATH /'merchant_tokens.json')
    SPECIAL_CITY_GROUPS = {
        "worcester_group": ["Worcester", "Kidderminster", "farm_brewery_south"]
    }
    SPECIAL_MERCHANT = 'Shrewsbury'
    COAL_MAX_COST = 8
    IRON_MAX_COST = 6
    COAL_MAX_COUNT = 14
    IRON_MAX_COUNT = 10
    TOTAL_MERCHANT_TOKENS = 9
    logging.basicConfig(level=logging.INFO)
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
        self.validation_service = Actionvalidation_service(self.state)

    def start(self, player_count:int, players_colors: List[PlayerColor]):
        self.state = self._create_initial_state(player_count, players_colors)
        self.exposed_state = self.state.hide_state()

    def _create_initial_state(self, player_count: int, player_colors: List[PlayerColor]) -> BoardState:
        
        self.deck = self._build_initial_deck(player_count)

        players = {color: self._create_player(color) for color in player_colors}

        cities = self._create_cities(player_count)

        market = self._create_starting_market()

        self.status = GameStatus.ONGOING
        
        current_turn = random.choice(list(players.keys()))

        actions_left = 1

        discard = []

        #burn initial cards
        for _ in players:
            self.deck.pop()

        return BoardState(cities=cities, players=players, deck=self.deck, market=market, era=LinkType.CANAL, current_turn=current_turn, actions_left=actions_left, discard=discard)
    
    def _build_initial_building_roster(self, player_color:PlayerColor) -> Dict[str, Building]:
        out = {}
        with open(self.BUILDING_ROSTER_PATH) as openfile:
            building_json:List[dict] = json.load(openfile)
        for building in building_json:
            building = Building(
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
                for _ in range(card_data['count']):
                    logging.debug(f"processing card data {card_data}")
                    card = Card(**card_data)
                    logging.debug(f"appending card{card}")
                    out.append(card)
        random.shuffle(out)
        return out
    
    def _create_cities(self, player_count:int) -> Dict[str, City]:
        '''
        Базовая генерация городов без связей
        '''
        out:Dict[str, City] = {}
        links_dict:dict[tuple, Link] = {}
        with open(self.CITIES_LIST_PATH) as cityfile:
            cities_data:dict = json.load(cityfile)
        for city_data in cities_data:
            city_name = city_data['name']
            logging.debug(f'creating city {city_name}')
            logging.debug(f'merchant player count: {city_data["player_count"]}') if 'player_count' in city_data.keys() else logging.debug('not a merchant')
            slots=[BuildingSlot(
                    city=city_name,
                    industry_type_options=[IndustryType(industry) for industry in slot]
                ) for slot in city_data['slots']] if 'slots' in city_data.keys() else []
            city = (City(
                name=city_name,
                slots={slot.id: slot for slot in slots},
                is_merchant=city_data.get('merchant', False),
                links={},
                merchant_min_players=city_data.get('player_count')
            ))
            out[city_name] = city

        '''
        Создаем линки
        '''

        for city_data in cities_data:
            added_link_keys = set()
            city_name = city_data['name']
            logging.debug(f'Processing links for city {city_name}')
            city = out[city_name]
            for link_data in city_data['links']:
                if 'group' in link_data:
                    group_name = link_data['group']
                    group_cities = self.SPECIAL_CITY_GROUPS[group_name]
                    for transport_type in link_data['transport']:
                        link_key = f'{group_name}_{transport_type}'
                        if link_key not in added_link_keys:
                            if link_key not in links_dict:
                                link = Link(
                                    type=LinkType(transport_type),
                                    cities=group_cities
                                )
                                links_dict[link_key] = link
                            link = links_dict[link_key]
                            city.links[link.id] = link
                            added_link_keys.add(link_key)
                else:
                    linked_city_name = link_data['name']
                    for transport_type in link_data['transport']:
                        cities_key = tuple(sorted([city_name, linked_city_name]))
                        link_key = f'{cities_key}-{transport_type}'
                        if link_key not in links_dict:
                            link = Link(
                                type=LinkType(transport_type),
                                cities=[city_name, linked_city_name]
                            )
                            links_dict[link_key] = link
                        link = links_dict[link_key]
                        city.links[link.id] = (link)
                        added_link_keys.add(link_key)
        
        '''
        Размещаем коммивояжеров
        '''
        all_merchants = [city for city in out.values() if city.is_merchant] 
        playable_merchants = [city for city in all_merchants if city.merchant_min_players <= player_count]
        empty_merchants = [city for city in all_merchants if city.merchant_min_players > player_count]
        tokens = []
        with open(self.MERCHANTS_TOKENS_PATH) as merchantsfile:
            tokens_data = json.load(merchantsfile)
        for token_data in tokens_data:
            if token_data['player_count'] <= player_count:
                tokens.append(MerchantType(token_data['type']))
        random.shuffle(tokens)
        for city in playable_merchants:
            city.merchant_slots = {}
            if city.name != self.SPECIAL_MERCHANT:
                for _ in range(2):
                    token = tokens.pop()
                    slot = MerchantSlot(
                        city=city.name,
                        merchant_type=token
                    )
                    logging.debug(f'Placed token {token} in city {city.name}')
                    city.merchant_slots[slot.id] = slot
            else:
                token = tokens.pop()
                slot = MerchantSlot(
                    city=city.name,
                    merchant_type=token
                )
                logging.debug(f'Placed token {token} in city {city.name}')
                city.merchant_slots[slot.id] = slot
        for city in empty_merchants:
            city.merchant_slots = {}
            for _ in range(2):
                slot = MerchantSlot(city=city.name, merchant_type=MerchantType.EMPTY)
                city.merchant_slots[slot.id] = slot
        return out
    
    def _create_starting_market(self) -> Market:
        coal_count = 13
        iron_count = 8
        market = Market(coal_count=coal_count, iron_count=iron_count, coal_cost=0, iron_cost=0)
        market = self.calculate_market_costs(market)
        return market
    
    def calculate_market_costs(self, market: Market) -> Market:
        coal_cost = self.COAL_MAX_COST - math.ceil(market.coal_count / 2)
        iron_cost = self.IRON_MAX_COST - math.ceil(market.iron_count / 2)
        return Market(coal_cost=coal_cost, iron_cost=iron_cost, coal_count=market.coal_count, iron_count=market.iron_count)
    
    def get_player_state(self, color:PlayerColor) -> PlayerState:
        return PlayerState(
            common_state=self.state.hide_state(),
            your_color=color,
            your_hand={card.id: card for card in self.state.players[color].hand.values()}
        )
    
    def play_action(self, action:Action, color:PlayerColor) -> ExecutionResult:
        player = self.state.players[color]
        validation_result = self.validation_service.validate_action(action, player)
        if not validation_result.is_valid:
            return ExecutionResult(executed=False, message=validation_result.message)
        pass
        
        

if __name__ == '__main__':
    game = Game(4)
    print(game)