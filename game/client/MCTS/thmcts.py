from ...schema import PlayerState, Action, ActionType
from typing import List, Set, Optional
from ...server.game_logic.game import Game
from ...server.game_logic.action_space_generator import ActionSpaceGenerator
from ...server.game_logic.state_changer import StateChanger
from ...server.game_logic.services.board_state_service import BoardStateService
import random
import math
import logging
import json
from copy import deepcopy
from enum import StrEnum


class NodeType(StrEnum):
    ACTION_TYPE = "action_type"
    ACTION_PARAM = "action_param"


class Node:
    def __init__(
        self,
        parent: Optional['Node'] = None,
        action: Optional[Action] = None,
        who_moved=None,
        node_type: NodeType = NodeType.ACTION_TYPE,
        action_type: Optional[ActionType] = None
    ):
        self.parent = parent
        self.action = action  # Only set for ACTION_PARAM nodes
        self.action_type = action_type  # Only set for ACTION_TYPE nodes (1st level)
        self.node_type = node_type
        self.children: List[Node] = []
        self.visits = 0
        self.value = 0.0
        self.who_moved = who_moved
        
        # Track which action types/actions we've explored
        self.explored_action_types: Set[str] = set()  # For root and ACTION_TYPE nodes
        self.explored_actions: Set[str] = set()  # For ACTION_PARAM nodes
        
        # Track action history for determinization
        if parent is not None and parent.action_history is not None:
            self.action_history = parent.action_history.copy()
        else:
            self.action_history = []
        
        # Only ACTION_PARAM nodes add to action history
        if action is not None and node_type == NodeType.ACTION_PARAM:
            self.action_history.append(action)
    
    def is_fully_expanded(self, legal_actions: List[Action]) -> bool:
        """
        Check if node is fully expanded based on its type.
        """
        if not legal_actions:
            return True
        
        if self.node_type == NodeType.ACTION_TYPE:
            if self.action_type is None:
                # Root node: check if all action types are explored
                legal_action_types = {action.action for action in legal_actions}
                return legal_action_types.issubset(self.explored_action_types)
            else:
                # First-level action type node: check if all parameterized actions are explored
                legal_actions_for_type = [a for a in legal_actions if a.action == self.action_type]
                if not legal_actions_for_type:
                    return True
                legal_action_hashes = {self._hash_action(a) for a in legal_actions_for_type}
                return legal_action_hashes.issubset(self.explored_actions)
        
        # ACTION_PARAM nodes can now have children, so check if all legal actions are explored
        legal_action_types = {action.action for action in legal_actions}
        return legal_action_types.issubset(self.explored_action_types)
    
    @staticmethod
    def _hash_action(action: Action) -> str:
        """Create a hashable string representation of an action."""
        return json.dumps(action.model_dump(), sort_keys=True)


class RandomActionSelector:
    def select_action(self, legal_actions: List[Action], state) -> Optional[Action]:
        try:
            return random.choice(legal_actions)
        except IndexError:
            logging.error(f"COULDN'T FIND AN ACTION IN STATE {state.get_board_state().model_dump()}")
            return None


