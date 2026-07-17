from investment.agents.state import InvestmentState


def create_investment_graph(*args, **kwargs):
    from investment.agents.graph import create_investment_graph as build_graph

    return build_graph(*args, **kwargs)

__all__ = ["InvestmentState", "create_investment_graph"]
