import logging
from pydantic import BaseModel, ConfigDict
from enum import Enum, StrEnum 
logger = logging.getLogger(__name__)


class Channel(BaseModel):
    """Example of a custom agent extension."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    channelname: str
    prefix: str = "ff:dd:ww"

    def fqname(self) -> str:
        return f"{self.prefix}:{self.channelname}"
    
class HumanChannel(Channel):
    channelname: str = "human" 


class RegistryChannel(Channel):
    channelname: str = "registry" 


class SilconChannel(Channel):
    channelname: str = "insilicon" 


class ChannelType(StrEnum):
    HUMAN = HumanChannel().fqname()
    REGISTRY = RegistryChannel().fqname()
    SILICON = SilconChannel().fqname()  

    def to_class(self) -> Channel:
        if self.name == ChannelType.HUMAN.name:
            return HumanChannel()
        elif self.name == ChannelType.REGISTRY.name:
            return RegistryChannel()
        elif self.name == ChannelType.SILICON.name:
            return SilconChannel()