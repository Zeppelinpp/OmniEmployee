这是一份为 Code Agent 编写的**“类脑进化记忆组件 (Bio-Inspired Evolving Memory, BIEM)”**工程实现文档。该方案抛弃了传统的“单一向量库检索”，转而采用一种基于“能量衰减”和“关联图谱”的动态代谢架构。

---

# Feature 开发文档：类脑进化记忆组件 (BIEM)

## 1. 目标概述
构建一个具备自动代谢、关联联想和冲突检测功能的 Agent 记忆插件。该组件需实现：
*   **毫秒级及时性**：通过三级缓存与能量分层实现。
*   **语义准确性**：基于多维锚点（时间、空间、情感、逻辑）的图关联召回。
*   **逻辑对齐**：内置认知失调检测机制，识别并处理事实冲突。

---

## 2. 核心数据结构定义

### 2.1 记忆节点 (MemoryNode)
```python
class MemoryNode:
    id: uuid
    content: str          # 原始信息片段
    vector: ndarray       # 语义向量
    metadata: {
        timestamp: float,
        location: str,    # 环境上下文
        entities: list,   # 提取的实体锚点
        sentiment: float  # 情感极性/强度
    }
    energy: float         # 初始能量值(0-1.0)，由LLM评估信息重要性决定
    last_accessed: float  # 最后一次激活时间
    links: list[Link]     # 与其他节点的关联边
```

### 2.2 关联边 (Link)
*   **Source/Target**: 节点 ID。
*   **Weight**: 关联强度。
*   **Type**: `temporal` (先后顺序), `causal` (因果), `semantic` (语义相似).

---

## 3. 三级存储架构 (Storage Tiers)

1.  **L1 - 工作内存 (Working Canvas)**: 
    *   **实现**: Python Dict / Redis。
    *   **内容**: 当前任务最相关的 Top-K 高能节点。
2.  **L2 - 联想网 (Association Web)**: 
    *   **实现**: Graph Database (NetworkX 或 Neo4j) + Vector DB (FAISS/Milvus)。
    *   **内容**: 全量情境记忆。
3.  **L3 - 知识基座 (The Crystal)**: 
    *   **实现**: 结构化数据库 (PostgreSQL)。
    *   **内容**: 经异步固化后的事实与规则。

---

## 4. 核心算子逻辑 (Core Operations)

### 4.1 写入与代谢逻辑 (The Metabolism)
*   **写入 (Ingestion)**:
    1.  提取 Entity 和 Sentiment。
    2.  计算初始能量 $E_{init}$（根据任务相关度）。
    3.  建立与最近活跃节点的 `temporal` 链接。
*   **衰减 (Decay)**: 
    *   公式：$E_{current} = E_{last} \cdot e^{-\lambda \Delta t}$，其中 $\lambda$ 是衰减系数。
*   **整合 (Consolidation)**: 
    *   后台异步任务：扫描 L2 中关联度极高且被频繁激活的节点簇，利用 LLM 将其合并为一条“语义事实”存入 L3。

### 4.2 召回与联想逻辑 (Spreading Activation)
1.  **直接召回**: 根据当前 Input 进行向量检索 + 关键词检索。
2.  **能量扩散 (Assocation Spread)**: 
    *   激活召回节点的相邻节点。即使相邻节点与当前输入向量距离较远，但如果由于“时间”或“因果”联系紧密，其能量也会被点亮进入工作内存。
3.  **排序优先级**: $Score = \alpha \cdot Similarity + \beta \cdot Energy + \gamma \cdot Recency$。

### 4.3 冲突检测逻辑 (Cognitive Dissonance)
*   **机制**: 在新信息写入 L1 时，检索 L2/L3 中语义重合度高于 0.8 但逻辑极性相反的节点。
*   **动作**: 
    *   若检测到冲突，系统不覆盖旧记忆，而是生成一个 `ConflictNode`。
    *   向 Agent 发送 `DissonanceSignal`，强制触发“确认询问”或“逻辑重构”指令。

---

## 5. 工程开发任务清单 (Implementation Tasks)

### Phase 1: 基础设施搭建
- [ ] 实现 `MemoryNode` 和 `Link` 的序列化协议。
- [ ] 集成 `FAISS` 处理向量索引，`NetworkX` 处理图关联。
- [ ] 开发 `EnergyController` 模块，负责定时计算能量衰减。

### Phase 2: 记忆链路流水线
- [ ] 开发 `Encoder` 模块：调用 LLM 提取原始输入的实体、情感及初步权重。
- [ ] 实现 `AssociationRouter`：在写入时自动搜索潜在关联并建立 Edge。
- [ ] 开发 `TierManager`：管理 L1, L2, L3 之间的数据流转（升位与降位）。

### Phase 3: 召回优化 (Timeliness & Accuracy)
- [ ] 实现“两阶段召回”：先由局部 Graph 快速扩散，再并行由 Vector DB 精准修正。
- [ ] 编写 `ConflictChecker` 模块：基于 LLM 对比两个冲突节点的逻辑一致性。

### Phase 4: Agent 集成接口
- [ ] 暴露 `get_context()` 接口：为 LLM Prompt 提供当前最活跃的记忆片段。
- [ ] 暴露 `record_event()` 接口：记录 Agent 的决策及其反馈（强化记忆）。

---

## 6. 关键性能指标 (Metrics)
*   **Latency**: 记忆检索总耗时应 $< 200ms$。
*   **Alignment Rate**: 能够自动识别并拦截 80% 以上的虚假矛盾信息。
*   **Context Density**: 在相同的 Token 限制下，由于经过了“压缩整合”，记忆信息熵应提升 50% 以上。

---
