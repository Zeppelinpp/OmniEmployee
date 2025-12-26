# Agent Skill System

本文档详细说明 OmniEmployee 的 Skill（技能）系统机制，包括渐进式披露（Progressive Disclosure）和触发时 Context 的变化。

## 概述

Skill 系统遵循 Anthropic 的 Agent Skills 设计模式，采用**渐进式披露**策略来优化上下文窗口的使用。Skill 不是一次性全部加载，而是根据需要在不同阶段逐步加载。

## Skill 的三阶段加载机制

### Phase 1: Discovery（发现阶段）

**触发时机**: Agent 初始化时，调用 `agent.discover_skills()`

**Context 变化**:
- 只加载 Skill 的**元数据**（metadata）
- 包括：name, description, when_to_use, tags
- 每个 Skill 约占用 **~100 tokens**

**示例 Context 内容**:
```
## Available Skills (use when needed)
- [○] **book-flight**: Flight booking assistant that helps users search for flights...
- [○] **codebase-tools**: Advanced code search and analysis tools...
```

**状态标识**:
- `[○]` = 未加载（仅元数据）
- `[✓]` = 已加载（完整指令）

### Phase 2: On-Demand Loading（按需加载）

**触发时机**: 
- Agent 识别到用户请求匹配某个 Skill
- Agent 主动调用 `load_skill("skill-name")` 工具

**Context 变化**:
- 加载完整的 `SKILL.md` 内容
- 包括：完整指令、脚本路径信息、可用参考文件列表
- 每个 Skill 约占用 **~5k tokens**（取决于 SKILL.md 大小）

**Context 新增内容**:
```
## Loaded Skill Instructions

### Skill: book-flight
# Skill: book-flight

Flight booking assistant that helps users search for flights...

## Skill Context
- **Skill Directory**: `src/skills/book-flight`
- **Available Scripts**:
  - `src/skills/book-flight/scripts/get_current_time.py` (run with: `uv run src/skills/book-flight/scripts/get_current_time.py`)
  - `src/skills/book-flight/scripts/search_flights.py` (run with: `uv run src/skills/book-flight/scripts/search_flights.py`)

## Instructions
# Flight Booking Guide
...
```

**Token 预算检查**:
- 每个 Skill 有 `skill_token_budget`（默认 8000 tokens）
- 如果 Skill 超过预算，加载会失败
- 如果接近上下文上限（90%），系统会尝试卸载未使用的 Skill

### Phase 3: Reference Loading（参考文件加载）

**触发时机**:
- 遇到错误（如 "Unknown city", "No flights found"）
- 需要详细示例或错误处理指南
- Agent 主动调用 `load_skill_reference("skill-name", "reference.md")`

**Context 变化**:
- 加载额外的参考文件（如 `reference.md`, `forms.md`）
- 这些文件包含：错误处理策略、示例对话、支持的参数列表等
- 每个参考文件约占用 **~2-5k tokens**

**Context 新增内容**:
```
## Loaded Skill References

### book-flight - reference.md
# Flight Booking Reference

## Error Handling
### Common Issues and Solutions
#### 1. No Flights Available
...
#### 3. Route Not Found
**Supported Cities:**
| City | Airport Code | Airport Name |
|------|--------------|--------------|
| Beijing | PEK | Beijing Capital International Airport |
...
```

## Skill 触发流程

### 1. 用户请求匹配

```
User: "我想订一张去东京的机票"
         ↓
Agent 分析：匹配到 "book-flight" skill
         ↓
检查 Context：skill 是否已加载？
         ↓
未加载 → 调用 load_skill("book-flight")
```

### 2. Skill 加载过程

```python
# Agent 内部执行
1. 检查 skill 是否已加载（避免重复加载）
2. 计算 SKILL.md 的 token 数
3. 检查 token 预算：
   - Skill 大小 < skill_token_budget (8000)?
   - 当前 tokens + Skill tokens < max_tokens * 0.9?
4. 如果预算充足：
   - 加载 SKILL.md 内容
   - 注入 Skill Context（脚本路径）
   - 更新 Context Manager
   - 返回成功
5. 如果预算不足：
   - 尝试卸载未使用的 Skill
   - 如果仍不足，返回失败
```

### 3. Context 更新

**加载前**:
```
System Prompt: ...
Available Skills:
- [○] book-flight: Flight booking assistant...

Messages: [User: "我想订一张去东京的机票"]
Tokens: ~500
```

**加载后**:
```
System Prompt: ...
Available Skills:
- [✓] book-flight: Flight booking assistant...

Loaded Skill Instructions:
### Skill: book-flight
[完整的 SKILL.md 内容，包括指令和脚本路径]

Messages: [
  User: "我想订一张去东京的机票",
  Assistant: [tool_call: load_skill("book-flight")],
  Tool: "Skill 'book-flight' loaded successfully..."
]
Tokens: ~5500 (+5000 from skill)
```

## Skill Reference 加载流程

### 触发条件

1. **错误发生**: Agent 执行工具时遇到错误
   ```
   run_command("search_flights.py --from Beijing --to San Francisco")
   → Error: Unknown destination city 'San Francisco'
   ```

