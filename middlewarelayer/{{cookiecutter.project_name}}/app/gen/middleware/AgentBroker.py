import asyncio
import logging
import threading
import uuid
import redis
import logging

from app.gen.domainmodel.middleware.Event import Event, EventType, HeartBeatEvent,AnnounceEvent,AnswerEvent, QuestionEvent
from app.gen.domainmodel.middleware.Channel import Channel, ChannelType, RegistryChannel, HumanChannel, SilconChannel 
from pydantic import BaseModel, ConfigDict
from pydantic_core import from_json
from typing import ClassVar, List
from functools import singledispatchmethod

from app.gen.domainmodel.agent import AbstractAgent
from app.gen.domainmodel.baseentity import BaseInputEntity, BaseOutputEntity
from app.gen.config.settings_middleware import MiddlewareSettings
logger = logging.getLogger(__name__)

class ExceptionBroadcastError(Exception):
    """Custom exception for broadcast errors."""
    pass


class AgentBroker(BaseModel):
    """Example of a custom agent extension."""
    settings:MiddlewareSettings = None
    model_config = ConfigDict(arbitrary_types_allowed=True,)
    r: ClassVar =  None
    retry_config: ClassVar = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    heartbeat_rate: ClassVar = 30
    channels: List[Channel] = []
    listener_registry_thread: threading.Thread = None
    heartbeat_thread: threading.Thread = None
    announce_thread: threading.Thread = None
    agent: AbstractAgent = None
   
 
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis.Redis(host=self.settings.redishost, port=self.settings.redisport, db=0) # Declare r as a ClassVar for class-level usage
        self.listener_registry_thread = threading.Thread(target=self._listen)
        self.heartbeat_thread = threading.Thread(target=self._heartbeat)  
        self.announce_thread = threading.Thread(target=self._announce)
        self.announce_thread.start()

    def _announce(self):
        """Announce Agent to Registry"""
        query = BaseInputEntity(input="Describe your capabilities in short list in lingua franca: English. Use Markdown Format")
        capability_description = asyncio.new_event_loop().run_until_complete(self.agent.ask(query))
        announce_event = AnnounceEvent(payload={"agent_name": self.agent.agentid, "capabilities": capability_description})
        
        for retry in self.retry_config:
            try:
                self._add_channel(SilconChannel())
                self._add_channel(RegistryChannel())
                self.broadcast(RegistryChannel(), announce_event) 
                break # When announce successful, go forward
            except ExceptionBroadcastError as ebe:
                logger.error(f"Broadcast error during announcement: {ebe}")
                logger.warning(f"Preparing Retry in {retry}")
                asyncio.new_event_loop().run_until_complete(asyncio.sleep(retry))

        self.heartbeat_thread.start()
        selftest = QuestionEvent(payload={'question' : 'Erzähl einen witz'})
        self.broadcast(SilconChannel(),selftest)
        self.listener_registry_thread.start()

    def _heartbeat(self):
        """Send heartbeat events to all registered channels."""
        while True:
            try:
                heartbeat_event = HeartBeatEvent(conversationid="0", 
                                            source=self.agent.agentid,
                                            eventid=self._gen_eventid(), # Use generated event ID
                                            payload={})
                self.broadcast(RegistryChannel(), heartbeat_event)
               # asyncio.new_event_loop().run_until_complete(asyncio.sleep(self.heartbeat_rate))

            except ExceptionBroadcastError as ebe:
                logger.error(f"Broadcast error during heartbeat: {ebe}")
            finally:
                asyncio.new_event_loop().run_until_complete(asyncio.sleep(self.heartbeat_rate))

    def _gen_eventid(self) -> str:
        """Generate event ID with source suffix."""
        return f"{str(uuid.uuid4())}:{self.agent.namespace}"
       
    def _add_channel(self, channel: Channel) -> Channel:
        """Add a new channel to the broadcaster."""
        try:
            self.channels.append(channel)
            self.r.xgroup_create(channel.fqname(), self.agent.namespace, id='0', mkstream=True)
        except redis.exceptions.ResponseError as e:
            logger.warning(f"Group already exists for channel {channel.fqname()}: {e}")
        except redis.exceptions.ConnectionError as ce:
            logger.error(f"Redis connection error while adding channel {channel.fqname()}: {ce}")
            raise ExceptionBroadcastError(f"Broadcast failed: {ce}") 
    
    def broadcast(self, channel: Channel, event: Event):
        """Broadcast Event"""
        try:
            event.source = self._get_source()
            event.eventid = self._gen_eventid()
            logger.info(f"Broadcasting Event: {event.json()} to channel: {channel.fqname()} ")
            if channel not in self.channels:
                self._add_channel(channel)

            self.r.xadd(channel.fqname(), { 'event': f'{event.model_dump_json()}'}) 

        except redis.exceptions.ConnectionError as ce:
            logger.error(f"Redis connection error while adding channel {channel.fqname()}: {ce}")
            raise ExceptionBroadcastError(f"Broadcast failed: {ce}") 
        
    def reply(self, prev_event:Event, send_event:Event, channel:Channel):
        send_event.conversationid=prev_event.conversationid
        channels = [channel]
        for channel in channels:
            self.broadcast(channel, send_event)

    def _listen(self):
        """Listen to Streams"""
        while True:
            try:
                stream = self.r.xreadgroup(streams={
                                                        RegistryChannel().fqname(): '>',
                                                        SilconChannel().fqname(): '>'
                                                    },
                                            consumername=self.agent.agentid,
                                            groupname=self.agent.namespace, 
                                            block=0)
                logger.info(f"AgentBroker received new stream: {stream}")
                self._process_stream(stream)
            except redis.exceptions.ConnectionError as ce:
                logger.error(f"Redis connection error while reading from channel {RegistryChannel().fqname()}: {ce}")
                asyncio.new_event_loop().run_until_complete(asyncio.sleep(1))
    
    def _process_stream(self, stream):
        """Process the stream"""
        for message in stream:
            try:
                channel_name = message[0].decode('utf-8')
                channel = ChannelType(channel_name).to_class()
            except ValueError as ve:
                logger.error(f"Unknown channel type received: {channel_name}. Error: {ve}")
                channel = Channel(channelname="undislosed")
            
            for record in message[1]:
                
                evtraw = from_json(record[1][b'event'].decode('utf-8'))
                try:
                    eventclass = EventType.to_class(evtraw.get("NAME","Any"))
                    evt = eventclass.model_validate(from_json(record[1][b'event'].decode('utf-8')))

                    logger.info(f"AgentBroker processing event: {evtraw} from channel: {channel.fqname()}")
                    if not self._is_circuit(evt):
                        self._handle_event(evt, channel)
                    self.r.xack(channel.fqname(),self.agent.namespace, record[0])

                except ValueError as ve:
                    logger.error(f"Unknown event type received: {evtraw.get('NAME','Unknown')}. Error: {ve}")
             
    def _gen_eventid(self) -> str:
        """Generate event ID with source suffix."""
        return f"{str(uuid.uuid4())}:{self.agent.agentid}"
    def _get_source(self) -> str:
        """Generate Event Source"""
        return f"{self.agent.namespace}:{self.agent.agentid}"
    
    def _is_circuit(self, event:Event) -> bool:
        """Check if event sent in circuit"""
        return event.source == self.agent.agentid

    @singledispatchmethod
    def _handle_event(self, event:Event, in_channel:Channel=None):
        logger.info(f"Handling generict event: {event.NAME}")

    @_handle_event.register
    def _(self, event:AnnounceEvent, in_channel:Channel=None):
        """Handle Announce Event"""
        logger.info(f"Handling Announce: {event.NAME}")

    @_handle_event.register
    def _(self, event:QuestionEvent, in_channel:Channel=None):
        """Handle QuestionEvent Event"""
        logger.info(f"Handling Question: {event.NAME}")
        input = BaseInputEntity(input=event.payload.get("question","NOOP"))
        result:BaseOutputEntity = asyncio.new_event_loop().run_until_complete(self.agent.ask(input=input))
        answer = AnswerEvent(payload={"answer" : result.output})
        self.reply(event,answer,HumanChannel())


       
