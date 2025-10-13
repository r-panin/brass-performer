import math
from typing import Dict, Optional, List, Set
from enum import StrEnum
from ...schema import Action, PlayerState, ActionType, PlayerColor
from ...server.game_logic.services.board_state_service import BoardStateService
from ...server.game_logic.action_space_generator import ActionSpaceGenerator
from ...server.game_logic.state_changer import StateChanger
from ...server.game_logic.game import Game
from copy import deepcopy
import json
import random
import logging


class NodeType(StrEnum):
    ACTION_TYPE = "action_type"
    ACTION_PARAM = "action_param"

class Node:
    def __init__(
            self,
            parent: Optional['Node'],
            action: Optional[Action],
            who_moved: PlayerColor,
            node_type: NodeType,
            action_type: Optional[ActionType] = None
    ):
        self.parent = parent
        self.action = action
        self.action_type = action_type
        self.node_type = node_type
        self.children: List[Node] = []
        self.visits = 0
        self.value = 0.0
        self.who_moved = who_moved

        self.explored_action_types: Set[str] = set()
        self.explored_actions: Set[str] = set()

        if parent is not None and parent.action_history is not None:
            self.action_history = parent.action_history.copy()
        else:
            self.action_history = []

        if action is not None and node_type == NodeType.ACTION_PARAM:
            self.action_history.append(action)

    def is_fully_expanded(self, legal_actions: List[Action]) -> bool:
        if not legal_actions:
            return True
        
        if self.node_type == NodeType.ACTION_TYPE:
            legal_action_types = {action.action for action in legal_actions}
            return legal_action_types.issubset(self.explored_action_types)
        else:
            legal_atomic_actions = [a for a in legal_actions if a.action == self.action_type]
            if not legal_atomic_actions:
                return True
            legal_action_hashes = {self._hash_action(a) for a in legal_atomic_actions}
            return legal_action_hashes.issubset(self.explored_actions)
        
    @staticmethod
    def _hash_action(action: Action) -> str:
        return json.dumps(action.model_dump(), sort_keys=True)
    

class RandomActionSelector:
    def select_action(self, legal_actions: List[Action], state) -> Optional[Action]:
        try:
            return random.choice(legal_actions)
        except IndexError:
            logging.error(f"COULDN'T FIND AN ACTION IN STATE {state.get_board_state().model_dump()}")
            return None

