from ...schema import BoardState, PlayerColor, Action, ShortfallAction, LoanAction, PassAction, SellAction, BuildAction, ScoutAction, DevelopAction,NetworkAction, SellAction, Player, IndustryType, ResourceType, ResourceSource, CardType, MerchantType, LinkType, CommitAction
from typing import Dict, List
from collections import defaultdict
import itertools
import logging
from .action_cat_provider import ActionsCatProvider


class ActionSpaceGenerator():
    INDUSTRY_RESOURCE_OPTIONS:Dict[IndustryType, set[tuple[ResourceType]]] = {
        IndustryType.BOX: {(ResourceType.COAL), (ResourceType.IRON), (ResourceType.COAL, ResourceType.COAL), (), (ResourceType.COAL, ResourceType.IRON), (ResourceType.IRON, ResourceType.IRON)},
        IndustryType.IRON: {(ResourceType.COAL)},
        IndustryType.COAL: {(), (ResourceType.IRON)},
        IndustryType.BREWERY: {(ResourceType.IRON)},
        IndustryType.COTTON: {(), (ResourceType.COAL), (ResourceType.COAL, ResourceType.IRON)},
        IndustryType.POTTERY: {(ResourceType.IRON), (ResourceType.COAL), (ResourceType.COAL, ResourceType.COAL)}
    }
    def __init__(self):
        self.cat_getter = ActionsCatProvider()

    def get_action_space(self, state:BoardState, color:PlayerColor) -> List[Action]:
        player = state.players[color]
        valid_action_types = self.cat_getter.get_expected_params(state)
        out = []
        for action in valid_action_types:
            match action:
                case "BuildAction":
                    out.extend(self.get_valid_build_actions(state, player))
                case "SellAction":
                    out.extend(self.get_valid_sell_actions(state, player))
                case "NetworkAction":
                    out.extend(self.get_valid_network_actions(state, player))
                case "DevelopAction":
                    out.extend(self.get_valid_develop_actions(state, player))
                case "ScoutAction":
                    out.extend(self.get_valid_scout_actions(player))
                case "LoanAction":
                    out.extend(self.get_valid_loan_actions(player))
                case "PassAction":
                    out.extend(self.get_valid_pass_actions(player))
                case "CommitAction":
                    out.extend(self.get_valid_commit_actions(state))
                case "ShortfallAction":
                    out.extend(self.get_valid_shortfall_actions(player))
        logging.debug(f"Generator returns a list of actions: {out}")
        return out
                

    def get_valid_build_actions(self, state:BoardState, player: Player) -> List[BuildAction]: # oh boy
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
                first_priority = None
                second_priority = None
                for building, priority in coal_buildings:
                    if first_priority is None:
                        first_priority = priority

                    if priority == first_priority:  # Primary sources
                        coal_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                        coal_amounts[building.slot_id] = building.resource_count

                    else:  # Secondary sources
                        second_priority = priority

                    if priority == second_priority:
                        coal_secondary_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                        secondary_coal_amounts[building.slot_id] = building.resource_count
                    
                    else:
                         break

                primary_coal_available = sum(coal_amounts.values())
                secondary_coal_available = sum(secondary_coal_amounts.values())

                for industry in industries:

                    other_city_slots = [s for s in state.cities[slot.city].slots.values() if slot.id != s.id]
                    for s in other_city_slots:
                        if (len(s.industry_type_options) < len(slot.industry_type_options)) and industry in s.industry_type_options:
                            continue

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
                        if slot.city not in network:
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
                        
                        out.append(BuildAction(
                            slot_id=slot.id,
                            card_id=card.id,
                            industry=industry,
                            resources_used=resources_used
                        ))
        
        data_strings = sorted(action.model_dump_json() for action in out)
        return [BuildAction.model_validate_json(data) for data in data_strings]

    def get_valid_sell_actions(self, state:BoardState, player:Player) -> List[SellAction]:
        out = []
        cards = player.hand
        slots = [
                slot 
                for city in state.cities.values() 
                for slot in city.slots.values() 
                if slot.building_placed is not None and slot.building_placed.is_sellable() and slot.building_placed.owner == player.color
            ] 

        for slot in slots:
            if not state.can_sell(slot.city, slot.building_placed.industry_type):
                continue

            beer_buildings = state.get_player_beer_sources(player.color, city_name=slot.city)
            beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=building.slot_id) for building in beer_buildings]
            merchant_sources = [ResourceSource(resource_type=ResourceType.BEER, merchant_slot_id=s.id)
                                for s in state.iter_merchant_slots()
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

                if state.subaction_count > 0:
                    out.append(SellAction(
                        slot_id=slot.id,
                        resources_used=beer_combo))
                else:
                    for card in cards:
                        out.append(SellAction(
                            slot_id=slot.id,
                            resources_used=beer_combo,
                            card_id=card
                        ))

        data_strings = sorted(action.model_dump_json() for action in out)
        return [SellAction.model_validate_json(data) for data in data_strings]

    def get_valid_network_actions(self, state:BoardState, player:Player) -> List[NetworkAction]:
        out = []
        if state.subaction_count > 1:
            return out
        cards = player.hand
        network = state.get_player_network(player.color)
        links = [link for link in state.links.values() 
            if link.owner is None and not network.isdisjoint(link.cities) and state.era in link.type]
        base_cost = state.get_link_cost(state.subaction_count)
        if base_cost.money > player.bank:
            return out
        
        for link in links:
            if state.era == LinkType.CANAL:
                if state.subaction_count == 0:
                    for card in cards:
                        out.append(NetworkAction(
                            link_id=link.id,
                            card_id=card,
                            resources_used=[]
                        ))
                else:
                    return []
            else: # gulp
                coal_buildings = state.get_player_coal_sources(link_id=link.id)
                coal_sources = []
                first_priority = None
                for building, priority in coal_buildings:
                    if first_priority is None:
                        first_priority = priority

                    if priority == first_priority:  # Primary sources
                        coal_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                    else:
                        break
                
                if not coal_sources:
                    if any(state.market_access_exists(city_name=city) for city in link.cities):
                        market_cost = state.market.calculate_coal_cost(base_cost.coal)
                        coal_sources = [[ResourceSource(resource_type=ResourceType.COAL)]] # market coal
                    else:
                        continue
                
                    if market_cost + base_cost.money > player.bank:
                        continue
                
                beer_buildings = state.get_player_beer_sources(color=player.color, link_id=link.id)
                beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=b.slot_id) for b in beer_buildings]
                if state.subaction_count > 0:
                    for coal_source, beer_source in itertools.product(coal_sources, beer_sources):
                        res = list(coal_source) + list(beer_source)
                        out.append(NetworkAction(
                            resources_used=res,
                            link_id=link.id
                        ))
                else:
                    for coal_source, card in itertools.product(coal_sources, cards):
                        res = list(coal_source)
                        out.append(NetworkAction(
                            resources_used=res,
                            link_id=link.id,
                            card_id=card
                        ))

        data_strings = sorted(action.model_dump_json() for action in out)
        return [NetworkAction.model_validate_json(data) for data in data_strings]
                        
    def get_valid_develop_actions(self, state:BoardState, player:Player, gloucester=False) -> List[DevelopAction]:
        out = []
        if state.subaction_count > 1:
            return out 
        industries = list(IndustryType)
        cards = player.hand
        iron_buildings = state.get_player_iron_sources()
        if not gloucester:
            if iron_buildings:
                iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=building.slot_id) for building in iron_buildings]
            else:
                cost = state.market.calculate_iron_cost(state.get_develop_cost().iron)
                if cost > player.bank:
                    return []
                iron_sources = [[ResourceSource(resource_type=ResourceType.IRON)]]
        else:
            iron_sources = [[]]
        for industry in industries:
            building = player.get_lowest_level_building(industry)
            if not building.is_developable:
                continue
            if not building:
                continue
            if iron_sources:
                for source in iron_sources:
                    if state.subaction_count > 0:
                        out.append(DevelopAction(industry=industry, resources_used=source))
                    else:
                        for card in cards:
                            out.append(DevelopAction(industry=industry, resources_used=source, card_id=card))
        data_strings = sorted(action.model_dump_json() for action in out)
        return [DevelopAction.model_validate_json(data) for data in data_strings]

    def get_valid_scout_actions(self, player:Player) -> List[ScoutAction]:
        cards = player.hand.values()
        out = []
        if len(cards) < 3:
            return []
        if any(card.value == 'wild' for card in cards):
            return []
        ids = [card.id for card in cards]
        for combo in itertools.combinations(ids, 3):
            out.append(ScoutAction(card_id=list(combo)))
        data_strings = sorted(action.model_dump_json() for action in out)
        return [ScoutAction.model_validate_json(data) for data in data_strings]

    def get_valid_loan_actions(self, player:Player) -> List[LoanAction]:
        if player.income < -7:
            return []
        return [LoanAction(card_id=card) for card in player.hand]
    
    def get_valid_pass_actions(self, player:Player) -> List[PassAction]:
        return [PassAction(card_id=card) for card in player.hand]

    def get_valid_commit_actions(self, state:BoardState):
        if state.subaction_count > 0:
            return [CommitAction()]
        else:
            return []
    
    def get_valid_shortfall_actions(self, state:BoardState, player:Player):
        buildings = [building for building in state.iter_placed_buildings() if building.owner is player.color]
        if buildings:
            return [ShortfallAction(slot_id=building.slot_id) for building in buildings]
        else:
            return [ShortfallAction()]

    def _remove_duplicates(self, lst):
        seen = set()
        result = []
        for sublist in lst:
            key = tuple(sorted(item.model_dump_json() for item in sublist))
            if key not in seen:
                seen.add(key)
                result.append(sublist)
        return result