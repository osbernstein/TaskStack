from typing import Optional, List
from pydantic import BaseModel

class StackCreate(BaseModel):
    name: str
    tags: Optional[List[str]] = []

class StackTagAdd(BaseModel):
    tag_name: str

class BatchUpdate(BaseModel):
    task_ids: List[int]
    status: Optional[str] = None
    course: Optional[str] = None

class BatchDelete(BaseModel):
    task_ids: List[int]

class MergeStacksRequest(BaseModel):
    source_stack: str
    target_stack: str
    task_ids: Optional[List[int]] = None

class AssignmentCreate(BaseModel):
    title: str
    course: str
    stack_name: str
    due_date: str
    due_time: Optional[str] = None
    status: Optional[str] = "not_started"
    link: Optional[str] = None

class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    course: Optional[str] = None
    stack_name: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    status: Optional[str] = None
    link: Optional[str] = None

class CanvasInspectRequest(BaseModel):
    feed_url: str
    target_stack: str
    include_past_due: bool = False

class CanvasSyncRequest(BaseModel):
    feed_url: str
    target_stack: str
    allowed_tags: list[str] = []
    include_past_due: bool = False

class BatchTaskItem(BaseModel):
    title: str
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    link: Optional[str] = None

class BatchAssignmentCreate(BaseModel):
    stack_name: str
    course: str
    tasks: List[BatchTaskItem]
