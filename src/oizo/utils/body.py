from pydantic import BaseModel, ConfigDict


class Body(BaseModel):

    model_config = ConfigDict(extra="forbid")
