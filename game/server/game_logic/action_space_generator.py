from ...schema import PlayerColor, Action, LoanStart, PassStart, SellStart, BuildStart, ScoutStart, DevelopStart,NetworkStart, SellSelection, BuildSelection, Player, IndustryType, ResourceType, ResourceSource, CardType, MerchantType
from typing import Dict, List
from collections import Counter, defaultdict
import itertools
from .game_state_manager import GameStateManager

class ActionSpaceGenerator():
    INDUSTRY_RESOURCE_OPTIONS:Dict[IndustryType, set[tuple[ResourceType]]] = {
        IndustryType.BOX: {(ResourceType.COAL), (ResourceType.IRON), (ResourceType.COAL, ResourceType.COAL), (), (ResourceType.COAL, ResourceType.IRON), (ResourceType.IRON, ResourceType.IRON)},
        IndustryType.IRON: {(ResourceType.COAL)},
        IndustryType.COAL: {(), (ResourceType.IRON)},
        IndustryType.BREWERY: {(ResourceType.IRON)},
        IndustryType.COTTON: {(), (ResourceType.COAL), (ResourceType.COAL, ResourceType.IRON)},
        IndustryType.POTTERY: {(ResourceType.IRON), (ResourceType.COAL), (ResourceType.COAL, ResourceType.COAL)}
    }
    def __init__(self, state_manager:GameStateManager):
        self.state_manager = state_manager

    @property
    def state(self):
        return self.state_manager.current_state

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

    def get_valid_build_actions(self, player: Player) -> List[BuildSelection]: # oh boy
        out = []
        cards = player.hand.values()
        slots = [slot for city in self.state.cities.values() for slot in city.slots.values() if not slot.building_placed]
        industries = list(IndustryType)

        iron_buildings = self.state.get_player_iron_sources()
        iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=building.slot_id) for building in iron_buildings]
        iron_amounts = {building.slot_id: building.resource_count for building in iron_buildings}
        total_iron_available = sum(iron_amounts.values())

        market_iron = ResourceSource(resource_type=ResourceType.IRON)
        market_coal = ResourceSource(resource_type=ResourceType.COAL)

        network = self.state.get_player_network(player.color)

        for card in cards:
            for slot in slots:
                market_coal_available = self.state.market_access_exists(slot.city)
                
                # Получаем ВСЕ источники угля с приоритетами
                coal_buildings = self.state.get_player_coal_sources(city_name=slot.city)
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
                            
                        coal_cost = self.state.market.calculate_coal_cost(market_coal_count)
                        iron_cost = self.state.market.calculate_iron_cost(market_iron_count)
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

    def get_valid_sell_actions(self, player:Player, subaction_count:int) -> List[SellSelection]:
        out = []
        cards = player.hand.values()
        slots = [
                slot 
                for city in self.state.cities.values() 
                for slot in city.slots.values() 
                if slot.building_placed is not None and slot.building_placed.is_sellable() and slot.building_placed.owner == player.color
            ] 

        for slot in slots:
            if not self.state.can_sell(slot.city, slot.building_placed.industry_type):
                continue

            beer_buildings = self.state.get_player_beer_sources(player.color, city_name=slot.city)
            beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=building.slot_id) for building in beer_buildings]
            merchant_sources = [ResourceSource(resource_type=ResourceType.BEER, merchant_slot_id=s.id)
                                for s in self.state.iter_merchant_slots()
                                if s.beer_available and s.merchant_type in (MerchantType.ANY, MerchantType(slot.building_placed.industry_type))]
            beer_sources += merchant_sources
            beer_amounts = {b.slot_id: b.resource_count for b in beer_buildings}
            beer_required = slot.building_placed.sell_cost
            if beer_required:
                beer_combinations = itertools.combinations_with_replacement(beer_sources, beer_required)
            else:
                beer_combinations = [()]
            for beer_combo in beer_combinations:
                beer_used = defaultdict(int)
                merchant_beer_used = False
                valid = True
                for resource in beer_combo:
                    if resource.building_slot_id:
                        beer_used[resource.building_slot_id] += 1
                        if beer_used[resource.building_slot_id] > beer_amounts[resource.building_slot_id]:
                            valid = False
                            break
                    else:
                        if merchant_beer_used:
                            valid = False
                            break
                        merchant_beer_used = True
                
                if not valid:
                    continue

                if subaction_count > 0:
                    out.append(SellSelection(
                        slot_id=slot.id,
                        resources_used=beer_combo))
                else:
                    for card in cards:
                        out.append(SellSelection(
                            slot_id=slot.id,
                            resources_used=beer_combo,
                            card_id=card.id
                        ))

        data_strings = sorted(action.model_dump_json() for action in out)
        return [SellSelection.model_validate_json(data) for data in data_strings]

    def _get_theoretically_valid_build_actions(self, game) -> List[BuildSelection]:
        '''Gets all build action parameter permutations that could in theory be valid under a specific game self.state'''
        out = []

        '''Build cards'''
        cards = game._build_initial_deck(4)
        jokers = game._build_wild_deck()
        cards.append(next(joker for joker in jokers if joker.card_type == CardType.CITY))
        cards.append(next(joker for joker in jokers if joker.card_type == CardType.INDUSTRY))

        '''Build slots'''
        slots = [slot for city in game.self.state.cities.values() for slot in city.slots.values()]

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