class HierarchicalMCTS:
    def __init__(self, simulations: int, exploration: float = 2.0, depth: int = 1000):
        self.simulations = simulations
        self.exploration = exploration
        self.max_depth = depth
        self.action_selector = RandomActionSelector()
        self.action_space_generator = ActionSpaceGenerator()
        self.root: Optional[Node] = None

    def search(self, state: PlayerState) -> Optional[Action]:
        """
        Perform hierarchical MCTS search from the given state.
        """
        root_info_set = deepcopy(state)
        
        # Initialize root as ACTION_TYPE selector node
        if self.root is None:
            self.root = Node(
                parent=None,
                action=None,
                who_moved=None,
                node_type=NodeType.ACTION_TYPE,
                action_type=None  # Root doesn't have a specific action type
            )
            determinized_state = self._determinize_state(root_info_set, [])
            self.root.active_player = determinized_state.get_active_player().color

        for sim_idx in range(self.simulations):
            logging.debug(f"Running simulation #{sim_idx}")
            
            # Selection: traverse tree using UCB
            node, path = self._select(self.root, root_info_set)

            # Expansion: add unexplored children
            expanded_nodes = self._expand(node, root_info_set)
            
            # If we expanded, choose one of the new children to simulate from
            if expanded_nodes:
                node = random.choice(expanded_nodes)
                path.append(node)

            # Simulation: rollout from the selected/expanded node
            simulation_result = self._simulate(node, root_info_set)

            # Backpropagation
            self._backpropagate(path, simulation_result, root_info_set.your_color)

        best_action = self._get_best_action(self.root)
        
        # Reset tree after choosing
        self.root = None
        
        return best_action
    
    def _select(self, root: Node, root_info_set: PlayerState) -> tuple[Node, List[Node]]:
        """
        Traverse the tree from root to a leaf using UCB selection.
        """
        node = root
        path = [node]

        while node.children:
            # Check if this node is fully expanded
            determinized_state = self._determinize_state(root_info_set, node.action_history)
            legal_actions = self._get_legal_actions(determinized_state)
            
            if not node.is_fully_expanded(legal_actions):
                # This node has unexplored actions, stop here
                break
            
            # All actions explored, select best child using UCB
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
    
    def _get_best_action(self, root: Node) -> Optional[Action]:
        """
        Return the best action by traversing the tree.
        Root -> best ACTION_TYPE child -> best ACTION_PARAM grandchild
        """
        if not root.children:
            return None
            
        # Find best first-level action type node (most visited)
        best_action_type_node = max(root.children, key=lambda child: child.visits)
        
        # Find best parameterized action under that action type
        if best_action_type_node.children:
            best_action_node = max(
                best_action_type_node.children,
                key=lambda child: child.visits
            )
            return best_action_node.action
            
        return None
    
    def _expand(self, node: Node, root_info_set: PlayerState) -> List[Node]:
        """
        Expand the node by adding ALL unexplored children.
        The type of children depends on the node type.
        """
        determinized_state = self._determinize_state(root_info_set, node.action_history)
        legal_actions = self._get_legal_actions(determinized_state)
        
        if not legal_actions:
            return []
        
        new_children = []
        
        if node.node_type == NodeType.ACTION_TYPE and node.action_type is None:
            # This is the root node or a post-action node: expand by creating ACTION_TYPE children
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
                    
        elif node.node_type == NodeType.ACTION_TYPE and node.action_type is not None:
            # This is a first-level action type node: expand by creating ACTION_PARAM children
            legal_actions_for_type = [a for a in legal_actions if a.action == node.action_type]
            
            for action in legal_actions_for_type:
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
        
        elif node.node_type == NodeType.ACTION_PARAM:
            # ACTION_PARAM nodes can now expand to ACTION_TYPE nodes for the next move
            # Apply the action to get to the next state
            temp_state = self._determinize_state(root_info_set, node.action_history)
            next_legal_actions = self._get_legal_actions(temp_state)
            
            if next_legal_actions:
                legal_action_types = {action.action for action in next_legal_actions}
                
                for action_type in legal_action_types:
                    if action_type not in node.explored_action_types:
                        child_node = Node(
                            parent=node,
                            action=None,
                            who_moved=temp_state.get_active_player().color,
                            node_type=NodeType.ACTION_TYPE,
                            action_type=action_type
                        )
                        node.children.append(child_node)
                        node.explored_action_types.add(action_type)
                        new_children.append(child_node)
        
        return new_children
    
    def _apply_action(self, state: BoardStateService, action: Action):
        """Apply an action to the state."""
        active_player = state.get_active_player()
        state_changer = StateChanger(state)
        state_changer.apply_action(action, state, active_player)
        
    def _get_legal_actions(self, state: BoardStateService) -> List[Action]:
        """Get all legal actions for the active player in the given state."""
        actions_list = self.action_space_generator.get_action_space(
            state,
            state.get_active_player().color
        )
        return actions_list

    def _simulate(self, node: Node, root_info_set: PlayerState) -> dict:
        """
        Perform a random rollout from the given node.
        """
        # Start from the state after applying all actions in the node's history
        determinized_state = self._determinize_state(root_info_set, node.action_history)
        
        # If we're at an ACTION_TYPE node, we need to apply a random action of that type first
        if node.node_type == NodeType.ACTION_TYPE and node.action_type is not None:
            legal_actions = self._get_legal_actions(determinized_state)
            legal_actions_for_type = [a for a in legal_actions if a.action == node.action_type]
            
            if legal_actions_for_type:
                action = self.action_selector.select_action(legal_actions_for_type, determinized_state)
                if action:
                    self._apply_action(determinized_state, action)
        
        # Continue with normal rollout
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

    def _determinize_state(
        self,
        root_info_set: PlayerState,
        action_history: List[Action]
    ) -> BoardStateService:
        """
        Create a determinized version of the game state by sampling hidden information.
        """
        return Game.from_partial_state(root_info_set, history=action_history).state_service
    
    def _evaluate_state(self, state: BoardStateService) -> dict:
        """
        Evaluate the terminal or non-terminal state and return rewards for each player.
        """
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


if __name__ == '__main__':
    m = HierarchicalMCTS(simulations=1000)
