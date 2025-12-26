# Codebase Tools Reference

This document contains supplementary information for the codebase-tools skill, including complete tool documentation, advanced search techniques, and error handling strategies.

## Tool Reference

### grep

**Purpose:** Search for patterns in files across the codebase.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | Yes | - | Regex pattern to search for |
| `path` | string | No | "." | Directory or file to search in |
| `file_type` | string | No | None | File extension filter (e.g., "py", "ts") |
| `case_sensitive` | bool | No | True | Case-sensitive matching |
| `whole_word` | bool | No | False | Match whole words only |
| `context_lines` | int | No | 0 | Lines of context before/after match |
| `max_results` | int | No | 100 | Maximum number of results |

**Examples:**

```python
# Basic search
grep(pattern="TODO")

# Search with file type filter
grep(pattern=r"def \w+\(", file_type="py")

# Case-insensitive with context
grep(pattern="error", case_sensitive=False, context_lines=2)

# Whole word matching
grep(pattern="user", whole_word=True)

# Search in specific directory
grep(pattern="import", path="src/utils", file_type="py")
```

---

### list_dir

**Purpose:** Explore directory structure and list contents.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | "." | Directory path to list |
| `depth` | int | No | 1 | Recursion depth |
| `pattern` | string | No | None | Glob pattern filter (e.g., "*.py") |
| `show_hidden` | bool | No | False | Include hidden files/directories |
| `dirs_only` | bool | No | False | Show only directories |

**Examples:**

```python
# List current directory
list_dir()

# Recursive listing
list_dir(path="src", depth=3)

# Filter by pattern
list_dir(path=".", pattern="*.py", depth=2)

# Show only directories
list_dir(path=".", dirs_only=True, depth=2)

# Include hidden files
list_dir(path=".", show_hidden=True)
```

---

### read_file

**Purpose:** Read file contents, optionally with line range.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | File path to read |
| `start_line` | int | No | None | Starting line number (1-indexed) |
| `end_line` | int | No | None | Ending line number (inclusive) |
| `max_lines` | int | No | 1000 | Maximum lines to read |

**Examples:**

```python
# Read entire file
read_file(path="src/main.py")

# Read specific line range
read_file(path="src/main.py", start_line=50, end_line=100)

# Read first 50 lines
read_file(path="src/main.py", end_line=50)

# Limit output for large files
read_file(path="large_file.py", max_lines=500)
```

---

### write_file

**Purpose:** Modify file contents with various modes.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | File path to write |
| `content` | string | Yes | - | Content to write |
| `mode` | string | No | "overwrite" | Write mode (see below) |
| `start_line` | int | No | None | For insert/replace modes |
| `end_line` | int | No | None | For replace_lines mode |
| `create_dirs` | bool | No | False | Create parent directories |

**Write Modes:**

| Mode | Description | Required Params |
|------|-------------|-----------------|
| `overwrite` | Replace entire file content | - |
| `append` | Add content to end of file | - |
| `insert` | Insert at specific line | `start_line` |
| `replace_lines` | Replace line range | `start_line`, `end_line` |

**Examples:**

```python
# Overwrite entire file
write_file(path="config.json", content='{"key": "value"}', mode="overwrite")

# Append to file
write_file(path="log.txt", content="New log entry\n", mode="append")

# Insert at line 10
write_file(path="main.py", content="import os\n", mode="insert", start_line=10)

# Replace lines 45-50
write_file(
    path="main.py",
    content="def new_function():\n    pass\n",
    mode="replace_lines",
    start_line=45,
    end_line=50
)

# Create file with parent directories
write_file(
    path="new_dir/subdir/file.py",
    content="# New file",
    create_dirs=True
)
```

---

### run_command

**Purpose:** Execute system commands.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | string | Yes | - | Command to execute |
| `working_dir` | string | No | "." | Working directory |
| `timeout` | int | No | 60 | Timeout in seconds |
| `env` | dict | No | None | Environment variables |

**Examples:**

```python
# Run tests
run_command(command="pytest tests/")

# Run with specific directory
run_command(command="npm install", working_dir="frontend")

# Run with timeout
run_command(command="python long_script.py", timeout=300)

# Run with environment variables
run_command(command="python app.py", env={"DEBUG": "1"})
```

---

## Advanced Search Patterns

