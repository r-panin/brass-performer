from ...schema import PlayerColor, BoardState, LinkType, Building, Player, Card, CardType, City, MerchantSlot, MerchantType, BuildingSlot, IndustryType, Link, Market, ActionContext
from pathlib import Path
from typing import List, Dict
import random
import json


class GameInitializer():

    RES_PATH = Path(r'C:\brass\brass-performer\game\server\res')
    BUILDING_ROSTER_PATH = Path(RES_PATH / 'building_table.json')
    CARD_LIST_PATH = Path(RES_PATH / 'card_list.json')
    CITIES_LIST_PATH = Path(RES_PATH / 'cities_list.json')
    MERCHANTS_TOKENS_PATH = Path(RES_PATH /'merchant_tokens.json')
    LINKS_PATH = Path(RES_PATH / 'city_links.json')


    def create_initial_state(self, player_count: int, player_colors: List[PlayerColor]) -> BoardState:
        
        self.deck = self._build_initial_deck(player_count)

        players = {color: self._create_player(color) for color in player_colors}

        cities = self._create_cities(player_count)

        links = self._create_links()

        market = self._create_starting_market()

        turn_order = player_colors
        
        random.shuffle(turn_order)

        actions_left = 1

        discard = []

        wilds = self._build_wild_deck()

        context = ActionContext.MAIN

        #burn initial cards
        for _ in players:
            self.deck.pop()

        return BoardState(cities=cities, players=players, deck=self.deck, market=market, era=LinkType.CANAL, turn_order=turn_order, actions_left=actions_left, discard=discard, wilds=wilds, links=links, action_context=context)
    
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
                card = Card(
                    id=card_data["id"],
                    card_type=CardType(card_data["card_type"]),
                    value=card_data["value"]
                )
                out.append(card)
        random.shuffle(out)
        return out

    def _build_wild_deck(self) -> List[Card]:
        INDUSTRY_ID = 65
        CITY_ID = 66
        return [Card(card_type=CardType.INDUSTRY, id=INDUSTRY_ID, value='wild'), Card(card_type=CardType.CITY, id=CITY_ID, value='wild')]

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
        return market