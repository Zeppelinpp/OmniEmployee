---
name: codebase-tools
description: Advanced codebase exploration and manipulation toolkit for searching code, navigating project structure, and making precise file edits.
license: MIT
version: 1.0.0
tags: [development, search, navigation, editing]
when_to_use: When you need to explore, search, or modify code in a project. Use for finding function definitions, searching for patterns, understanding project structure, or making targeted code changes.
required_tools: [grep, list_dir, read_file, write_file]
required_packages: [ripgrep, fd]
---

# Codebase Tools Guide

## Overview

This skill provides patterns and best practices for exploring and manipulating codebases efficiently using the built-in tools: `grep`, `list_dir`, `read_file`, and `write_file`.

## Quick Reference

| Task | Tool | Example |
|------|------|---------|
| Find code by content | `grep` | Search for function definitions |
| Explore structure | `list_dir` | Navigate directories |
| Read file content | `read_file` | View specific lines |
| Modify files | `write_file` | Make targeted edits |

## Search Patterns

### Finding Function Definitions

```python
# Python functions
grep(pattern=r"def \w+\(", file_type="py")

# TypeScript/JavaScript functions  
grep(pattern=r"(function|const|let)\s+\w+\s*=?\s*\(", file_type="ts")

# Class definitions
grep(pattern=r"class \w+", file_type="py")
```

### Finding Import Statements

```python
# Python imports
grep(pattern=r"^(from|import)\s+", file_type="py")

# JS/TS imports
grep(pattern=r"^import\s+", file_type="ts")
```

### Finding TODO/FIXME Comments

```python
grep(pattern=r"(TODO|FIXME|HACK|XXX):", context_lines=1)
```

## Navigation Patterns

### Exploring Project Structure

```python
# Get top-level structure
list_dir(depth=1)

# Explore specific directory
list_dir(path="src", depth=2)

# Find specific file types
list_dir(pattern="*.py", depth=3)
```

### Understanding a New Codebase

1. **Start with the root**: `list_dir(depth=1)` to see top-level structure
2. **Check for entry points**: Look for `main.py`, `index.ts`, `app.py`
3. **Find configuration**: Search for `config`, `settings`, `*.yaml`, `*.json`
4. **Locate tests**: `list_dir(path="tests")` or `list_dir(pattern="*test*")`

## Reading Patterns

### Smart File Reading

```python
# Read entire small file
read_file(path="config.yaml")

# Read specific section of large file
read_file(path="main.py", start_line=100, end_line=150)

# Read function definition (after finding line with grep)
read_file(path="utils.py", start_line=45, end_line=60)
```

### Context-Aware Reading

When you find something with `grep`, always read surrounding context:

1. Use `grep` to find the target
2. Note the line number
3. Use `read_file` with `start_line` and `end_line` to get full context

## Editing Patterns

### Safe File Modifications

**Always follow this workflow:**

1. **Read first**: `read_file(path="target.py")` to understand current state
2. **Plan changes**: Identify exact lines to modify
3. **Make precise edits**: Use `write_file` with appropriate mode

### Editing Modes

```python
# Replace entire file (for new files or complete rewrites)
write_file(path="new_file.py", content="...", mode="overwrite")

# Append to file (for adding to end)
write_file(path="log.txt", content="new entry", mode="append")

# Insert at specific line
write_file(path="main.py", content="new_code", mode="insert", start_line=50)

# Replace specific lines
write_file(
    path="main.py",
    content="replacement_code",
    mode="replace_lines",
    start_line=45,
    end_line=50
)
```

## Best Practices

### 1. Search Before You Read

Don't read entire files blindly. Use `grep` to find relevant sections first.

### 2. Minimal Changes

When editing, change only what's necessary. Use `replace_lines` mode for surgical edits.

### 3. Verify After Changes

After making edits, use `read_file` to verify the changes are correct.

### 4. Respect Project Conventions

- Match existing code style
- Preserve indentation
- Follow naming conventions

## Common Workflows

### Bug Investigation

```
1. grep(pattern="error_message") → Find where error occurs
2. read_file(path=found_file, start_line=N-10, end_line=N+10) → Get context
3. grep(pattern="function_name") → Find function definition
4. read_file(...) → Understand the function
5. write_file(..., mode="replace_lines") → Fix the bug
```

### Adding a New Feature

```
1. list_dir(depth=2) → Understand project structure
2. grep(pattern="similar_feature") → Find related code
3. read_file(...) → Study the pattern
4. write_file(..., mode="overwrite") → Create new file
5. read_file(...) → Verify creation
```

### Code Refactoring

```
1. grep(pattern="old_name") → Find all occurrences
2. For each occurrence:
   a. read_file(...) → Get context
   b. write_file(..., mode="replace_lines") → Update
3. grep(pattern="old_name") → Verify no remaining occurrences
```

