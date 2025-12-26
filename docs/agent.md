# Agent Loop and Context Management

本文档详细阐述 OmniEmployee 的 Agent Loop 执行逻辑、System Prompt 的作用、Context 在多轮对话中的变化，以及工具执行和任务完成的完整流程。

## Agent Loop 概述

Agent Loop 是 OmniEmployee 的核心执行引擎，负责：
1. 接收用户输入
2. 调用 LLM 生成响应或工具调用
3. 执行工具并收集结果
4. 更新上下文
5. 循环直到任务完成

## System Prompt 的作用

### System Prompt 结构

System Prompt 是每次 LLM 调用时都会包含的上下文，由以下部分组成：

```
┌─────────────────────────────────────────────────┐
│           System Prompt Components              │
├─────────────────────────────────────────────────┤
│ 1. Core Behavior Loop                          │
│    - 5步推理流程（分析→评估→计划→执行→迭代）    │
│                                                 │
│ 2. Skill Loading Protocol                      │
│    - 渐进式披露说明                            │
│    - 何时加载 Skill                            │
│    - 何时加载 Reference                        │
│                                                 │
│ 3. Guidelines                                   │
│    - 代码修改原则                              │
│    - 工具使用规范                              │
│                                                 │
│ 4. Workspace Information                       │
│    - 工作目录路径                              │
│                                                 │
│ 5. Available Tools                             │
│    - 所有可用工具的摘要                        │
│                                                 │
│ 6. Available Skills                            │
│    - Skill 元数据列表（Phase 1）               │
│                                                 │
│ 7. Loaded Skill Instructions                   │
│    - 已加载 Skill 的完整指令（Phase 2）       │
│    - 已加载 Reference 的内容（Phase 3）        │
└─────────────────────────────────────────────────┘
```

### System Prompt 的动态更新

System Prompt 不是静态的，会根据 Context 状态动态更新：

```python
def build_messages(self) -> list[dict]:
    system_content = self._system_prompt  # 基础提示
    
    # 动态添加 Skill 摘要
    skill_summary = self.get_skill_summary()
    if skill_summary:
        system_content += f"\n\n{skill_summary}"
    
    # 动态添加已加载的 Skill 指令
    skill_instructions = self.get_loaded_skill_instructions()
    if skill_instructions:
        system_content += f"\n\n{skill_instructions}"
    
    return [{"role": "system", "content": system_content}]
```

## Agent Loop 执行流程

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop Execution                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [User Input]                                               │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 1: Add User Message to Context                  │  │
│  │   - context.add_user_message(user_input)              │  │
│  │   - Token count updated                              │  │
│  └──────────────────────────────────────────────────────┘  │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 2: Build Messages for LLM                       │  │
│  │   - System Prompt (with skills & tools)              │  │
│  │   - Conversation History                             │  │
│  │   - Tool Definitions                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 3: Call LLM (via LiteLLM)                        │  │
│  │   - Input: messages + tools                           │  │
│  │   - Output: response or tool_calls                    │  │
│  └──────────────────────────────────────────────────────┘  │
│       │                                                     │
│       ├─────────────────┬─────────────────┐              │
│       ▼                 ▼                 ▼                │
│  [Tool Calls]    [Final Response]   [Error]             │
│       │                 │                 │              │
│       ▼                 │                 │              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Step 4a: Execute Tools                                │ │
│  │   - For each tool_call:                              │ │
│  │     1. Parse arguments                               │ │
│  │     2. Execute tool.execute(**args)                   │ │
│  │     3. Add result to context                         │ │
│  │   - Add assistant message with tool_calls             │ │
│  └──────────────────────────────────────────────────────┘ │
│       │                                                     │
│       └─────────────────┐                                  │
│                         ▼                                  │
│              [Loop Back to Step 2]                        │
│                                                             │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Step 4b: Return Final Response                        │  │
│  │   - Add assistant message                            │  │
│  │   - State = COMPLETED                                │  │
│  │   - Return to user                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 详细执行步骤

