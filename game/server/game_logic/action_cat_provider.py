from typing import Dict, List, get_args
from ...schema import ActionContext, BoardState, CommitAction, BuildAction, DevelopAction, NetworkAction,SellAction,ScoutAction,ShortfallAction, LoanAction, PassAction


class ActionsCatProvider():
    ACTION_CONTEXT_MAP:Dict[ActionContext, tuple] = {
        ActionContext.MAIN: (BuildAction, SellAction, NetworkAction,ScoutAction,DevelopAction,LoanAction, PassAction),
        ActionContext.DEVELOP: (DevelopAction, CommitAction),
        ActionContext.NETWORK: (NetworkAction, CommitAction),
        ActionContext.SELL: (SellAction, CommitAction),
        ActionContext.SHORTFALL: (ShortfallAction,),
        ActionContext.GLOUCESTER_DEVELOP: (DevelopAction,)
    }

    def __init__(self):
        pass

    def get_expected_params(self, state:BoardState) -> Dict[str, List[str]]:
        classes = self.ACTION_CONTEXT_MAP[state.action_context]
        out = {}
        for cls in classes:
            fields = list(cls.model_fields.keys())
            if state.action_context is not ActionContext.MAIN:
                if state.has_subaction() and 'card_id' in fields:
                    fields.remove('card_id')
            out[cls.__name__] = fields
        return out