class HierarchicalMCTS:
    def __init__(self, simulations:int, exploration:float = 2.0, depth:int = 1000):
        self.simulations = simulations
        self.exploration = exploration
        self.max_depth = depth
        self.action_selector = RandomActionSelector()
        self.action_space_generator = ActionSpaceGenerator()
        self.root: Optional[Node] = None

    def _determinize_state(self, state:PlayerState, history:List[Action]=[]) -> BoardStateService:
        return Game.from_partial_state(state, history).state_service

    def _get_legal_actions(self, state:BoardStateService) -> List[Action]:
        return self.action_space_generator.get_action_space(state, state.get_active_player().color)

    def _apply_action(self, state: BoardStateService, action: Action):
        active_player = state.get_active_player()
        state_changer = StateChanger(state)
        state_changer.apply_action(action, state, active_player)

    def search(self, state: PlayerState) -> Optional[Action]:
        root_info_set = deepcopy(state)

        if self.root is None:
            self.root = Node(
                parent=None,
                action=None,
                who_moved=None,
                node_type=NodeType.ACTION_PARAM,
                action_type=None
            )
            determinized_state = self._determinize_state(root_info_set, [])
            self.root.active_player = determinized_state.get_active_player().color

        for sim_idx in range(self.simulations):
            logging.debug(f"Running simulation #{sim_idx}")

            node, path = self._select(self.root, root_info_set)

            expanded_nodes = self._expand(node, root_info_set)

            if expanded_nodes:
                node = random.choice(expanded_nodes)
                path.append(node)

            simulation_result = self._simulate(node, root_info_set)

            self._backpropagate(path, simulation_result, root_info_set.your_color)
        
        best_action = self._get_best_action(self.root)

        self.root = None

        return best_action
    
    def _select(self, root:Node, root_info_set: PlayerState) -> tuple[Node, List[Node]]:
        node = root
        path = [node]
        while node.children:
            determinized_state = self._determinize_state(root_info_set, node.action_history)
            legal_actions = self._get_legal_actions(determinized_state)

            if not node.is_fully_expanded(legal_actions):
                break

            best_child = self._best_child(node)
            path.append(best_child)
            node = best_child

        return node, path
    
    def _best_child(self, node: Node) -> Node:
        """
        Select the best child using UCB1 formula.
        """
        best_score = -float('inf')
        best_child = None

        for child in node.children:
            if child.visits == 0:
                ucb_score = float('inf')
            else:
                exploitation = child.value / child.visits
                exploration = self.exploration * math.sqrt(
                    max(0.0, math.log(max(1, node.visits))) / child.visits
                )
                ucb_score = exploitation + exploration
                
            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child
        
        return best_child
    
    def _get_best_action(self, root:Node) -> Optional[Action]:
        if not root.children:
            return None
        
        best_action_type_node = max(root.children, key=lambda child: child.visits)

        if best_action_type_node.children:
            best_atomic_action_node = max(best_action_type_node.children, key=lambda child: child.visits)

            return best_atomic_action_node.action
        
        return None

    def _expand(self, node: Node, root_info_set: PlayerState) -> List[Node]:
        determinized_state = self._determinize_state(root_info_set, node.action_history)
        legal_actions = self._get_legal_actions(determinized_state)

        if not legal_actions:
            return []
        
        new_children = []
        if node.node_type == NodeType.ACTION_PARAM:
            legal_action_types = {action.action for action in legal_actions}

            for action_type in legal_action_types:
                if action_type not in node.explored_action_types:
                    child_node = Node(
                        parent=node,
                        action=None,
                        who_moved=determinized_state.get_active_player().color,
                        node_type=NodeType.ACTION_TYPE,
                        action_type=action_type
                    )
                    node.children.append(child_node)
                    node.explored_action_types.add(action_type)
                    new_children.append(child_node)
        
        elif node.node_type == NodeType.ACTION_TYPE:
            legal_atomic_actions = [a for a in legal_actions if a.action == node.action_type]

            for action in legal_atomic_actions:
                action_hash = Node._hash_action(action)
                if action_hash not in node.explored_actions:
                    child_node = Node(
                        parent=node,
                        action=action,
                        who_moved=determinized_state.get_active_player().color,
                        node_type=NodeType.ACTION_PARAM,
                        action_type=None
                    )
                    node.children.append(child_node)
                    node.explored_actions.add(action_hash)
                    new_children.append(child_node)

    def _simulate(self, node: Node, root_info_set: PlayerState) -> Dict[PlayerColor, float]:
        determinized_state = self._determinize_state(root_info_set, node.action_history)

        if node.node_type == NodeType.ACTION_TYPE:
            legal_actions = self._get_legal_actions(determinized_state)
            legal_atomic_actions = [a for a in legal_actions if a.action == node.action_type]

            if legal_atomic_actions:
                action = self.action_selector.select_action(legal_atomic_actions, determinized_state)
                if action:
                    self._apply_action(determinized_state, action)

            depth = 0
            while depth < self.max_depth and not determinized_state.is_terminal():
                legal_actions = self._get_legal_actions(determinized_state)
                if not legal_actions:
                    break

                action = self.action_selector.select_action(legal_actions, determinized_state)
                if action is None:
                    break

                self._apply_action(determinized_state, action)
                depth += 1

        return self._evaluate_state(determinized_state)
        
    def _evaluate_state(self, state:BoardStateService) -> dict:
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
            # Non-terminal evaluation: use random values or heuristic
            return {p.color: random.random() for p in state.get_players().values()}
    
    def _backpropagate(self, path: List[Node], results: dict, root_player) -> None:
        """
        Backpropagate the simulation result up the tree.
        """
        for current in path:
            current.visits += 1
            # Add reward from the perspective of the player who acted at this node
            # For the root node (no action yet), use the root player
            acting_player = current.who_moved if current.who_moved is not None else root_player
            reward = results.get(acting_player, 0.0)
            if acting_player == root_player:
                current.value += reward