#### Step 1: 接收用户输入

```python
async def run_stream(self, user_input: str):
    # 添加用户消息到上下文
    self.agent.context.add_user_message(user_input)
    
    # Context 变化：
    # - _messages 列表新增一条 USER 消息
    # - _current_tokens 增加（约 ~100-500 tokens，取决于输入长度）
```

**Context 状态**:
```
Messages: [
  User: "我想订一张去东京的机票"
]
Tokens: ~500
```

#### Step 2: 构建消息和工具定义

```python
async def _call_llm(self) -> LLMResponse:
    # 构建消息列表
    messages = self.agent.get_messages()
    # [
    #   {"role": "system", "content": "完整系统提示..."},
    #   {"role": "user", "content": "我想订一张去东京的机票"}
    # ]
    
    # 获取工具定义
    tools = self.agent.get_tool_definitions()
    # [
    #   {"type": "function", "function": {...}},  # grep
    #   {"type": "function", "function": {...}},  # list_dir
    #   {"type": "function", "function": {...}},  # load_skill
    #   ...
    # ]
    
    # 添加技能管理工具
    if self.config.auto_load_skills:
        tools = self._add_skill_tools(tools)
    
    return await self.llm.complete(messages, tools)
```

**System Prompt 内容示例**:
```
You are OmniEmployee, an AI assistant...

## Available Tools
- grep: Search file contents using ripgrep...
- list_dir: List directory contents...
- load_skill: Load a skill to get detailed instructions...

## Available Skills
- [○] book-flight: Flight booking assistant...

## Loaded Skill Instructions
(空，因为还没有加载 skill)
```

#### Step 3: LLM 响应处理

```python
response = await self.llm.complete(messages, tools)

# LLM 可能返回两种结果：
# 1. 工具调用请求
if response.has_tool_calls:
    # 处理工具调用
    tool_calls = response.tool_calls
    # [
    #   ToolCall(id="call_123", name="load_skill", arguments={"name": "book-flight"})
    # ]

# 2. 最终回复
else:
    # 返回给用户
    final_response = response.content
```

#### Step 4a: 执行工具调用

```python
# 添加 Assistant 消息（包含工具调用）
self.agent.context.add_assistant_message(
    content=response.content,  # 可能为空
    tool_calls=tool_calls
)

# 执行每个工具
for tool_call in tool_calls:
    result = await self._execute_single_tool(
        tool_call.name,
        tool_call.arguments
    )
    
    # 添加工具结果到上下文
    self.agent.context.add_tool_result(
        tool_call_id=tool_call.id,
        content=result.to_message(),
        is_error=not result.success
    )

# Context 变化：
# - 新增 Assistant 消息（包含 tool_calls）
# - 新增 Tool 消息（工具执行结果）
# - Token 增加（Assistant 消息 + Tool 结果）
```

**Context 状态更新**:
```
Messages: [
  User: "我想订一张去东京的机票",
  Assistant: [tool_call: load_skill("book-flight")],
  Tool: "Skill 'book-flight' loaded successfully..."
]
Tokens: ~1500 (+1000 from tool execution)
```

#### Step 4b: 循环回到 Step 2

```python
# 工具执行后，循环回到 LLM 调用
# 此时 System Prompt 已更新（包含加载的 Skill）

# 新的 System Prompt 包含：
## Loaded Skill Instructions
### Skill: book-flight
[完整的 SKILL.md 内容，包括指令和脚本路径]

# LLM 现在知道如何执行订票流程
```

**Context 状态**:
```
System Prompt: [
  ...基础提示...,
  Available Skills: [✓] book-flight: ...,
  Loaded Skill Instructions: [完整的 book-flight 指令]
]

Messages: [
  User: "我想订一张去东京的机票",
  Assistant: [tool_call: load_skill("book-flight")],
  Tool: "Skill 'book-flight' loaded successfully..."
]
Tokens: ~6500 (+5000 from skill loading)
```

#### Step 5: 继续执行（根据 Skill 指令）

