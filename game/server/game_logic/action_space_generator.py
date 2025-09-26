from ...schema import ActionContext, PlayerColor, Action, Building, ShortfallAction, LoanAction, PassAction, SellAction, BuildAction, ScoutAction, DevelopAction,NetworkAction, SellAction, Player, IndustryType, ResourceType, ResourceSource, CardType, MerchantType, LinkType, CommitAction
from typing import Dict, List
from collections import defaultdict
import itertools
from .action_cat_provider import ActionsCatProvider
from .services.board_state_service import BoardStateService
import logging


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

    def get_action_space(self, state_service:BoardStateService, color:PlayerColor) -> List[Action]:
        player = state_service.state.players[color]
        valid_action_types = self.cat_getter.get_expected_params(state_service)
        out = []
        for action in valid_action_types:
            match action:
                case "BuildAction":
                    out.extend(self.get_valid_build_actions(state_service, player))
                case "SellAction":
                    out.extend(self.get_valid_sell_actions(state_service, player))
                case "NetworkAction":
                    out.extend(self.get_valid_network_actions(state_service, player))
                case "DevelopAction":
                    out.extend(self.get_valid_develop_actions(state_service, player, gloucester=state_service.state.action_context is ActionContext.GLOUCESTER_DEVELOP))
                case "ScoutAction":
                    out.extend(self.get_valid_scout_actions(player))
                case "LoanAction":
                    out.extend(self.get_valid_loan_actions(player))
                case "PassAction":
                    out.extend(self.get_valid_pass_actions(player))
                case "CommitAction":
                    out.extend(self.get_valid_commit_actions(state_service))
                case "ShortfallAction":
                    out.extend(self.get_valid_shortfall_actions(state_service, player))
        return out

    def get_valid_build_actions(self, state_service: BoardStateService, player: Player) -> List[BuildAction]:
        out = []
        cards = player.hand.values()
        
        # Предварительно собираем все свободные слоты, группируя по городам
        slots_by_city = {}
        for city in state_service.state.cities.values():
            for slot in city.slots.values():
                # Объединяем условия для пустого слота и возможности перестройки
                if not slot.building_placed or self._overbuildable(slot.building_placed, player, state_service):
                    slots_by_city.setdefault(slot.city, []).append(slot)

        industries = list(IndustryType)

        # Предварительно вычисляем данные по железу (не зависят от города)
        iron_buildings = state_service.get_player_iron_sources()
        iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=building.slot_id) for building in iron_buildings]
        iron_amounts = {building.slot_id: building.resource_count for building in iron_buildings}
        total_iron_available = sum(iron_amounts.values())
        market_iron = ResourceSource(resource_type=ResourceType.IRON)
        market_coal = ResourceSource(resource_type=ResourceType.COAL)

        network = state_service.get_player_network(player.color)

        # Кеш для данных по углю по городам (чтобы не вычислять многократно для одного города)
        coal_data_cache = {}

        def get_coal_data_for_city(city_name):
            if city_name in coal_data_cache:
                return coal_data_cache[city_name]
            
            market_coal_available = state_service.market_access_exists(city_name)
            coal_buildings = state_service.get_player_coal_sources(city_name=city_name)
            
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
                    if second_priority is None:
                        second_priority = priority
                    
                    if priority == second_priority:
                        coal_secondary_sources.append(
                            ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id)
                        )
                        secondary_coal_amounts[building.slot_id] = building.resource_count
                    else:
                        break  # Только первые два приоритета

            primary_coal_available = sum(coal_amounts.values())
            secondary_coal_available = sum(secondary_coal_amounts.values())
            
            data = {
                'market_coal_available': market_coal_available,
                'coal_sources': coal_sources,
                'coal_secondary_sources': coal_secondary_sources,
                'coal_amounts': coal_amounts,
                'secondary_coal_amounts': secondary_coal_amounts,
                'primary_coal_available': primary_coal_available,
                'secondary_coal_available': secondary_coal_available
            }
            
            coal_data_cache[city_name] = data
            return data

        def generate_resource_combinations(coal_required, iron_required, coal_data, iron_data):
            """Генерирует комбинации ресурсов с соблюдением приоритетов"""
            combinations = []
            
            # Формируем coal_options с соблюдением приоритетов
            coal_options = []
            if coal_required > 0:
                # 1. Primary sources всегда first
                coal_options.extend(coal_data['coal_sources'])
                
                # 2. Secondary sources только если primary недостаточно
                if coal_data['primary_coal_available'] < coal_required:
                    coal_options.extend(coal_data['coal_secondary_sources'])
                    
                # 3. Market coal только если своих источников недостаточно
                if (coal_data['primary_coal_available'] + coal_data['secondary_coal_available'] < coal_required 
                    and coal_data['market_coal_available']):
                    coal_options.append(market_coal)
            
            # Формируем iron_options (логика проще)
            iron_options = []
            if iron_required > 0:
                iron_options.extend(iron_sources)
                # Market iron если своего недостаточно или нет своих источников
                if iron_data['total_iron_available'] < iron_required or not iron_sources:
                    iron_options.append(market_iron)
            
            # Генерируем комбинации угля
            coal_combinations = []
            if coal_required == 0:
                coal_combinations = [()]
            elif coal_required == 1:
                coal_combinations = [(src,) for src in coal_options]
            else:  # coal_required == 2
                for i, src1 in enumerate(coal_options):
                    for j, src2 in enumerate(coal_options[i:], i):
                        coal_combinations.append((src1, src2))
            
            # Генерируем комбинации железа
            iron_combinations = []
            if iron_required == 0:
                iron_combinations = [()]
            elif iron_required == 1:
                iron_combinations = [(src,) for src in iron_options]
            else:  # iron_required == 2
                for i, src1 in enumerate(iron_options):
                    for j, src2 in enumerate(iron_options[i:], i):
                        iron_combinations.append((src1, src2))
            
            # Комбинируем
            for coal_comb in coal_combinations:
                for iron_comb in iron_combinations:
                    combinations.append((coal_comb, iron_comb))
            
            return combinations

        def is_resource_combination_valid(coal_comb, iron_comb, coal_data, iron_data, coal_required, iron_required):
            """Проверяет валидность комбинации ресурсов"""
            resources_used = list(coal_comb) + list(iron_comb)
            
            coal_used = {}
            iron_used = {}
            market_coal_count = 0
            market_iron_count = 0
            
            for resource in resources_used:
                if resource.resource_type == ResourceType.COAL:
                    if resource.building_slot_id:
                        # Проверяем как primary, так и secondary источники
                        if resource.building_slot_id in coal_data['coal_amounts']:
                            coal_used[resource.building_slot_id] = coal_used.get(resource.building_slot_id, 0) + 1
                            if coal_used[resource.building_slot_id] > coal_data['coal_amounts'][resource.building_slot_id]:
                                return False, None, None, None, None
                        elif resource.building_slot_id in coal_data['secondary_coal_amounts']:
                            coal_used[resource.building_slot_id] = coal_used.get(resource.building_slot_id, 0) + 1
                            if coal_used[resource.building_slot_id] > coal_data['secondary_coal_amounts'][resource.building_slot_id]:
                                return False, None, None, None, None
                    else:
                        market_coal_count += 1
                        
                elif resource.resource_type == ResourceType.IRON:
                    if resource.building_slot_id:
                        iron_used[resource.building_slot_id] = iron_used.get(resource.building_slot_id, 0) + 1
                        if iron_used[resource.building_slot_id] > iron_data['iron_amounts'][resource.building_slot_id]:
                            return False, None, None, None, None
                    else:
                        market_iron_count += 1
            
            # Проверка: должен быть использован хотя бы один primary источник угля если они есть
            primary_coal_ids = set(coal_data['coal_amounts'].keys())
            used_primary_coal_ids = {r.building_slot_id for r in resources_used if r.building_slot_id in primary_coal_ids}
            if primary_coal_ids and not used_primary_coal_ids:
                return False, None, None, None, None
            
            # Проверка доступности рыночного угля
            if market_coal_count > 0 and not coal_data['market_coal_available']:
                return False, None, None, None, None
                
            return True, resources_used, market_coal_count, market_iron_count, (coal_used, iron_used)

        # Основные циклы оптимизированы: сначала по картам, затем по отраслям, потом по городам
        for card in cards:
            # Определяем допустимые города для этой карты
            valid_cities = set()
            valid_industries = set()
            if card.card_type == CardType.CITY:
                if card.value == 'wild':
                    valid_cities = set(slots_by_city.keys())
                else:
                    valid_cities = {card.value} if card.value in slots_by_city else set()
                # Исключаем пивоварни для CITY карт
                valid_cities = {city for city in valid_cities if "brewery" not in city}
                valid_industries = {IndustryType}
            else:  # INDUSTRY карта
                valid_cities = network  # только города в сети
                if card.value == 'box-cotton':
                    valid_industries.add(IndustryType.BOX)
                    valid_industries.add(IndustryType.COTTON)
                elif card.value == 'wild':
                    valid_industries = set(IndustryType)
                else:
                    valid_industries.add(IndustryType(card.value)) 
            
            for industry in industries:
                building = state_service.get_lowest_level_building(player.color, industry)
                if not building:
                    continue
                    
                # Предварительно проверяем базовую стоимость
                base_cost = building.cost['money']
                if player.bank < base_cost:
                    continue
                    
                coal_required = building.cost['coal']
                iron_required = building.cost['iron']
                
                # Данные по железу не зависят от города
                iron_data = {
                    'iron_sources': iron_sources,
                    'iron_amounts': iron_amounts,
                    'total_iron_available': total_iron_available
                }
                
                for city in valid_cities:
                    if city not in slots_by_city:
                        continue
                        
                    # Получаем данные по углю для города (с кешированием)
                    coal_data = get_coal_data_for_city(city)
                    
                    for slot in slots_by_city[city]:
                        # Проверяем допустимость отрасли для слота
                        if industry not in slot.industry_type_options:
                            continue
                        
                        # Проверка приоритета строительства в слоте
                        can_build = True
                        other_city_slots = [s for s in state_service.state.cities[slot.city].slots.values() if slot.id != s.id]
                        for s in other_city_slots:
                            if (len(s.industry_type_options) < len(slot.industry_type_options)) and (industry in s.industry_type_options):
                                can_build = False
                                break
                        
                        if not can_build:
                            continue
                        
                        # Генерируем комбинации ресурсов
                        resource_combinations = generate_resource_combinations(
                            coal_required, iron_required, coal_data, iron_data
                        )
                        
                        for coal_comb, iron_comb in resource_combinations:
                            # Проверяем валидность комбинации
                            valid, resources_used, market_coal_count, market_iron_count, _ = is_resource_combination_valid(
                                coal_comb, iron_comb, coal_data, iron_data, coal_required, iron_required
                            )
                            
                            if not valid:
                                continue
                            
                            # Проверяем конечную стоимость
                            coal_cost = state_service.calculate_coal_cost(market_coal_count) if market_coal_count > 0 else 0
                            iron_cost = state_service.calculate_iron_cost(market_iron_count) if market_iron_count > 0 else 0
                            total_cost = base_cost + coal_cost + iron_cost
                            
                            if player.bank < total_cost:
                                continue
                            
                            out.append(BuildAction(
                                slot_id=slot.id,
                                card_id=card.id,
                                industry=industry,
                                resources_used=resources_used
                            ))
        
        return out 
    
    def _overbuildable(self, to_overbuild: Building, player: Player, state_service: BoardStateService) -> bool:
        # Проверяем уровень здания
        if to_overbuild is None:
            return True
        overbuild_with = state_service.get_lowest_level_building(player.color, to_overbuild.industry_type)
        if overbuild_with is None:
            return False
        if overbuild_with.level <= to_overbuild.level:
            return False

        # Если игрок не владелец - проверяем специальные условия
        if player.color != to_overbuild.owner:
            if to_overbuild.industry_type not in (IndustryType.COAL, IndustryType.IRON):
                return False
            
            # Для угля и железа проверяем доступность ресурсов
            resource_checks = {
                IndustryType.COAL: state_service.state.market.coal_count,
                IndustryType.IRON: state_service.state.market.iron_count
            }
            if resource_checks.get(to_overbuild.industry_type, 0) > 0:
                return False

        return True

    def get_valid_sell_actions(self, state_service:BoardStateService, player:Player) -> List[SellAction]:
        out = []
        cards = player.hand
        slots = [
                slot 
                for city in state_service.state.cities.values() 
                for slot in city.slots.values() 
                if slot.building_placed is not None and slot.building_placed.is_sellable() and slot.building_placed.owner == player.color
            ] 

        for slot in slots:
            if not state_service.can_sell(slot.city, slot.building_placed.industry_type):
                continue

            beer_buildings = state_service.get_player_beer_sources(player.color, city_name=slot.city)
            beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=building.slot_id) for building in beer_buildings]
            merchant_sources = [ResourceSource(resource_type=ResourceType.BEER, merchant_slot_id=s.id)
                                for s in state_service.iter_merchant_slots()
                                if s.beer_available and s.merchant_type in (MerchantType.ANY, MerchantType(slot.building_placed.industry_type) and state_service.are_connected(slot.city, s.city))]
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

                if state_service.subaction_count > 0:
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

        return out

    def get_valid_network_actions(self, state_service:BoardStateService, player:Player) -> List[NetworkAction]:
        out = []
        if state_service.subaction_count > 1:
            return out
        cards = player.hand
        network = state_service.get_player_network(player.color)
        links = [link for link in state_service.state.links.values() 
            if link.owner is None and not network.isdisjoint(link.cities) and state_service.state.era in link.type]
        base_cost = state_service.get_link_cost(state_service.subaction_count)
        if base_cost.money > player.bank:
            return out
        
        if state_service.state.era == LinkType.CANAL:
            if state_service.subaction_count == 0:
                return [NetworkAction(link_id=link.id, card_id=card, resources_used=[]) 
                   for link in links for card in player.hand]
            return [] 
        
        for link in links:
            coal_buildings = state_service.get_player_coal_sources(link_id=link.id)
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
                if any(state_service.market_access_exists(city_name=city) for city in link.cities):
                    market_cost = state_service.calculate_coal_cost(base_cost.coal)
                    coal_sources = [ResourceSource(resource_type=ResourceType.COAL)] # market coal
                else:
                    continue
            
                if market_cost + base_cost.money > player.bank:
                    continue
            
            beer_buildings = state_service.get_player_beer_sources(color=player.color, link_id=link.id)
            beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=b.slot_id) for b in beer_buildings]
            if state_service.subaction_count > 0:
                for coal_source in coal_sources:
                    for beer_source in beer_sources:
                        res = [coal_source, beer_source]
                        out.append(NetworkAction(
                            resources_used=res,
                            link_id=link.id
                        ))
            else:
                for coal_source in coal_sources:
                    for card in cards:
                        out.append(NetworkAction(
                            resources_used=[coal_source],
                            link_id=link.id,
                            card_id=card
                        ))

        return out
                        
    def get_valid_develop_actions(self, state_service:BoardStateService, player:Player, gloucester=False) -> List[DevelopAction]:
        cards = player.hand
        iron_buildings = state_service.get_player_iron_sources()
        if not gloucester:
            if iron_buildings:
                iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=building.slot_id) for building in iron_buildings]
            else:
                cost = state_service.calculate_iron_cost(state_service.get_develop_cost().iron)
                if cost > player.bank:
                    return []
                iron_sources = [ResourceSource(resource_type=ResourceType.IRON)]
        else:
            iron_sources = list()
        
        industries = []
        for industry in IndustryType:
            building = state_service.get_lowest_level_building(player.color, industry)
            if building and building.is_developable:
                industries.append(industry)

        if state_service.subaction_count > 0:
            if gloucester:
                return[DevelopAction(industry=industry, resources_used=[]) for industry in industries]
            return [DevelopAction(industry=industry, resources_used=[source])
                for industry in industries for source in iron_sources]
        else:
            return [DevelopAction(industry=industry, resources_used=[source], card_id=card)
                for industry in industries for source in iron_sources for card in cards]

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
        return out

    def get_valid_loan_actions(self, player:Player) -> List[LoanAction]:
        if player.income < -7:
            return []
        return [LoanAction(card_id=card) for card in player.hand]
    
    def get_valid_pass_actions(self, player:Player) -> List[PassAction]:
        return [PassAction(card_id=card) for card in player.hand]

    def get_valid_commit_actions(self, state_service:BoardStateService):
        logging.debug(f"Current subaction count is {state_service.subaction_count}")
        if state_service.subaction_count > 0:
            return [CommitAction()]
        else:
            return []
    
    def get_valid_shortfall_actions(self, state_service:BoardStateService, player:Player):
        buildings = [building for building in state_service.iter_placed_buildings() if building.owner is player.color]
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
