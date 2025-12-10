from app.gen.config.base import BaseEnvironmentContext
from app.gen.middleware.AgentBroker import AgentBroker


class BaseMiddlewareEnvironmentContext():

    baseEnvironment = BaseEnvironmentContext()

    def __init__(self):
    {%- for key, agent in cookiecutter.agents.items() %}
        self.{{agent.uid | aiurnvar | capitalize }}AgentBrokerBean()
    {%- endfor %}
    
    {%- for key, agent in cookiecutter.agents.items() %}
    def {{agent.uid | aiurnvar | capitalize }}AgentBrokerBean(self):
        agent = baseEnvironment.{{agent.uid | aiurnvar | capitalize }}AgentBean()
        return AgentBroker(agent)
    {%- endfor %}