### Language-Specific Regex Patterns

#### Python

```python
# Function definitions
grep(pattern=r"def \w+\(", file_type="py")

# Function with decorators
grep(pattern=r"@\w+\s*\n\s*def \w+", file_type="py")

# Class definitions
grep(pattern=r"class \w+.*:", file_type="py")

# Async functions
grep(pattern=r"async def \w+", file_type="py")

# Type-annotated functions
grep(pattern=r"def \w+\([^)]*:\s*\w+", file_type="py")

# Dataclass definitions
grep(pattern=r"@dataclass\s*\nclass \w+", file_type="py")

# Import statements
grep(pattern=r"^(from|import)\s+", file_type="py")
```

#### TypeScript/JavaScript

```python
# Arrow functions
grep(pattern=r"const \w+ = \([^)]*\) =>", file_type="ts")

# React components
grep(pattern=r"(function|const) \w+.*React\.FC", file_type="tsx")

# Hooks
grep(pattern=r"use[A-Z]\w+", file_type="ts")

# Interface definitions
grep(pattern=r"interface \w+ \{", file_type="ts")

# Type definitions
grep(pattern=r"type \w+ =", file_type="ts")

# Export statements
grep(pattern=r"export (default |const |function )", file_type="ts")
```

#### Go

```python
# Function definitions
grep(pattern=r"func \w+\(", file_type="go")

# Method definitions
grep(pattern=r"func \(\w+ \*?\w+\) \w+\(", file_type="go")

# Interface definitions
grep(pattern=r"type \w+ interface \{", file_type="go")

# Struct definitions
grep(pattern=r"type \w+ struct \{", file_type="go")
```

---

## Complex Search Strategies

### Finding Dead Code

```python
# Step 1: Find all function definitions
results = grep(pattern=r"def (\w+)\(", file_type="py")

# Step 2: For each function, search for usages
for func_name in extracted_function_names:
    usages = grep(pattern=rf"\b{func_name}\b", file_type="py")
    # If only 1 result (the definition), it might be dead code
```

### Finding Security Issues

```python
# Hardcoded secrets
grep(pattern=r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", 
     case_sensitive=False)

# SQL injection vulnerabilities
grep(pattern=r"execute\([^)]*%|execute\([^)]*\+", file_type="py")

# Unsafe deserialization
grep(pattern=r"pickle\.load|yaml\.load\((?!.*Loader)", file_type="py")

# Eval usage
grep(pattern=r"\beval\s*\(", file_type="py")
```

### Finding Performance Issues

```python
# N+1 queries (Django)
grep(pattern=r"\.objects\.(get|filter)\([^)]*\).*for.*in", file_type="py")

# Nested loops
grep(pattern=r"for.*:\s*\n\s*for.*:", file_type="py")

# Large list comprehensions
grep(pattern=r"\[.*for.*for.*\]", file_type="py")

# Missing indexes (SQL)
grep(pattern=r"WHERE.*=.*AND.*=", file_type="sql")
```

---

## Multi-File Analysis

### Dependency Analysis

```python
# Step 1: Find all imports in a file
imports = grep(pattern=r"^(from|import)\s+(\w+)", path="target_file.py")

# Step 2: For each import, find where it's defined
for module in imported_modules:
    grep(pattern=rf"(def|class)\s+{module}", file_type="py")
```

### Call Graph Construction

```python
# Step 1: Find function definitions
functions = grep(pattern=r"def (\w+)\(", file_type="py")

# Step 2: For each function, read its body
for func_name, file_path, line_num in functions:
    content = read_file(path=file_path, start_line=line_num, end_line=line_num+50)
    # Parse content to find function calls

# Step 3: Build call graph from relationships
```

### Finding Circular Dependencies

```python
# Step 1: Map all imports per file
# Step 2: Build dependency graph
# Step 3: Detect cycles using DFS
```

---

## Error Handling

### Common Errors and Solutions

#### File Not Found

**Symptoms:** `FileNotFoundError` or "No such file or directory"

**Solutions:**
1. Verify the file path using `list_dir`
2. Check for typos in the path
3. Ensure the file hasn't been moved or deleted

```python
# Verify file exists
list_dir(path="src", pattern="*.py")

# Then read
read_file(path="src/correct_file.py")
```

#### Permission Denied

