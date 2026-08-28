from pydantic import BaseModel, ConfigDict


class QS(BaseModel):

    model_config = ConfigDict(extra="forbid")
