from typing import ClassVar, List
from pydantic import BaseModel, ConfigDict, Field
from uuid import uuid4 as uuid
from app.ext.middleware.Channel import Channel
from enum import Enum, StrEnum 



class Event(BaseModel):
    """Example of a custom agent extension."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    NAME: str = Field(default="Any", description="Name of the abstract event.", frozen=True)
    description: str = Field(..., description="Description of the event")
    source: str = Field("annoymous", description="Source of the event")
    eventid: str = Field(str(uuid()), description="Unique identifier for the event")
    conversationid: str = Field("undisclosed", description="Conversation identifier")
    replychannel: List[Channel] = Field([], description="Channels to reply to")
    payload: dict

    def json(self) -> str:
        """Convinience method to get JSON representation."""
        return self.model_dump_json()

class HeartBeatEvent(Event):
    """HeartBeat Event derived from Event."""
    NAME: str = Field(default="HEARTBEAT", description="Name of the HeartBeat event.", frozen=True)
    description: str = Field(default="Heartbeat event to check system health.", description="Description of the HeartBeat event.")

class QuestionEvent(Event):
    NAME: str = Field(default="QUESTION", description="Name of the Announcement event.", frozen=True)
    description: str = "Question that requires an answer from participating coworkers"
    payload: dict = {
        "question": "",  
    }

 
class AnswerEvent(Event):
    NAME: str = Field(default="ANSWER", description="Name of the Announcement event.", frozen=True)
    description: str = "Answer in reply to a question from participating coworkers"
    payload: dict = {
        "source_question": "",  
        "answer": "",
    }   

class AnnounceEvent(Event):
    
    NAME: str = Field(default="ANNOUNCEMENT", description="Name of the Announcement event.", frozen=True)
    description: str = "Announcement of an agent's capabilities"
    payload: dict = {
        "agent_name": "",
        "capabilities": []  
    }

class EventType(StrEnum):
    ANNOUNCEMENT_EVT = "ANNOUNCEMENT"
    QUESTION_EVT = "QUESTION"
    ANSWER_EVT = "ANSWER"
    HEARTBEAT_EVT = "HEARTBEAT"

    @classmethod
    def to_class(cls, event_type_str: str):
        mapping = {
            cls.ANNOUNCEMENT_EVT: AnnounceEvent,
            cls.QUESTION_EVT: QuestionEvent,
            cls.ANSWER_EVT: AnswerEvent,
            cls.HEARTBEAT_EVT: HeartBeatEvent
        }
        return mapping.get(event_type_str, Event)
