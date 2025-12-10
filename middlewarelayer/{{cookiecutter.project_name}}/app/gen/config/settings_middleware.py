from pydantic import Field
from pydantic_settings import BaseSettings

class MiddlewareSettings(BaseSettings):
    redishost:str = Field("localhost", description="Host Redis is running on")
    redisport:int = Field(6379, description="Host Redis is running on")
