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
        self.untried_actions: List[Action] = []
        self.action_history: tuple[Action] = ()
        if parent is not None and parent.action_history is not None and action is not None:
            self.action_history = (*parent.action_history, action)
    
    def is_fully_expanded(self, legal_actions = List[Action]) -> bool:
        expanded_actions = {child.action for child in self.children}
        return all(action in expanded_actions for action in legal_actions)

class RandomActionSelector:
    def select_action(self, legal_actions:List[Action], state) -> Action:
        try:
            return random.choice(legal_actions)
        except IndexError:
            print(f"COULDN'T FIND AN ACTION IN STATE {state.get_board_state().model_dump()}")

class MCTS:
    def __init__(self, simulations:int, exploration:float=1.41, depth:int=1000):
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

        for sim_idx in range(self.simulations):
            initial_state = deepcopy(state)
            logging.debug(f"Running simulation #{sim_idx}")
            # Determinize hidden information per simulation
            determined_state: BoardStateService = Game.from_partial_state(initial_state).state_service
            logging.debug(f"Determined state: {determined_state.get_board_state().model_dump()}")
            self.state_changer = StateChanger(determined_state, event_bus=None)

            # Track root player's perspective for reward
            root_player = determined_state.get_active_player().color

            # Selection: traverse the persistent tree while applying chosen actions to a local rollout state
            node = self.root
            rollout_state = determined_state
            # Descend as long as node is fully expanded and game not over
            while node.is_fully_expanded() and not rollout_state.is_terminal():
                node = self._best_child(node)
                # Apply the chosen child's action to the local state only
                if node.action is not None:
                    self._apply_action(rollout_state, node.action)

            # Expansion: if not terminal, expand one untried action
            if not rollout_state.is_terminal():
                node = self._expand(node, rollout_state)

            # Simulation: from the new state, rollout randomly to terminal
            simulation_result = self._simulate(rollout_state)

            # Backpropagate from root player's perspective
            self._backpropagate(node, simulation_result, root_player)

        best_action = self._get_best_action(self.root)
        # Reset tree after choosing to avoid mixing across turns
        self.root = None
        return best_action
    
    def _select(self, node:Node) -> Node:
        while node.is_fully_expanded() and not node.is_terminal():
            node = self._best_child(node)
        return node
    
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
    
    def _expand(self, node: Node, rollout_state: BoardStateService) -> Node:
        if not node.untried_actions:
            legal_actions = self._get_legal_actions(rollout_state)
            node.untried_actions = list(legal_actions)
        
        if node.untried_actions:
            action = random.choice(node.untried_actions)
            node.untried_actions.remove(action)
            who_moved = rollout_state.get_active_player().color
            # Apply chosen action to the local rollout state only
            self._apply_action(rollout_state, action)
            child_node = Node(parent=node, action=action, who_moved=who_moved)
            node.children.append(child_node)
            return child_node
        
        return node
    
    def _apply_action(self, state:BoardStateService, action:Action):
        active_player = state.get_active_player()
        self.state_changer.apply_action(action, state, active_player)
        return state
        
    def _get_legal_actions(self, state: BoardStateService):
        actions_list = self.action_space_generator.get_action_space(state, state.get_active_player().color)
        return actions_list

    def _simulate(self, rollout_state:BoardStateService) -> dict:
        depth = 0
        while depth < self.max_depth and not self._is_terminal_state(rollout_state):
            action = self._select_action(rollout_state)
            self._apply_action(rollout_state, action)
            depth += 1
        return self._evaluate_state(rollout_state)
    
    def _is_terminal_state(self, state:BoardStateService):
        return state.is_terminal()

    def _evaluate_state(self, state: BoardStateService) -> dict:
        if self._is_terminal_state(state):
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

    def _backpropagate(self, node:Node, results:dict, root_player) -> None:
        current = node
        while current is not None:
            current.visits += 1
            reward = results.get(root_player, 0.0)
            current.value += reward
            current = current.parent
    
    def _select_action(self, state:BoardStateService) -> Action:
        legal_actions = self._get_legal_actions(state)
        return self.action_selector.select_action(legal_actions, state)


if __name__ == '__main__':
    m = MCTS()
