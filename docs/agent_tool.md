# Agent Tools

本文档详细说明 OmniEmployee 内置的基础工具（Tools）及其功能。

## 概述

Tools 是 Agent 执行具体操作的接口。每个 Tool 都遵循统一的接口规范，可以被 Agent 动态调用。Tools 通过 `ToolRegistry` 统一管理，并在每次 LLM 调用时作为 function calling 的工具定义传递给模型。

## Tool 架构

### BaseTool 接口

所有 Tool 都继承自 `BaseTool` 抽象基类：

```python
class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool 名称"""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool 描述（用于 LLM 理解何时使用）"""
    
    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema 定义（用于 LLM 生成参数）"""
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具并返回结果"""
```

### ToolResult

每个 Tool 执行后返回 `ToolResult`:

```python
@dataclass
class ToolResult:
    status: ToolResultStatus  # SUCCESS, ERROR, TIMEOUT
    output: Any = None         # 成功时的输出
    error: str | None = None   # 错误时的错误信息
    metadata: dict = {}        # 额外的元数据
```

## 内置工具详解

### 1. grep - 代码搜索

**用途**: 使用 ripgrep 进行快速代码搜索

**功能特性**:
- 支持正则表达式模式
- 文件类型过滤（如 `py`, `ts`, `js`）
- 上下文行数（显示匹配行前后的内容）
- 大小写敏感/智能匹配
- 整词匹配
- 结果数量限制

**参数**:
```python
grep(
    pattern: str,              # 搜索模式（正则表达式）
    path: str | None = None,   # 搜索路径（默认：workspace root）
    file_type: str | None = None,  # 文件类型过滤（如 "py"）
    context_lines: int = 0,    # 上下文行数
    max_results: int = 50,     # 最大结果数
    case_sensitive: bool = False,  # 大小写敏感
    whole_word: bool = False   # 整词匹配
)
```

**使用示例**:
```python
# 搜索所有 __init__ 方法定义
grep(pattern="def __init__", file_type="py", context_lines=2)

# 搜索特定类名
grep(pattern="class.*Agent", path="src/omniemployee/core")

# 搜索错误处理代码
grep(pattern="except|raise|Error", file_type="py", max_results=20)
```

**输出格式**:
```
file_path:line_number: matching_line_content
file_path:line_number: matching_line_content
...
```

### 2. list_dir - 目录列表

**用途**: 列出目录内容，支持树形结构和过滤

**功能特性**:
- 递归深度控制
- 隐藏文件过滤
- Glob 模式过滤（如 `*.py`）
- 仅显示目录选项
- 使用 `fd` 命令加速（如果可用）

**参数**:
```python
list_dir(
    path: str | None = None,   # 目录路径（默认：workspace root）
    depth: int = 1,             # 递归深度（默认：1，仅当前目录）
    show_hidden: bool = False,  # 显示隐藏文件
    pattern: str | None = None, # Glob 模式（如 "*.py"）
    dirs_only: bool = False    # 仅显示目录
)
```

**使用示例**:
```python
# 列出当前目录
list_dir()

# 列出 src 目录，深度为 2
list_dir(path="src/", depth=2)

# 查找所有 Python 文件
list_dir(pattern="*.py", depth=3)

# 列出所有目录
list_dir(dirs_only=True)
```

**输出格式**:
```
📁 directory_name/
├── 📁 subdirectory/
├── file.py
└── README.md
```

### 3. read_file - 文件读取

**用途**: 读取文件内容，支持行范围读取

**功能特性**:
- 支持指定行范围（start_line, end_line）
- 自动行号显示
- 大文件截断保护（max_lines）
- 文件大小检查
- 相对路径和绝对路径支持

**参数**:
```python
read_file(
    path: str,                 # 文件路径（必需）
    start_line: int | None = None,  # 起始行号（1-based）
    end_line: int | None = None,    # 结束行号（包含）
    max_lines: int = 500       # 最大返回行数
)
```

