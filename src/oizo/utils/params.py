from pydantic import BaseModel, ConfigDict


class Params(BaseModel):

    model_config = ConfigDict(extra="forbid")
