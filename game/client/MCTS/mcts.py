from ...schema import PlayerState, Action, Request, RequestType 
from typing import List
from ...server.game_logic.game import Game
import random
import math
import logging


class Node:
    def __init__(self, state:PlayerState, parent=None, action:Action=None, who_moved=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children: List[Node] = []
        self.visits = 0
        self.value = float()
        self.who_moved = who_moved
        self.untried_actions = []
    
    def is_fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0 and len(self.children) > 0
    
    def is_terminal(self):
        return self.state.state.deck_size == 0 and not any(player.hand for player in self.state.players.values())

class RandomActionSelector:
    def select_action(self, legal_actions:List[Action]) -> Action:
        return random.choice(legal_actions)

class MCTS:
    def __init__(self, simulations:int=100, exploration:float=1.41, depth:int=1000):
        self.simulations = simulations
        self.exploration = exploration
        self.max_depth = depth
        self.action_selector = RandomActionSelector()

    def search(self, initial_state:PlayerState):
        root = Node(initial_state)

        for _ in range(self.simulations):
            node = self._select(root)

            if not node.is_terminal():
                node = self._expand(node)

            simulation_result = self._simulate(node)

            self._backpropagate(node, simulation_result)

        return self._get_best_action(root)
    
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
                exploration = self.exploration * (math.log(node.visits) / child.visits)
                ucb_score = exploitation + exploration
            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child
        
        return best_child
    
    def _get_best_action(self, root:Node):
        return max(root.children, key=lambda child: child.visits).action
    
    def _expand(self, node: Node) -> Node:
        if not node.untried_actions:
            legal_actions = self._get_legal_actions(node.state)
            node.untried_actions = legal_actions
        
        if node.untried_actions:
            action = random.choice(node.untried_actions)
            node.untried_actions.remove(action)
            who_moved = node.state.state.turn_order[0]
            new_state = self._apply_action(node.state, action)
            child_node = Node(new_state, parent=node, action=action, who_moved=who_moved)
            node.children.append(child_node)
            return child_node
        
        return node
    
    def _apply_action(self, state:PlayerState, action:Action):
        game = Game.from_partial_state(state)
        logging.debug(f'Applying action {action}')
        game.process_action(action, state.state.turn_order[0])
        return game.process_action(Request(request=RequestType.REQUEST_STATE), state.state.turn_order[0])
        
    def _get_legal_actions(self, state: PlayerState):
        game = Game.from_partial_state(state)
        for player in game.state.players:
            if game.state_manager.is_player_to_move(player):
                active_player = game.state.turn_order[0]
                break
        request_result = game.process_action(Request(request=RequestType.REQUEST_ACTIONS), active_player).result
        logging.debug(request_result)
        out = []
        for cat, actions in request_result.items():
            out.extend(actions)
        logging.debug(f'Legal actions: {out}')
        return out 

    def _simulate(self, node:Node) -> float:
        current_state = node.state.model_copy()
        depth = 0
        #while depth < self.max_depth:
        while not self._is_terminal_state(current_state):
            action = self._select_action(current_state)
            current_state = self._apply_action(current_state, action)
            depth += 1

        return self._evaluate_state(current_state)
    
    def _is_terminal_state(self, state:PlayerState):
        game = Game.from_partial_state(state)
        return not game.state.deck and not any(player.hand for player in game.state.players.values())

    def _evaluate_state(self, state: PlayerState) -> dict:
        players = sorted(
            state.state.players.values(), 
            key=lambda p: p.victory_points, 
            reverse=True
        )
        
        results = {}
        for idx, player in enumerate(players):
            # Нормализованная оценка: 1.0 за первое место, 0.0 за последнее
            normalized_score = 1.0 - (idx / (len(players) - 1)) if len(players) > 1 else 1.0
            results[player.color] = normalized_score
        
        return results

    def _backpropagate(self, node:Node, results:dict):
        while node is not None:
            who_moved = node.who_moved
            node.visits +=1
            if who_moved in results:
                node.value += results[who_moved]
            node = node.parent
    
    def _select_action(self, state:PlayerState) -> Action:
        legal_actions = self._get_legal_actions(state)
        return self.action_selector.select_action(legal_actions)


if __name__ == '__main__':
    m = MCTS()