**使用示例**:
```python
# 读取整个文件
read_file(path="main.py")

# 读取特定行范围
read_file(path="src/agent.py", start_line=10, end_line=50)

# 读取文件开头
read_file(path="README.md", start_line=1, end_line=100)
```

**输出格式**:
```
File: path/to/file.py (lines 10-50 of 200)
────────────────────────────────────────────────────────────
    10| def function_name():
    11|     """Function docstring."""
    12|     ...
```

### 4. write_file - 文件写入

**用途**: 写入或编辑文件内容

**功能特性**:
- 多种写入模式：overwrite, append, insert, replace_lines
- 自动创建父目录
- 原子写入（临时文件 + 重命名）
- 备份支持（可选）
- 行号范围替换

**参数**:
```python
write_file(
    path: str,                 # 文件路径（必需）
    content: str,              # 写入内容（必需）
    mode: str = "overwrite",   # 模式：overwrite/append/insert/replace_lines
    start_line: int | None = None,  # 插入/替换起始行号
    end_line: int | None = None,    # 替换结束行号
    create_dirs: bool = True   # 自动创建目录
)
```

**写入模式**:

| 模式 | 说明 | 示例 |
|------|------|------|
| `overwrite` | 覆盖整个文件 | 创建新文件或完全替换 |
| `append` | 追加到文件末尾 | 在现有内容后添加 |
| `insert` | 在指定行插入 | 在第 10 行插入新内容 |
| `replace_lines` | 替换指定行范围 | 替换第 10-20 行 |

**使用示例**:
```python
# 创建新文件
write_file(path="new_file.py", content="print('Hello')")

# 追加内容
write_file(path="log.txt", content="New log entry", mode="append")

# 在指定行插入
write_file(path="script.py", content="new_code()", mode="insert", start_line=10)

# 替换指定行
write_file(path="config.py", content="new_config", mode="replace_lines", start_line=5, end_line=10)
```

### 5. run_command - 命令执行

**用途**: 执行 shell 命令或 Python 脚本

**功能特性**:
- 支持任意 shell 命令
- Python 脚本执行（通过 `uv run`）
- 工作目录设置
- 超时控制
- 环境变量设置
- 标准输出和错误输出捕获

**参数**:
```python
run_command(
    command: str,              # 要执行的命令（必需）
    working_dir: str | None = None,  # 工作目录
    timeout: int | None = None,      # 超时时间（秒，默认：120）
    env: dict[str, str] | None = None  # 额外环境变量
)
```

**使用示例**:
```python
# 执行 Python 脚本
run_command(command="uv run scripts/get_current_time.py")

# 执行带参数的脚本
run_command(command="uv run scripts/search_flights.py --from Beijing --to Tokyo --date 2025-01-15")

# 执行系统命令
run_command(command="ls -la")

# 在指定目录执行
run_command(command="python script.py", working_dir="src/skills/book-flight")

# 设置环境变量
run_command(command="python script.py", env={"DEBUG": "1"})
```

**输出格式**:
```
Command output here...
[stderr]
Error messages if any...
```

## Tool 注册和管理

### ToolRegistry

所有 Tool 通过 `ToolRegistry` 统一管理：

```python
class ToolRegistry:
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
    
    def get(self, name: str) -> BaseTool | None:
        """获取工具"""
    
    def execute(self, name: str, **kwargs) -> ToolResult:
        """执行工具"""
    
    def get_definitions(self) -> list[dict]:
        """获取所有工具定义（OpenAI 格式）"""
```

### Tool 定义格式

每个 Tool 都会被转换为 OpenAI function calling 格式：

```json
{
  "type": "function",
  "function": {
    "name": "grep",
    "description": "Search file contents using ripgrep...",
    "parameters": {
      "type": "object",
      "properties": {
        "pattern": {
          "type": "string",
          "description": "Search pattern (regex supported)"
        },
        "path": {
          "type": "string",
          "description": "Directory or file to search in"
        }
      },
      "required": ["pattern"],
      "additionalProperties": false
    }
  }
}
```

