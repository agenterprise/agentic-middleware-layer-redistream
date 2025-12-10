from app.gen.config.base import BaseEnvironmentContext
from app.gen.middleware.AgentBroker import AgentBroker
from app.gen.config.settings_middleware import MiddlewareSettings


class BaseMiddlewareEnvironmentContext():

    baseEnvironment = BaseEnvironmentContext()

    def MiddlewareSettingsBean():
        return MiddlewareSettings()
    
    def __init__(self):
    {%- for key, agent in cookiecutter.agents.items() %}
        self.{{agent.uid | aiurnvar | capitalize }}AgentBrokerBean()
    {%- endfor %}

    {%- for key, agent in cookiecutter.agents.items() %}
    def {{agent.uid | aiurnvar | capitalize }}AgentBrokerBean(self):
        agent = self.baseEnvironment.{{agent.uid | aiurnvar | capitalize }}AgentBean()
        return AgentBroker(agent=agent, settings=self.MiddlewareSettingsBean())
    {%- endfor %}


