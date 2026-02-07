from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    id: str
    name: str
    createdAt: int

    model_config = ConfigDict(extra="ignore")


class Source(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    text: Optional[str] = None
    addedAt: int
    status: Literal["idle", "loading", "success", "error"]
    error: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

    model_config = ConfigDict(extra="ignore")


class LLMOptions(BaseModel):
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class ScrapeRequest(BaseModel):
    url: str
    notebookId: Optional[str] = None


class SummaryRequest(LLMOptions):
    context: Optional[str] = None


class ChatRequest(LLMOptions):
    messages: List[Message] = Field(default_factory=list)
    context: Optional[str] = None
    notebookId: Optional[str] = None
    useSources: Optional[bool] = True
    topK: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class NotebookRequest(BaseModel):
    notebookId: str
    sources: List[Source] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class LLMNotebookRequest(NotebookRequest, LLMOptions):
    model_config = ConfigDict(extra="ignore")


class SearchRequest(BaseModel):
    notebookId: str
    query: str
    topK: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class SourceListRequest(BaseModel):
    notebookId: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class CreateProjectRequest(BaseModel):
    name: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class DeleteProjectRequest(BaseModel):
    projectId: str

    model_config = ConfigDict(extra="ignore")


class ExportProjectRequest(BaseModel):
    projectId: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class RemoveSourceRequest(BaseModel):
    notebookId: Optional[str] = None
    sourceId: str

    model_config = ConfigDict(extra="ignore")

class VeoStartRequest(BaseModel):
    prompt: str


class VeoPollRequest(BaseModel):
    operationName: str