## Tool 执行流程

### 1. Agent 调用 LLM

```
Agent Loop
    ↓
构建消息列表（包含工具定义）
    ↓
调用 LLM（通过 LiteLLM）
    ↓
LLM 返回工具调用请求
```

### 2. 工具调用解析

```python
# LLM 返回格式
{
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "grep",
        "arguments": '{"pattern": "def __init__", "file_type": "py"}'
      }
    }
  ]
}
```

### 3. 工具执行

```python
# AgentLoop._execute_single_tool()
1. 解析工具名称和参数
2. 从 ToolRegistry 获取工具实例
3. 调用 tool.execute(**arguments)
4. 捕获异常并返回 ToolResult
5. 将结果添加到 Context
```

### 4. 结果处理

```python
# ToolResult 转换为消息
tool_result = ToolResult(
    status=ToolResultStatus.SUCCESS,
    output="file1.py:10: def __init__(self):\nfile2.py:25: def __init__(self):"
)

# 添加到 Context
context.add_tool_result(
    tool_call_id="call_abc123",
    content=tool_result.to_message(),  # 转换为字符串
    is_error=False
)
```

## Tool 错误处理

### 错误类型

| 错误类型 | 说明 | 示例 |
|---------|------|------|
| `ERROR` | 工具执行失败 | 文件不存在、命令执行失败 |
| `TIMEOUT` | 执行超时 | 命令执行超过 timeout 时间 |
| `SUCCESS` | 执行成功 | 正常返回结果 |

### 错误处理流程

```python
try:
    result = await tool.execute(**kwargs)
except asyncio.TimeoutError:
    return ToolResult(
        status=ToolResultStatus.TIMEOUT,
        error=f"Command timed out after {timeout} seconds"
    )
except Exception as e:
    return ToolResult(
        status=ToolResultStatus.ERROR,
        error=str(e)
    )
```

## Tool 结果优化

### 结果截断

对于过长的工具输出，系统会自动截断：

```python
# 如果工具结果超过 2000 字符
if len(content) > 2000:
    content = summarize_tool_result(content, max_length=500)
    # 保留开头和结尾，中间用 ... 省略
```

### 结果压缩

在上下文接近上限时，旧的工具结果会被压缩：

```python
# 压缩旧工具结果（保留最近 N 轮）
if len(content) > 500:
    content = summarize_tool_result(content, max_length=200)
```

## 工具使用最佳实践

### 1. 选择合适的工具

- **搜索代码**: 使用 `grep`（支持正则，快速）
- **浏览目录**: 使用 `list_dir`（树形结构，清晰）
- **读取文件**: 使用 `read_file`（支持行范围，高效）
- **修改文件**: 使用 `write_file`（多种模式，安全）
- **执行脚本**: 使用 `run_command`（灵活，支持任意命令）

### 2. 参数优化

- **grep**: 使用 `file_type` 过滤减少结果
- **read_file**: 使用 `start_line`/`end_line` 只读取需要的部分
- **run_command**: 设置合理的 `timeout` 避免长时间等待

### 3. 错误处理

- 检查工具返回的 `status`
- 对于 `ERROR` 状态，查看 `error` 字段
- 对于 `TIMEOUT`，考虑增加 timeout 或优化命令

## 总结

OmniEmployee 的工具系统提供了：

1. **统一的接口**: 所有工具遵循相同的 `BaseTool` 接口
2. **类型安全**: 使用 JSON Schema 定义参数类型
3. **错误处理**: 统一的错误处理和结果格式
4. **性能优化**: 结果截断和压缩机制
5. **灵活扩展**: 易于添加新工具

这些工具为 Agent 提供了强大的能力，使其能够执行文件操作、代码搜索、命令执行等各种任务。

