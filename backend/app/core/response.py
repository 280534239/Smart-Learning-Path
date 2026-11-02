"""统一 API 响应模型。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """所有业务接口使用的统一响应结构。"""

    code: int = Field(default=200, description="200 表示成功，非 200 表示失败")
    message: str = Field(default="success", description="面向调用方的结果说明")
    data: DataT | None = Field(default=None, description="业务数据")
