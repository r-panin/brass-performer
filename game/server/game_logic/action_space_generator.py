from ...schema import (
    ActionContext,
    PlayerColor,
    Action,
    Building,
    ShortfallAction,
    LoanAction,
    PassAction,
    SellAction,
    BuildAction,
    ScoutAction,
    DevelopAction,
    NetworkAction,
    Player,
    IndustryType,
    ResourceType,
    ResourceSource,
    CardType,
    MerchantType,
    LinkType,
    CommitAction,
)
from typing import List
from collections import defaultdict
import itertools
from .action_cat_provider import ActionsCatProvider
from .services.board_state_service import BoardStateService


class ActionSpaceGenerator():
    def __init__(self):
        self.cat_getter = ActionsCatProvider()

    def get_action_space(self, state_service:BoardStateService, color:PlayerColor) -> List[Action]:
        player = state_service.get_player(color)
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
                    out.extend(self.get_valid_develop_actions(state_service, player, gloucester=state_service.get_action_context() == ActionContext.GLOUCESTER_DEVELOP))
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
        out: List[BuildAction] = []
        append_out = out.append

        cards = player.hand.values()

        # Собираем доступные для строительства или перестройки слоты по городам
        slots_by_city: dict = {}
        state = state_service.get_board_state()
        for city in state.cities.values():
            city_slots = city.slots.values()
            buildings_in_city = [s.building_placed for s in city_slots if s.building_placed is not None]
            if state_service.get_era() == LinkType.CANAL and any(b.owner == player.color for b in buildings_in_city): # check for 1 building per city per player in canal era
                slots_by_city[city.name] = []
                continue
            for slot in city_slots:
                if (slot.building_placed is None or self._overbuildable(slot.building_placed, player, state_service)):
                    slots_by_city.setdefault(slot.city, []).append(slot)

        industries = list(IndustryType)

        # Предварительные данные по железу (общие)
        iron_buildings = state_service.get_player_iron_sources()
        iron_sources = [ResourceSource(resource_type=ResourceType.IRON, building_slot_id=b.slot_id) for b in iron_buildings]
        iron_amounts = {b.slot_id: b.resource_count for b in iron_buildings}
        total_iron_available = sum(iron_amounts.values())
        market_iron = ResourceSource(resource_type=ResourceType.IRON)
        market_coal = ResourceSource(resource_type=ResourceType.COAL)

        network = state_service.get_player_network(player.color)

        # Кеш по углю на город
        coal_data_cache: dict = {}

        def get_coal_data_for_city(city_name: str):
            cached = coal_data_cache.get(city_name)
            if cached is not None:
                return cached

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

                if priority == first_priority:
                    coal_sources.append(ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id))
                    coal_amounts[building.slot_id] = building.resource_count
                else:
                    if second_priority is None:
                        second_priority = priority
                    if priority == second_priority:
                        coal_secondary_sources.append(ResourceSource(resource_type=ResourceType.COAL, building_slot_id=building.slot_id))
                        secondary_coal_amounts[building.slot_id] = building.resource_count
                    else:
                        break

            primary_coal_available = sum(coal_amounts.values())
            secondary_coal_available = sum(secondary_coal_amounts.values())

            data = {
                'market_coal_available': market_coal_available,
                'coal_sources': coal_sources,
                'coal_secondary_sources': coal_secondary_sources,
                'coal_amounts': coal_amounts,
                'secondary_coal_amounts': secondary_coal_amounts,
                'primary_coal_available': primary_coal_available,
                'secondary_coal_available': secondary_coal_available,
            }
            coal_data_cache[city_name] = data
            return data

        # Предрасчет приоритета слотов по отраслям в каждом городе (min-слоты для индустрии)
        allowed_slots_per_city_industry: dict = {}
        for city_name, city in state.cities.items():
            
            # min len per industry
            local_min = {}
            for industry in IndustryType:
                for slot in slots_by_city.get(city_name, []):
                    if industry in slot.industry_type_options:
                        if len(slot.industry_type_options) < local_min.get(industry, 10**9):
                            local_min[industry] = len(slot.industry_type_options)

            # allowed slots set per industry (only slots with minimal options_len for that industry)
            per_industry = {ind: [] for ind in IndustryType}
            for slot in slots_by_city.get(city_name, []):
                options_len = len(slot.industry_type_options)
                for ind in slot.industry_type_options:
                    if local_min.get(ind, 10**9) == options_len:
                        per_industry[ind].append(slot)
                
            allowed_slots_per_city_industry[city_name] = per_industry
        
        allowed_industry_for_card: dict = {}
        for card in cards:
            if card.card_type == CardType.CITY:
                allowed_industry_for_card[card.id] = set(IndustryType)
            else:
                if card.value == 'box-cotton':
                    allowed_industry_for_card[card.id] = {IndustryType.BOX, IndustryType.COTTON}
                elif card.value == 'wild':
                    allowed_industry_for_card[card.id] = set(IndustryType)
                else:
                    allowed_industry_for_card[card.id] = {IndustryType(card.value)}


        # Утилиты по ресурсам
        def generate_resource_combinations(coal_required: int, iron_required: int, coal_data: dict):
            combinations = []

            # Угольные опции с учетом приоритетов
            coal_options = []
            if coal_required > 0:
                primary_avail = coal_data['primary_coal_available']
                secondary_avail = coal_data['secondary_coal_available']
                coal_options.extend(coal_data['coal_sources'])
                if primary_avail < coal_required:
                    coal_options.extend(coal_data['coal_secondary_sources'])
                # быстрый отсев невозможных случаев без рынка
                if (primary_avail + secondary_avail < coal_required) and not coal_data['market_coal_available']:
                    return []
                if (primary_avail + secondary_avail < coal_required) and coal_data['market_coal_available']:
                    coal_options.append(market_coal)

            # Железные опции
            if iron_required > 0:
                iron_options = list(iron_sources)
                if total_iron_available < iron_required or not iron_sources:
                    iron_options.append(market_iron)
            else:
                iron_options = []

            # Комбинации для угля (max 2)
            if coal_required == 0:
                coal_combinations = [()]
            elif coal_required == 1:
                coal_combinations = [(src,) for src in coal_options]
            else:
                coal_combinations = list(itertools.combinations_with_replacement(coal_options, 2))

            # Комбинации для железа (max 2)
            if iron_required == 0:
                iron_combinations = [()]
            elif iron_required == 1:
                iron_combinations = [(src,) for src in iron_options]
            else:
                iron_combinations = list(itertools.combinations_with_replacement(iron_options, 2))

            for cc in coal_combinations:
                for ic in iron_combinations:
                    combinations.append((cc, ic))
            return combinations

        def is_resource_combination_valid(coal_comb, iron_comb, coal_data, iron_amounts_map):
            market_coal_count = 0
            market_iron_count = 0

            # track usage per slot
            coal_used = {}
            iron_used = {}

            # validate coal part
            for r in coal_comb:
                if r.building_slot_id is None:
                    market_coal_count += 1
                else:
                    sid = r.building_slot_id
                    # primary or secondary buckets
                    if sid in coal_data['coal_amounts']:
                        limit = coal_data['coal_amounts'][sid]
                    else:
                        limit = coal_data['secondary_coal_amounts'].get(sid, 0)
                    used = coal_used.get(sid, 0) + 1
                    if used > limit:
                        return False, 0, 0
                    coal_used[sid] = used

            # must use at least one primary if any exist
            if coal_data['coal_amounts'] and not any((sid in coal_data['coal_amounts']) for sid in coal_used.keys()):
                return False, 0, 0

            if market_coal_count > 0 and not coal_data['market_coal_available']:
                return False, 0, 0

            # validate iron part
            for r in iron_comb:
                if r.building_slot_id is None:
                    market_iron_count += 1
                else:
                    sid = r.building_slot_id
                    used = iron_used.get(sid, 0) + 1
                    if used > iron_amounts_map.get(sid, 0):
                        return False, 0, 0
                    iron_used[sid] = used

            return True, market_coal_count, market_iron_count

        # Основные циклы: по картам → индустриям → городам/слотам
        # кэши для комбо и рыночных стоимостей
        resource_combo_cache: dict = {}
        coal_cost_cache: dict[int, int] = {}
        iron_cost_cache: dict[int, int] = {}
        calculate_coal_cost = state_service.calculate_coal_cost
        calculate_iron_cost = state_service.calculate_iron_cost
        player_bank = player.bank

        for card in cards:
            # Допустимые города для карты
            if card.card_type == CardType.CITY:
                if card.value == 'wild':
                    valid_cities = set(slots_by_city.keys())
                else:
                    valid_cities = {card.value} if card.value in slots_by_city else set()
            else:
                valid_cities = network

            if not valid_cities:
                continue

            for industry in industries:
                # check card-industry compatibility
                if not industry in allowed_industry_for_card[card.id]:
                    continue
                # Текущий нижний уровень здания данной индустрии
                building = state_service.get_current_building(player, industry)
                if not building:
                    continue

                #check era exclusion
                if building.era_exclusion is not None and building.era_exclusion != state_service.get_era():
                    continue

                cost = building.get_cost()
                base_money = cost.money
                if player_bank < base_money:
                    continue

                coal_required = cost.coal
                iron_required = cost.iron

                for city_name in valid_cities:
                    city_slots = slots_by_city.get(city_name)
                    if not city_slots:
                        continue

                    coal_data = get_coal_data_for_city(city_name)

                    # Только слоты, допускаемые правилом приоритета для данной индустрии
                    allowed_slots = allowed_slots_per_city_industry[city_name].get(industry, [])
                    if not allowed_slots:
                        continue

                    # подготовить валидные комбинации ресурсов для города и требований
                    cache_key = (city_name, coal_required, iron_required)
                    combos = resource_combo_cache.get(cache_key)
                    if combos is None:
                        combos = []
                        for coal_comb, iron_comb in generate_resource_combinations(coal_required, iron_required, coal_data):
                            valid, market_coal_count, market_iron_count = is_resource_combination_valid(
                                coal_comb, iron_comb, coal_data, iron_amounts
                            )
                            if not valid:
                                continue
                            combos.append((coal_comb, iron_comb, market_coal_count, market_iron_count))
                        resource_combo_cache[cache_key] = combos

                    for slot in allowed_slots:
                        # индустрия должна поддерживаться слотом
                        if industry not in slot.industry_type_options:
                            continue 

                        # Комбинации ресурсов и валидация
                        for coal_comb, iron_comb, market_coal_count, market_iron_count in combos:
                            coal_cost = coal_cost_cache.get(market_coal_count)
                            if coal_cost is None:
                                coal_cost = calculate_coal_cost(market_coal_count) if market_coal_count else 0
                                coal_cost_cache[market_coal_count] = coal_cost
                            iron_cost = iron_cost_cache.get(market_iron_count)
                            if iron_cost is None:
                                iron_cost = calculate_iron_cost(market_iron_count) if market_iron_count else 0
                                iron_cost_cache[market_iron_count] = iron_cost
                            total = base_money + coal_cost + iron_cost
                            if player_bank < total:
                                continue

                            resources_used = list(coal_comb) + list(iron_comb)
                            append_out(BuildAction(
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
        overbuild_with = state_service.get_current_building(player, to_overbuild.industry_type)
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
                IndustryType.COAL: state_service.get_market_coal_count(),
                IndustryType.IRON: state_service.get_market_iron_count(),
            }
            if resource_checks.get(to_overbuild.industry_type, 0) > 0:
                return False

        return True

    def get_valid_sell_actions(self, state_service:BoardStateService, player:Player) -> List[SellAction]:
        out = []
        cards = player.hand
        slots = [
                slot 
                for city in state_service.get_cities().values() 
                for slot in city.slots.values() 
                if slot.building_placed is not None and slot.building_placed.is_sellable() and slot.building_placed.owner == player.color
            ] 

        # Предрасчет купцов с пивом, доступных из города
        connected_merchant_beer_by_city: dict[str, list[ResourceSource]] = {}
        for city in state_service.get_cities().values():
            city_name = city.name
            sources: list[ResourceSource] = []
            for s in state_service.iter_merchant_slots():
                if not s.beer_available:
                    continue
                if not state_service.are_connected(city_name, s.city):
                    continue
                # тип соответствия проверим позже по индустрии строения
                sources.append(ResourceSource(resource_type=ResourceType.BEER, merchant_slot_id=s.id))
            connected_merchant_beer_by_city[city_name] = sources

        for slot in slots:
            if not state_service.can_sell(slot.city, slot.building_placed.industry_type):
                continue

            beer_required = slot.building_placed.sell_cost
            if not beer_required:
                beer_buildings = []
                beer_sources = []
                beer_amounts = {}
                beer_combinations = [()]
            else:
                beer_buildings = state_service.get_player_beer_sources(player.color, city_name=slot.city)
                beer_sources = [ResourceSource(resource_type=ResourceType.BEER, building_slot_id=building.slot_id) for building in beer_buildings]
                # купцы: тип соответствует индустрии ИЛИ ANY
                merchant_sources = []
                for src in connected_merchant_beer_by_city.get(slot.city, []):
                    s = state_service.get_merchant_slot(src.merchant_slot_id)
                    if s.merchant_type == MerchantType.ANY or s.merchant_type == MerchantType(slot.building_placed.industry_type):
                        merchant_sources.append(src)
                beer_sources.extend(merchant_sources)
                beer_amounts = {b.slot_id: b.resource_count for b in beer_buildings}
                beer_combinations = itertools.combinations_with_replacement(beer_sources, beer_required)
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
        links = [link for link in state_service.iter_links()
            if link.owner is None and not network.isdisjoint(link.cities) and state_service.get_era() in link.type]
        base_cost = state_service.get_link_cost(state_service.subaction_count)
        if base_cost.money > player.bank:
            return out
        
        if state_service.get_era() == LinkType.CANAL:
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
                    if market_cost + base_cost.money > player.bank:
                        continue
                    coal_sources = [ResourceSource(resource_type=ResourceType.COAL)]  # market coal
                else:
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
            building = state_service.get_current_building(player, industry)
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
