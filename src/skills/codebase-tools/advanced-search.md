# Advanced Search Techniques

## Regex Patterns for Code Search

### Language-Specific Patterns

#### Python

```regex
# Function definitions with decorators
@\w+\s*\n\s*def \w+

# Class methods
def \w+\(self

# Async functions
async def \w+

# Type hints
def \w+\([^)]*:\s*\w+

# Dataclass definitions
@dataclass\s*\nclass \w+
```

#### TypeScript/JavaScript

```regex
# Arrow functions
const \w+ = \([^)]*\) =>

# React components
(function|const) \w+\s*[=:]\s*(React\.FC|FC|Component)

# Hooks
use[A-Z]\w+

# Interface definitions
interface \w+ \{
```

#### Go

```regex
# Function definitions
func \w+\(

# Method definitions
func \(\w+ \*?\w+\) \w+\(

# Interface definitions
type \w+ interface \{
```

## Complex Search Strategies

### Finding Dead Code

```python
# Find function definitions
grep(pattern=r"def (\w+)\(", file_type="py")

# For each function, search for usages
grep(pattern=r"function_name\(")

# If no usages found (except definition), it might be dead code
```

### Finding Security Issues

```python
# Hardcoded secrets
grep(pattern=r"(password|secret|api_key|token)\s*=\s*['\"]", case_sensitive=False)

# SQL injection vulnerabilities
grep(pattern=r"execute\([^)]*%s|execute\([^)]*\+")

# Unsafe deserialization
grep(pattern=r"pickle\.load|yaml\.load\(")
```

### Finding Performance Issues

```python
# N+1 queries (Django)
grep(pattern=r"\.objects\.(get|filter)\([^)]*\).*for.*in")

# Nested loops
grep(pattern=r"for.*:\s*\n\s*for.*:")

# Large list comprehensions
grep(pattern=r"\[.*for.*for.*\]")
```

## Multi-File Analysis

### Dependency Analysis

1. Find all imports in a file:
```python
grep(pattern=r"^(from|import)\s+(\w+)", path="target_file.py")
```

2. For each import, find where it's defined:
```python
grep(pattern=r"(def|class)\s+ImportedName")
```

### Call Graph Construction

1. Find function definitions:
```python
grep(pattern=r"def (\w+)\(")
```

2. For each function, find what it calls:
```python
read_file(path="file.py", start_line=func_start, end_line=func_end)
# Parse the function body for function calls
```

## Tips for Efficient Searching

### 1. Use File Type Filters

Always specify `file_type` when possible to avoid searching binary files and irrelevant content.

### 2. Start Broad, Then Narrow

```python
# Start with a broad search
grep(pattern="authenticate")

# Narrow down based on results
grep(pattern=r"def authenticate\(", file_type="py")
```

### 3. Use Word Boundaries

```python
# Without boundary - matches "user", "username", "userdata"
grep(pattern="user")

# With boundary - matches only "user"
grep(pattern=r"\buser\b", whole_word=True)
```

### 4. Combine with Context

```python
# Get surrounding context for better understanding
grep(pattern="TODO", context_lines=2)
```