2. **SKILL.md 指示**: SKILL.md 中明确说明遇到错误时应加载 reference
   ```markdown
   ## Error Handling
   **IMPORTANT**: When encountering errors, load the reference:
   ```
   load_skill_reference("book-flight", "reference.md")
   ```
   ```

3. **Agent 决策**: Agent 根据错误信息判断需要更多帮助

### Reference 加载过程

```python
# Agent 执行
1. 检查 skill 是否已加载（reference 需要 skill 先加载）
2. 检查 reference 是否已加载（避免重复）
3. 从文件系统加载 reference.md
4. 计算 token 数
5. 检查上下文空间（如果不足，压缩旧消息）
6. 添加到 Context Manager 的 _loaded_references
7. 更新 token 计数
```

### Context 更新示例

**加载 reference 前**:
```
Loaded Skill Instructions:
### Skill: book-flight
[SKILL.md 内容]

Messages: [
  ...
  Tool: "Error: Unknown destination city 'San Francisco'"
]
Tokens: ~5500
```

**加载 reference 后**:
```
Loaded Skill Instructions:
### Skill: book-flight
[SKILL.md 内容]

Loaded Skill References:
### book-flight - reference.md
[reference.md 完整内容，包括支持的城市列表、错误处理方案]

Messages: [
  ...
  Tool: "Error: Unknown destination city 'San Francisco'",
  Assistant: [tool_call: load_skill_reference("book-flight", "reference.md")],
  Tool: "Reference 'reference.md' loaded: [内容]"
]
Tokens: ~10000 (+4500 from reference)
```

## Skill 卸载机制

### 自动卸载

**触发条件**:
- Context 接近上限（90%）
- 需要为新 Skill 腾出空间

**卸载策略**:
```python
def _unload_unused_skills(self):
    # 检查最近 10 条消息中是否提到该 skill
    recent_content = " ".join([msg.content for msg in messages[-10:]])
    
    for skill_name in loaded_skills:
        if skill_name not in recent_content.lower():
            unload_skill(skill_name)  # 卸载未使用的 skill
```

### 手动卸载

Agent 可以主动卸载不再需要的 Skill：
```python
agent.unload_skill("book-flight")
```

**卸载时的 Context 变化**:
- 移除 Skill 指令
- 移除该 Skill 的所有 reference
- 减少 token 计数
- 更新 Available Skills 列表中的状态标识

## Skill 文件结构

```
src/skills/
└── book-flight/
    ├── SKILL.md           # Phase 2: 主指令文件
    ├── reference.md        # Phase 3: 错误处理、示例
    ├── forms.md           # Phase 3: 表单定义（可选）
    ├── scripts/           # 脚本文件（路径自动注入）
    │   ├── get_current_time.py
    │   └── search_flights.py
    └── references/         # 其他参考文件（可选）
        └── api.md
```

## Context Token 管理

### Token 预算分配

| 组件 | 默认预算 | 说明 |
|------|---------|------|
| System Prompt | ~2000 | 基础系统提示 |
| Skill Metadata | ~100/Skill | Phase 1: 每个 Skill 的元数据 |
| Skill Instructions | ~5000/Skill | Phase 2: 每个 Skill 的完整指令 |
| Skill Reference | ~3000/Ref | Phase 3: 每个参考文件 |
| Messages | 动态 | 对话消息（可压缩） |
| Tool Results | 动态 | 工具执行结果（可截断） |

### Token 使用示例

**场景**: 用户请求订票，Agent 加载 skill 和 reference

```
初始状态:
- System Prompt: 2000 tokens
- Skill Metadata (book-flight): 100 tokens
- Messages: 500 tokens
总计: ~2600 tokens (2%)

加载 Skill 后:
- System Prompt: 2000 tokens
- Skill Metadata: 100 tokens
- Skill Instructions: 5000 tokens  ← 新增
- Messages: 1000 tokens (+500 from tool calls)
总计: ~8100 tokens (6.3%)

加载 Reference 后:
- System Prompt: 2000 tokens
- Skill Metadata: 100 tokens
- Skill Instructions: 5000 tokens
- Skill Reference: 4500 tokens  ← 新增
- Messages: 1500 tokens (+500 from tool calls)
总计: ~13100 tokens (10.2%)
```

## 最佳实践

### 1. Skill 设计

- **保持 SKILL.md 简洁**: 只包含核心指令，详细内容放在 reference.md
- **明确错误处理**: 在 SKILL.md 中指示何时加载 reference
- **使用相对路径**: 脚本路径会自动解析为绝对路径

### 2. Reference 设计

- **错误处理优先**: 包含常见错误的解决方案
- **提供示例**: 包含对话示例和用例
- **列出支持值**: 如支持的城市列表、参数选项等

### 3. Token 优化

- **分阶段加载**: 不要一次性加载所有内容
- **及时卸载**: 任务完成后卸载不再需要的 Skill
- **压缩策略**: 系统会自动压缩旧消息和工具结果

## 总结

Skill 系统通过渐进式披露实现了高效的上下文管理：

1. **Phase 1**: 只加载元数据，让 Agent 知道有哪些 Skill 可用
2. **Phase 2**: 按需加载完整指令，提供详细的操作指南
3. **Phase 3**: 遇到问题时加载参考文件，获取错误处理和示例

这种设计既保证了 Agent 有足够的信息完成任务，又避免了不必要的 token 浪费。