**Symptoms:** `PermissionError` when reading/writing

**Solutions:**
1. Check file permissions
2. Ensure file is not locked by another process
3. Verify you have write access to the directory

```python
# Check file info
run_command(command="ls -la target_file.py")
```

#### Pattern Not Found

**Symptoms:** Empty results from `grep`

**Solutions:**
1. Verify the pattern syntax (escape special characters)
2. Try a broader search first
3. Check file type filter

```python
# Start broad
grep(pattern="function_name")

# Then narrow down
grep(pattern=r"def function_name\(", file_type="py")
```

#### Syntax Errors After Modification

**Symptoms:** Code doesn't run after `write_file`

**Solutions:**
1. Verify indentation matches surrounding code
2. Check for missing/extra brackets
3. Validate syntax before committing

```python
# Validate Python syntax
run_command(command="python -m py_compile modified_file.py")

# Validate JSON
run_command(command="python -c \"import json; json.load(open('config.json'))\"")
```

#### Partial Match Issues

**Symptoms:** Grep returns too many/few results

**Solutions:**
1. Use word boundaries for exact matches
2. Escape special regex characters
3. Use `whole_word=True` for simple patterns

```python
# Too many results - use word boundary
grep(pattern=r"\buser\b", whole_word=True)

# Escape special characters
grep(pattern=r"config\.json")  # Matches "config.json" not "configXjson"
```

---

## Best Practices

### 1. Always Read Before Writing

```python
# Good: Read first, understand context
content = read_file(path="module.py")
# Analyze content, plan changes
write_file(path="module.py", content=modified_content)

# Bad: Write without understanding
write_file(path="module.py", content=new_content)  # May break things
```

### 2. Make Minimal Changes

```python
# Good: Change only what's needed
write_file(
    path="module.py",
    content="new_value",
    mode="replace_lines",
    start_line=45,
    end_line=45
)

# Bad: Rewrite entire file for one change
write_file(path="module.py", content=entire_file_with_one_change)
```

### 3. Verify After Each Change

```python
# After modification
read_file(path="module.py", start_line=40, end_line=50)  # Verify change

# Check for remaining old code
grep(pattern="old_function_name")  # Should return empty

# Validate syntax
run_command(command="python -m py_compile module.py")
```

### 4. Preserve Code Style

- Match existing indentation (spaces vs tabs)
- Follow naming conventions in the project
- Maintain consistent quote style
- Keep import organization

### 5. Handle Large Files Efficiently

```python
# Good: Read only needed section
read_file(path="large_file.py", start_line=100, end_line=200)

# Bad: Read entire large file
read_file(path="large_file.py")  # Slow, memory intensive
```

### 6. Use Incremental Changes

```python
# Good: Apply changes one at a time, verify each
write_file(path="file.py", content=change1, mode="replace_lines", ...)
read_file(path="file.py")  # Verify
write_file(path="file.py", content=change2, mode="replace_lines", ...)
read_file(path="file.py")  # Verify

# Bad: Apply all changes at once
write_file(path="file.py", content=all_changes)  # Hard to debug if wrong
```

---

## Common Workflows

### Bug Investigation

```
1. grep(pattern="error_message") → Find where error occurs
2. read_file(path, start_line=N-10, end_line=N+10) → Get context
3. grep(pattern="function_name") → Find function definition
4. read_file(...) → Understand the function
5. write_file(..., mode="replace_lines") → Fix the bug
6. Verify fix with grep and read_file
```

### Adding a New Feature

```
1. list_dir(depth=2) → Understand project structure
2. grep(pattern="similar_feature") → Find related code
3. read_file(...) → Study the pattern
4. write_file(..., mode="overwrite") → Create new file
5. read_file(...) → Verify creation
6. Update imports/exports as needed
```

### Code Refactoring

```
1. grep(pattern="old_name") → Find all occurrences
2. For each occurrence:
   a. read_file(...) → Get context
   b. write_file(..., mode="replace_lines") → Update
3. grep(pattern="old_name") → Verify no remaining occurrences
4. Run tests to verify behavior unchanged
```

### Bulk Updates

```
1. grep(pattern="old_value", file_type="json") → Find all config files
2. For each file:
   a. read_file(path) → Get current content
   b. Modify content
   c. write_file(path, content)
3. Verify all instances updated consistently
```