```python
# LLM 根据加载的 Skill 指令，继续执行任务
# 例如：调用 get_current_time.py 脚本

response = await self.llm.complete(messages, tools)
# → LLM 返回: tool_call("run_command", {"command": "uv run .../get_current_time.py"})

# 执行工具
result = await run_command.execute(command="...")

# 添加结果
context.add_tool_result(...)

# Context 继续更新
```

## 多轮对话中的 Context 变化

### 场景：不完整的订票请求

#### 第一轮：用户请求

**用户输入**: "我想订一张去东京的机票"

**Context 初始状态**:
```
System Prompt: [基础提示 + Available Skills]
Messages: []
Tokens: ~2000
```

**Agent 处理**:
1. 添加用户消息 → Tokens: ~2500
2. LLM 分析：需要 book-flight skill
3. 调用 `load_skill("book-flight")` → Tokens: ~7500
4. LLM 根据 Skill 指令，发现缺少信息
5. 返回：询问缺失信息

**Context 最终状态**:
```
Messages: [
  User: "我想订一张去东京的机票",
  Assistant: [tool_call: load_skill("book-flight")],
  Tool: "Skill loaded...",
  Assistant: "我需要以下信息：出发城市、出发日期..."
]
Tokens: ~8000
```

#### 第二轮：用户补充信息

**用户输入**: "从北京出发，明天的航班，经济舱，1个人"

**Context 状态**:
```
System Prompt: [
  ...基础提示...,
  Loaded Skill Instructions: [book-flight 完整指令]
]

Messages: [
  User: "我想订一张去东京的机票",
  Assistant: [tool_call: load_skill("book-flight")],
  Tool: "Skill loaded...",
  Assistant: "我需要以下信息...",
  User: "从北京出发，明天的航班，经济舱，1个人"  ← 新增
]
Tokens: ~8500
```

**Agent 处理**:
1. LLM 分析：已有完整信息
2. 根据 Skill 指令 Step 1：检查当前时间
3. 调用 `run_command("get_current_time.py")` → Tokens: ~9000
4. 根据 Skill 指令 Step 3：搜索航班
5. 调用 `run_command("search_flights.py ...")` → Tokens: ~9500
6. 返回航班选项

**Context 最终状态**:
```
Messages: [
  ...之前的消息...,
  User: "从北京出发，明天的航班，经济舱，1个人",
  Assistant: [tool_call: run_command("get_current_time.py")],
  Tool: "Current Date: 2025-12-26...",
  Assistant: [tool_call: run_command("search_flights.py ...")],
  Tool: "Searching flights... [航班列表]",
  Assistant: "我找到了以下航班选项：..."
]
Tokens: ~10000
```

### Context 压缩机制

当 Context 接近上限时（默认 80%），系统会自动压缩：

```python
def _compress_context(self):
    # 策略 1: 压缩旧工具结果
    self._summarize_old_tool_results()
    # 将旧工具结果从完整输出压缩为摘要
    
    # 策略 2: 压缩旧对话轮次
    self._compress_old_turns()
    # 将旧消息压缩为摘要，保留最近 N 轮
    
    # 策略 3: 卸载未使用的 Skill
    self._unload_unused_skills()
    # 卸载最近消息中未提及的 Skill
```

**压缩示例**:
```
压缩前:
Messages: [50 条消息，包含大量工具结果]
Tokens: ~100000 (78%)

压缩后:
Messages: [
  System: "[Earlier conversation summary]...",
  ...最近 10 条消息（完整）...
]
Tokens: ~60000 (47%)
```

## 工具执行和任务完成逻辑

### 工具执行流程

```python
async def _execute_single_tool(self, name: str, arguments: dict):
    # 1. 检查是否是技能管理工具
    if name == "load_skill":
        return self._handle_load_skill(arguments["name"])
    elif name == "load_skill_reference":
        return self._handle_load_skill_reference(...)
    
    # 2. 执行常规工具
    tool = self.agent.tools.get(name)
    if not tool:
        return ToolResult(status=ERROR, error="Tool not found")
    
    # 3. 执行工具
    try:
        result = await tool.execute(**arguments)
    except Exception as e:
        result = ToolResult(status=ERROR, error=str(e))
    
    # 4. 返回结果
    return result
```

