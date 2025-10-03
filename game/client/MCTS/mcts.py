from ...schema import PlayerState, Action
from typing import List
from ...server.game_logic.game import Game
from ...server.game_logic.action_space_generator import ActionSpaceGenerator
from ...server.game_logic.state_changer import StateChanger
from ...server.game_logic.services.board_state_service import BoardStateService
import random
import math
import logging
from copy import deepcopy


class Node:
    def __init__(self, parent:'Node'=None, action:Action=None, who_moved=None):
        self.parent = parent
        self.action = action
        self.children: List[Node] = []
        self.visits = 0
        self.value = float()
        self.who_moved = who_moved
        self.untried_actions: List[Action] = None
        if parent is not None and parent.action_history is not None:
            self.action_history = parent.action_history.copy()
        else:
            self.action_history = []
        if action is not None:
            self.action_history.append(action)
    
    def is_fully_expanded(self, legal_actions = List[Action]) -> bool:
        if self.untried_actions is None:
            return False
        return len(self.untried_actions) == 0

class RandomActionSelector:
    def select_action(self, legal_actions:List[Action], state) -> Action:
        try:
            return random.choice(legal_actions)
        except IndexError:
            print(f"COULDN'T FIND AN ACTION IN STATE {state.get_board_state().model_dump()}")

class MCTS:
    def __init__(self, simulations:int, exploration:float=2.0, depth:int=1000):
        self.simulations = simulations
        self.exploration = exploration
        self.max_depth = depth
        self.action_selector = RandomActionSelector()
        self.action_space_generator = ActionSpaceGenerator()
        self.root: Node | None = None

    def search(self, state:PlayerState):
        # Persist a single root across simulations for this search call
        root_info_set = deepcopy(state)
        if self.root is None:
            self.root = Node(parent=None, action=None, who_moved=None)
            determinized_state = self._determinize_state(root_info_set, [])
            legal_actions = self._get_legal_actions(determinized_state)
            self.root.untried_actions = legal_actions.copy()
            self.root.active_player = determinized_state.get_active_player().color

        for sim_idx in range(self.simulations):
            logging.debug(f"Running simulation #{sim_idx}")
            
            node, path = self._select(self.root)

            if not node.is_fully_expanded():
                new_node = self._expand(node, root_info_set)
                if new_node != node:
                    path.append(new_node)
                    node = new_node

            # Simulation: from the new state, rollout randomly to terminal
            simulation_result = self._simulate(node, root_info_set)

            # Backpropagate from root player's perspective
            self._backpropagate(path, simulation_result, root_info_set.your_color)

        best_action = self._get_best_action(self.root)
        # Reset tree after choosing to avoid mixing across turns
        self.root = None
        return best_action
    
    def _select(self, root:Node) -> tuple[Node, List[Node]]:
        node = root
        path = [node]

        while node.children:
            best_child = self._best_child(node)
            path.append(best_child)
            node = best_child
        return node, path
    
    def _best_child(self, node:Node) -> Node:
        best_score = -float('inf')
        best_child = None

        for child in node.children:
            if child.visits == 0:
                ucb_score = float('inf')
            else:
                exploitation = child.value / child.visits
                exploration = self.exploration * math.sqrt(max(0.0, math.log(max(1, node.visits))) / child.visits)
                ucb_score = exploitation + exploration
            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child
        
        return best_child
    
    def _get_best_action(self, root:Node):
        if not root.children:
            return None
        return max(root.children, key=lambda child: child.visits).action
    
    def _expand(self, node: Node, root_info_set: PlayerState) -> Node:
        determined_state = self._determinize_state(root_info_set, node.action_history)

        if node.untried_actions is None:
            legal_actions = self._get_legal_actions(determined_state)
            node.untried_actions = legal_actions.copy()
            node.active_player = determined_state.get_active_player().color

        if node.untried_actions:
            action = node.untried_actions.pop()
            child_node = Node(parent=node, action=action, who_moved=node.active_player)
            node.children.append(child_node)
            return child_node
        
        return node
    
    def _apply_action(self, state:BoardStateService, action:Action):
        active_player = state.get_active_player()
        state_changer = StateChanger(state)
        state_changer.apply_action(action, state, active_player)
        
    def _get_legal_actions(self, state: BoardStateService):
        actions_list = self.action_space_generator.get_action_space(state, state.get_active_player().color)
        return actions_list

    def _simulate(self, node:Node, root_info_set:PlayerState) -> dict:
        determinized_state = self._determinize_state(root_info_set, node.action_history)
        depth = 0
        while depth < self.max_depth and not determinized_state.is_terminal():
            action = self._select_action(determinized_state)
            self._apply_action(determinized_state, action)
            depth += 1
        return self._evaluate_state(determinized_state)

    def _determinize_state(self, root_info_set:PlayerState, action_history:List[Action]) -> BoardStateService:

        determined_state: BoardStateService = Game.from_partial_state(root_info_set, history=action_history).state_service 

        return determined_state
    
    def _evaluate_state(self, state: BoardStateService) -> dict:
        if state.is_terminal():
            players = sorted(
                state.get_players().values(), 
                key=lambda p: p.victory_points, 
                reverse=True
            )
            
            results = {}
            for idx, player in enumerate(players):
                normalized_score = 1.0 - (idx / (len(players) - 1)) if len(players) > 1 else 1.0
                results[player.color] = normalized_score
            
            return results
        else:
            return {p.color: random.random() for p in state.get_players().values()}

    def _backpropagate(self, path:List[Node], results:dict, root_player) -> None:
        reward = results.get(root_player, 0.0)
        for current in path:
            current.visits += 1
            current.value += reward

    def _select_action(self, state:BoardStateService) -> Action:
        legal_actions = self._get_legal_actions(state)
        return self.action_selector.select_action(legal_actions, state)


if __name__ == '__main__':
    m = MCTS()
