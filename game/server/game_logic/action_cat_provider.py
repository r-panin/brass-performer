from typing import Dict, List, get_args
from ...schema import ActionContext, MetaActions, CommitAction, BuildSelection, DevelopSelection, NetworkSelection,ParameterAction,SellSelection,ScoutSelection,EndOfTurnAction,ResolveShortfallAction


class ActionsCatProvider():
    ACTION_CONTEXT_MAP = {
        ActionContext.MAIN: get_args(MetaActions),
        ActionContext.AWAITING_COMMIT: (CommitAction,),
        ActionContext.BUILD: (BuildSelection, CommitAction),
        ActionContext.DEVELOP: (DevelopSelection, CommitAction),
        ActionContext.NETWORK: (NetworkSelection, CommitAction),
        ActionContext.PASS: (ParameterAction, CommitAction),
        ActionContext.SCOUT: (ScoutSelection, CommitAction),
        ActionContext.SELL: (SellSelection, CommitAction),
        ActionContext.LOAN: (ParameterAction, CommitAction),
        ActionContext.END_OF_TURN: (EndOfTurnAction, CommitAction),
        ActionContext.SHORTFALL: (ResolveShortfallAction,),
        ActionContext.GLOUCESTER_DEVELOP: (DevelopSelection, CommitAction)
    }

    def __init__(self):
        pass

    def get_expected_params(self, action_context) -> Dict[str, List[str]]:
        classes = self.ACTION_CONTEXT_MAP[action_context]
        out = {}
        for cls in classes:
            fields = list(cls.model_fields.keys())
            if self.action_context not in (ActionContext.MAIN, ActionContext.AWAITING_COMMIT, ActionContext.END_OF_TURN):
                if self.has_subaction() and 'card_id' in fields:
                    fields.remove('card_id')
            out[cls.__name__] = fields
        return out