### 任务完成判断

Agent 通过以下方式判断任务是否完成：

1. **LLM 返回最终回复**（无工具调用）
   ```python
   if not response.has_tool_calls:
       # 任务完成
       self.state = LoopState.COMPLETED
       return final_response
   ```

2. **达到最大迭代次数**
   ```python
   if self._iteration >= self.config.max_iterations:
       self.state = LoopState.MAX_ITERATIONS
       return "Reached maximum iterations"
   ```

3. **遇到错误**
   ```python
   except Exception as e:
       self.state = LoopState.ERROR
       return LoopResult(error=str(e))
   ```

### 完整任务执行示例

**任务**: "帮我订一张从北京到东京的机票，明天出发"

**执行流程**:

```
Iteration 1:
  Input: "帮我订一张从北京到东京的机票，明天出发"
  LLM: tool_call(load_skill, "book-flight")
  Execute: load_skill("book-flight")
  Result: Skill loaded
  State: TOOL_CALLING → THINKING

Iteration 2:
  Input: [之前的消息 + tool result]
  LLM: tool_call(run_command, "get_current_time.py")
  Execute: run_command(...)
  Result: Current date: 2025-12-26
  State: TOOL_CALLING → THINKING

Iteration 3:
  Input: [之前的消息 + tool result]
  LLM: tool_call(run_command, "search_flights.py --from Beijing --to Tokyo --date 2025-12-27")
  Execute: run_command(...)
  Result: [航班列表]
  State: TOOL_CALLING → THINKING

Iteration 4:
  Input: [之前的消息 + tool result]
  LLM: "我找到了以下航班选项：[展示航班列表]"
  State: COMPLETED
  Return: 最终回复
```

## System Prompt 与 Context 的协同

### System Prompt 的动态性

System Prompt 不是静态的，它会根据 Context 状态动态更新：

```python
# 初始状态
System Prompt = 基础提示 + Available Skills (metadata only)

# Skill 加载后
System Prompt = 基础提示 + Available Skills + Loaded Skill Instructions

# Reference 加载后
System Prompt = 基础提示 + Available Skills + Loaded Skill Instructions + Loaded References
```

### Context 与 System Prompt 的关系

```
┌─────────────────────────────────────────┐
│         Context Manager                  │
├─────────────────────────────────────────┤
│  System Prompt (动态构建)                │
│  ├─ 基础提示（静态）                     │
│  ├─ Available Skills（Phase 1）         │
│  ├─ Loaded Skills（Phase 2）            │
│  └─ Loaded References（Phase 3）        │
│                                          │
│  Messages（对话历史）                    │
│  ├─ User Messages                       │
│  ├─ Assistant Messages                  │
│  └─ Tool Results                        │
└─────────────────────────────────────────┘
         │
         ▼
    build_messages()
         │
         ▼
┌─────────────────────────────────────────┐
│      LLM API Call                       │
│  messages: [                            │
│    {role: "system", content: "..."},   │
│    {role: "user", content: "..."},      │
│    ...                                  │
│  ]                                      │
│  tools: [...]                           │
└─────────────────────────────────────────┘
```

## 总结

OmniEmployee 的 Agent Loop 通过以下机制实现高效的任务执行：

1. **动态 System Prompt**: 根据加载的 Skill 和 Reference 动态更新
2. **渐进式 Skill 加载**: 按需加载，节省 Token
3. **循环执行**: 工具调用 → 结果 → 继续思考 → 工具调用/完成
4. **Context 管理**: 自动压缩和优化，保持高效
5. **错误处理**: 完善的错误处理和恢复机制

这种设计使得 Agent 能够：
- 高效利用上下文窗口
- 灵活处理复杂任务
- 在多轮对话中保持上下文连贯性
- 根据任务需要动态加载相关知识

