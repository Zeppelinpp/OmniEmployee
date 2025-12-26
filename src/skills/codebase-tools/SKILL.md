---
name: codebase-tools
description: Advanced codebase exploration and manipulation toolkit for searching code, navigating project structure, and making precise file edits.
---

# Codebase Tools Guide

## Overview

This skill provides a standard operating procedure (SOP) for exploring, analyzing, and modifying codebases. It guides the agent through efficient code search, navigation, and precise file modifications.

## Standard Operating Procedure

### Step 1: Explore Project Structure

Before making any changes, understand the project layout:

```python
list_dir(path=".", depth=2)
```

This helps establish:
- Project organization and folder structure
- Location of source code, tests, and configuration
- Key entry points (main.py, index.ts, etc.)

### Step 2: Search for Relevant Code

Use `grep` to find specific code patterns. If searching for a function, class, or variable:

```python
# Find function definitions
grep(pattern=r"def function_name\(", file_type="py")

# Find class definitions
grep(pattern=r"class ClassName", file_type="py")

# Find all usages of a variable
grep(pattern=r"\bvariable_name\b", file_type="py", context_lines=2)
```

**Important**: Always use appropriate filters:
- Specify `file_type` to avoid searching irrelevant files
- Use `context_lines` to understand surrounding code
- Use word boundaries (`\b`) for precise matching

### Step 3: Read and Understand Context

Once you've located relevant code, read the full context:

```python
# Read entire small file
read_file(path="src/module.py")

# Read specific section of large file
read_file(path="src/large_file.py", start_line=100, end_line=150)
```

**Important**: Always read before writing:
- Understand the current implementation
- Identify dependencies and side effects
- Note the code style and conventions

### Step 4: Plan Modifications

Before making changes:
1. Identify ALL locations that need modification
2. Determine the safest modification approach
3. Plan verification steps

| Modification Type | Approach |
|-------------------|----------|
| Single line change | `write_file` with `mode="replace_lines"` |
| Add new code | `write_file` with `mode="insert"` |
| Append to file | `write_file` with `mode="append"` |
| Replace entire file | `write_file` with `mode="overwrite"` |

### Step 5: Execute Changes

Apply changes incrementally:

```python
# Replace specific lines
write_file(
    path="src/module.py",
    content="new_code_here",
    mode="replace_lines",
    start_line=45,
    end_line=50
)

# Insert at specific line
write_file(
    path="src/module.py",
    content="new_import_statement",
    mode="insert",
    start_line=5
)
```

### Step 6: Verify Results

After each change, verify correctness:

```python
# Confirm changes were applied
read_file(path="src/module.py", start_line=40, end_line=55)

# Verify no remaining old code
grep(pattern="old_function_name", file_type="py")

# Check for syntax errors (if applicable)
run_command(command="python -m py_compile src/module.py")
```

## Quick Reference

| Task | Tool | Usage |
|------|------|-------|
| Explore structure | `list_dir` | `list_dir(path="src", depth=2)` |
| Search code | `grep` | `grep(pattern="def func", file_type="py")` |
| Read file | `read_file` | `read_file(path="file.py")` |
| Modify file | `write_file` | `write_file(path, content, mode)` |
| Run command | `run_command` | `run_command(command="pytest")` |

## Error Handling

**IMPORTANT**: When you encounter errors (e.g., "File not found", "Permission denied", "Pattern not found"), you MUST load the reference document for detailed solutions:

```
load_skill_reference("codebase-tools", "reference.md")
```

The reference document contains:
- **Tool Parameters** - Complete parameter documentation for all tools
- **Error Solutions** - Step-by-step solutions for common issues
- **Advanced Patterns** - Complex search strategies and multi-file analysis

## Additional Resources

For detailed information on tool parameters, advanced search techniques, and error handling, load [reference.md](./reference.md) using `load_skill_reference`.

Contents include:
- **Tool Reference** - Complete parameter documentation for `grep`, `list_dir`, `read_file`, `write_file`
- **Advanced Search Patterns** - Language-specific regex patterns (Python, TypeScript, Go)
- **Complex Search Strategies** - Finding dead code, security issues, performance problems
- **Multi-File Analysis** - Dependency analysis, call graph construction
- **Error Handling** - File not found, permission errors, syntax errors, rollback strategies
- **Best Practices** - Minimal changes, verification workflows, code style preservation
