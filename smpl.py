import ast
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Tuple

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

VERSION = "0.1.0"

# Token Types
TOKEN_SET = "SET"
TOKEN_ASSIGN = "ASSIGN"
TOKEN_IF = "IF"
TOKEN_OTHERWISE = "OTHERWISE"
TOKEN_TASK = "TASK"
TOKEN_REPEAT = "REPEAT"
TOKEN_WHILE = "WHILE"
TOKEN_THE = "THE"
TOKEN_THEN = "THEN"
TOKEN_SPEAK = "SPEAK"
TOKEN_LISTEN = "LISTEN"
TOKEN_STOP = "STOP"
TOKEN_SHOW = "SHOW"
TOKEN_MEMORY = "MEMORY"
TOKEN_FORGET = "FORGET"
TOKEN_FLUSH = "FLUSH"
TOKEN_SAVE = "SAVE"
TOKEN_LOAD = "LOAD"
TOKEN_RUN = "RUN"
TOKEN_OPEN = "OPEN"
TOKEN_GIVE = "GIVE"
TOKEN_IDENT = "IDENTIFIER"
TOKEN_NUM = "NUMBER"
TOKEN_OP = "OPERATOR"
TOKEN_STR = "STRING"
TOKEN_AND = "AND"
TOKEN_OR = "OR"
TOKEN_NOT = "NOT"

Token = Tuple[str, Any, int]
Statement = Dict[str, Any]

KEYWORDS = {
    "set": TOKEN_SET,
    "if": TOKEN_IF,
    "otherwise": TOKEN_OTHERWISE,
    "task": TOKEN_TASK,
    "repeat": TOKEN_REPEAT,
    "while": TOKEN_WHILE,
    "the": TOKEN_THE,
    "then": TOKEN_THEN,
    "speak": TOKEN_SPEAK,
    "listen": TOKEN_LISTEN,
    "stop": TOKEN_STOP,
    "show": TOKEN_SHOW,
    "memory": TOKEN_MEMORY,
    "forget": TOKEN_FORGET,
    "flush": TOKEN_FLUSH,
    "save": TOKEN_SAVE,
    "load": TOKEN_LOAD,
    "run": TOKEN_RUN,
    "open": TOKEN_OPEN,
    "give": TOKEN_GIVE,
    "and": TOKEN_AND,
    "or": TOKEN_OR,
    "not": TOKEN_NOT,
}

functions: Dict[str, List[Statement]] = {}

ALLOWED_AST_NODES = {
    ast.Expression,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.List,
    ast.Subscript,
    ast.Tuple,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
}


def tokenize(code: str) -> List[Token]:
    code = re.sub(r"#.*", "", code)
    tokens: List[Token] = []

    for line_num, line in enumerate(code.splitlines(), 1):
        raw_tokens = re.findall(r'"[^"]*"|\w+|==|!=|<=|>=|[><=+\-*/(),\[\]]', line)
        for token in raw_tokens:
            lower = token.lower()
            if token.startswith('"') and token.endswith('"'):
                tokens.append((TOKEN_STR, token[1:-1], line_num))
            elif token.isdigit():
                tokens.append((TOKEN_NUM, int(token), line_num))
            elif lower in KEYWORDS:
                tokens.append((KEYWORDS[lower], lower, line_num))
            elif token in {"=", ">", "<", "==", "!=", "+", "-", "*", "/", "(", ")", "<=", ">=", ",", "[", "]"}:
                if token == "=":
                    tokens.append((TOKEN_ASSIGN, token, line_num))
                else:
                    tokens.append((TOKEN_OP, token, line_num))
            else:
                tokens.append((TOKEN_IDENT, token, line_num))

    return tokens


class StopExecution(Exception):
    pass


class ReturnException(Exception):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


def raise_error(message: str, line_num: int) -> None:
    print(f"\n[SMPL Runtime Error] on line {line_num}:")
    print(f"-> {message}")
    sys.exit(1)


def safe_eval(expression: str, line_num: int) -> Any:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise_error("Invalid expression syntax.", line_num)

    for node in ast.walk(tree):
        if type(node) not in ALLOWED_AST_NODES:
            raise_error(f"Expression contains unsupported syntax: {type(node).__name__}", line_num)

    return eval(compile(tree, filename="<smpl>", mode="eval"), {"__builtins__": None}, {})


def expression_to_python(expr_tokens: List[Token], line_num: int, memory_stack: List[Dict[str, Any]]) -> Any:
    expr_text = ""
    for token_type, value, _ in expr_tokens:
        if token_type == TOKEN_STR:
            expr_text += repr(value)
        elif token_type == TOKEN_NUM:
            expr_text += str(value)
        elif token_type == TOKEN_IDENT:
            found = False
            for frame in reversed(memory_stack):
                if value in frame:
                    expr_text += repr(frame[value])
                    found = True
                    break
            if not found:
                raise_error(f"Unknown variable '{value}'.", line_num)
        elif token_type == TOKEN_OP:
            expr_text += value
        elif token_type == TOKEN_AND:
            expr_text += " and "
        elif token_type == TOKEN_OR:
            expr_text += " or "
        elif token_type == TOKEN_NOT:
            expr_text += " not "
        else:
            raise_error(f"Invalid token in expression: {value}", line_num)

    return safe_eval(expr_text, line_num)


def evaluate_task_call(name: str, arg_tokens: List[Token], memory_stack: List[Dict[str, Any]], line_num: int) -> Any:
    if name not in functions:
        raise_error(f"Unknown task '{name}'.", line_num)
    task_def = functions[name]
    expected_args = task_def.get("args", [])
    if len(arg_tokens) != len(expected_args):
        raise_error(f"Task '{name}' expects {len(expected_args)} arguments, got {len(arg_tokens)}.", line_num)
    arg_values = [expression_to_python([token], line_num, memory_stack) if token[0] == TOKEN_IDENT or token[0] == TOKEN_NUM or token[0] == TOKEN_STR else expression_to_python([token], line_num, memory_stack) for token in arg_tokens]
    local_frame: Dict[str, Any] = {}
    for arg_name, arg_value in zip(expected_args, arg_values):
        local_frame[arg_name] = arg_value
    memory_stack.append(local_frame)
    try:
        execute_statements(task_def["body"], memory_stack)
    except ReturnException as ret:
        return ret.value
    finally:
        memory_stack.pop()
    return None


def parse_block(tokens: List[Token], start_index: int, stop_types: Tuple[str, ...], stop_on_blank_line: bool = False) -> Tuple[List[Statement], int]:
    statements: List[Statement] = []
    i = start_index
    prev_line = tokens[start_index - 1][2] if start_index > 0 else 0

    def mark_line() -> None:
        nonlocal prev_line
        if i > 0:
            prev_line = tokens[i - 1][2]
        else:
            prev_line = line_num

    while i < len(tokens):
        token_type, value, line_num = tokens[i]
        if stop_on_blank_line and prev_line and line_num > prev_line + 1:
            break
        if token_type == TOKEN_STOP:
            i += 1
            statements.append({"type": "stop", "line": line_num})
            if stop_types:
                break
            continue
        if token_type in stop_types:
            break

        if token_type == TOKEN_TASK:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected task name after 'task'.", line_num)
            task_name = tokens[i][1]
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_THE:
                i += 1
            args: List[str] = []
            while i < len(tokens) and tokens[i][0] != TOKEN_THEN:
                if tokens[i][0] != TOKEN_IDENT:
                    raise_error("Expected argument name in task signature.", line_num)
                args.append(tokens[i][1])
                i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_THEN:
                raise_error("Expected 'then' after task signature.", line_num)
            i += 1
            body, i = parse_block(tokens, i, (TOKEN_STOP,), stop_on_blank_line=True)
            statements.append({"type": "task", "name": task_name, "args": args, "body": body})
            mark_line()
            continue

        if token_type == TOKEN_IF:
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_THE:
                i += 1
            branches: List[Dict[str, Any]] = []
            cond_tokens: List[Token] = []
            while i < len(tokens) and tokens[i][0] != TOKEN_THEN:
                cond_tokens.append(tokens[i])
                i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_THEN:
                raise_error("Expected 'then' after if condition.", line_num)
            i += 1
            then_body, i = parse_block(tokens, i, (TOKEN_OTHERWISE, TOKEN_STOP), stop_on_blank_line=True)
            branches.append({"condition": cond_tokens, "body": then_body})
            else_body: List[Statement] = []
            while i < len(tokens) and tokens[i][0] == TOKEN_OTHERWISE:
                i += 1
                if i < len(tokens) and tokens[i][0] == TOKEN_THE:
                    i += 1
                if i < len(tokens) and tokens[i][0] == TOKEN_IF:
                    i += 1
                    if i < len(tokens) and tokens[i][0] == TOKEN_THE:
                        i += 1
                    cond_tokens = []
                    while i < len(tokens) and tokens[i][0] != TOKEN_THEN:
                        cond_tokens.append(tokens[i])
                        i += 1
                    if i >= len(tokens) or tokens[i][0] != TOKEN_THEN:
                        raise_error("Expected 'then' after otherwise if condition.", line_num)
                    i += 1
                    then_body, i = parse_block(tokens, i, (TOKEN_OTHERWISE, TOKEN_STOP), stop_on_blank_line=True)
                    branches.append({"condition": cond_tokens, "body": then_body})
                    continue
                if i < len(tokens) and tokens[i][0] == TOKEN_THEN:
                    i += 1
                else:
                    raise_error("Expected 'then' after otherwise.", line_num)
                else_body, i = parse_block(tokens, i, (TOKEN_STOP,), stop_on_blank_line=True)
                break
            statements.append({
                "type": "if",
                "branches": branches,
                "else": else_body,
                "line": line_num,
            })
            mark_line()
            continue

        if token_type == TOKEN_REPEAT:
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_WHILE:
                i += 1
            cond_tokens = []
            while i < len(tokens) and tokens[i][0] != TOKEN_THEN:
                cond_tokens.append(tokens[i])
                i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_THEN:
                raise_error("Expected 'then' after repeat condition.", line_num)
            i += 1
            body, i = parse_block(tokens, i, (TOKEN_STOP,), stop_on_blank_line=True)
            statements.append({"type": "repeat", "condition": cond_tokens, "body": body, "line": line_num})
            mark_line()
            continue

        if token_type == TOKEN_SET:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected variable name after 'set'.", line_num)
            target_name = tokens[i][1]
            target_index: List[Token] = []
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_OP and tokens[i][1] == "[":
                i += 1
                while i < len(tokens) and not (tokens[i][0] == TOKEN_OP and tokens[i][1] == "]"):
                    target_index.append(tokens[i])
                    i += 1
                if i >= len(tokens) or tokens[i][0] != TOKEN_OP or tokens[i][1] != "]":
                    raise_error("Expected closing ']' in indexed assignment.", line_num)
                i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_ASSIGN:
                raise_error("Expected '=' after variable name.", line_num)
            i += 1
            expr_tokens: List[Token] = []
            current_line = line_num
            while i < len(tokens) and tokens[i][2] == current_line:
                expr_tokens.append(tokens[i])
                i += 1
            if expr_tokens and expr_tokens[0][0] == TOKEN_IDENT and all(t[0] in {TOKEN_IDENT, TOKEN_NUM, TOKEN_STR} for t in expr_tokens[1:]) and len(expr_tokens) > 1:
                statements.append({
                    "type": "set_call",
                    "target": target_name,
                    "target_index": target_index or None,
                    "call_name": expr_tokens[0][1],
                    "call_args": expr_tokens[1:],
                    "line": line_num,
                })
            else:
                statements.append({
                    "type": "set",
                    "target": target_name,
                    "target_index": target_index or None,
                    "expr": expr_tokens,
                    "line": line_num,
                })
            mark_line()
            continue

        if token_type == TOKEN_SPEAK:
            i += 1
            expr_tokens: List[Token] = []
            current_line = line_num
            while i < len(tokens) and tokens[i][2] == current_line:
                expr_tokens.append(tokens[i])
                i += 1
            if not expr_tokens:
                raise_error("Expected expression after 'speak'.", line_num)
            if len(expr_tokens) == 1 and expr_tokens[0][0] == TOKEN_STR:
                statements.append({"type": "speak", "value": expr_tokens[0][1], "literal": True})
            else:
                statements.append({"type": "speak", "expr": expr_tokens, "literal": False})
            mark_line()
            continue

        if token_type == TOKEN_LISTEN:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected variable name after 'listen'.", line_num)
            statements.append({"type": "listen", "target": tokens[i][1]})
            i += 1
            mark_line()
            continue

        if token_type == TOKEN_GIVE:
            i += 1
            expr_tokens: List[Token] = []
            current_line = line_num
            while i < len(tokens) and tokens[i][2] == current_line:
                expr_tokens.append(tokens[i])
                i += 1
            if not expr_tokens:
                raise_error("Expected expression after 'give'.", line_num)
            statements.append({"type": "give", "expr": expr_tokens, "line": line_num})
            mark_line()
            continue

        if token_type == TOKEN_RUN or token_type == TOKEN_OPEN:
            keyword = "run" if token_type == TOKEN_RUN else "open"
            i += 1
            if i >= len(tokens):
                raise_error(f"Expected string or variable after '{keyword}'.", line_num)
            if tokens[i][0] == TOKEN_STR:
                statements.append({"type": keyword, "command": tokens[i][1], "literal": True, "line": line_num})
            elif tokens[i][0] == TOKEN_IDENT:
                statements.append({"type": keyword, "command": tokens[i][1], "literal": False, "line": line_num})
            else:
                raise_error(f"'{keyword}' accepts only strings or variable names.", line_num)
            i += 1
            mark_line()
            continue

        if token_type == TOKEN_FORGET:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected variable name after 'forget'.", line_num)
            statements.append({"type": "forget", "target": tokens[i][1], "line": line_num})
            i += 1
            mark_line()
            continue

        if token_type == TOKEN_FLUSH:
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_MEMORY:
                statements.append({"type": "flush_memory", "line": line_num})
                i += 1
            else:
                raise_error("Expected 'memory' after 'flush'.", line_num)
            mark_line()
            continue

        if token_type == TOKEN_SHOW:
            i += 1
            if i < len(tokens) and tokens[i][0] == TOKEN_MEMORY:
                statements.append({"type": "show_memory"})
                i += 1
            else:
                raise_error("Expected 'memory' after 'show'.", line_num)
            mark_line()
            continue

        if token_type == TOKEN_SAVE:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected variable name after 'save'.", line_num)
            statements.append({"type": "save", "target": tokens[i][1], "line": line_num})
            i += 1
            mark_line()
            continue

        if token_type == TOKEN_LOAD:
            i += 1
            if i >= len(tokens) or tokens[i][0] != TOKEN_IDENT:
                raise_error("Expected variable name after 'load'.", line_num)
            statements.append({"type": "load", "target": tokens[i][1], "line": line_num})
            i += 1
            mark_line()
            continue

        if token_type == TOKEN_IDENT:
            call_name = value
            args: List[Token] = []
            j = i + 1
            while j < len(tokens) and tokens[j][2] == line_num and tokens[j][0] in {TOKEN_IDENT, TOKEN_NUM, TOKEN_STR}:
                args.append(tokens[j])
                j += 1
            statements.append({"type": "call", "name": call_name, "args": args, "line": line_num})
            i = j
            mark_line()
            continue

        i += 1

    return statements, i


def execute_statements(statements: List[Statement], memory_stack: List[Dict[str, Any]]) -> None:
    for statement in statements:
        kind = statement["type"]
        line_num = statement.get("line", 0)

        if kind == "task":
            functions[statement["name"]] = {"args": statement.get("args", []), "body": statement["body"]}
            continue

        if kind == "set":
            value = expression_to_python(statement["expr"], line_num, memory_stack)
            if statement.get("target_index") is None:
                for frame in reversed(memory_stack):
                    if statement["target"] in frame:
                        frame[statement["target"]] = value
                        break
                else:
                    memory_stack[-1][statement["target"]] = value
            else:
                target_name = statement["target"]
                index_value = expression_to_python(statement["target_index"], line_num, memory_stack)
                if not isinstance(index_value, int):
                    raise_error("List index must be an integer.", line_num)
                for frame in reversed(memory_stack):
                    if target_name in frame:
                        container = frame[target_name]
                        if not isinstance(container, list):
                            raise_error(f"Target '{target_name}' is not indexable.", line_num)
                        try:
                            container[index_value] = value
                        except Exception as exc:
                            raise_error(str(exc), line_num)
                        break
                else:
                    raise_error(f"Unknown variable '{target_name}'.", line_num)
            continue

        if kind == "set_call":
            result = evaluate_task_call(statement["call_name"], statement["call_args"], memory_stack, line_num)
            target_name = statement["target"]
            if statement.get("target_index") is None:
                for frame in reversed(memory_stack):
                    if target_name in frame:
                        frame[target_name] = result
                        break
                else:
                    memory_stack[-1][target_name] = result
            else:
                index_value = expression_to_python(statement["target_index"], line_num, memory_stack)
                if not isinstance(index_value, int):
                    raise_error("List index must be an integer.", line_num)
                for frame in reversed(memory_stack):
                    if target_name in frame:
                        container = frame[target_name]
                        if not isinstance(container, list):
                            raise_error(f"Target '{target_name}' is not indexable.", line_num)
                        try:
                            container[index_value] = result
                        except Exception as exc:
                            raise_error(str(exc), line_num)
                        break
                else:
                    raise_error(f"Unknown variable '{target_name}'.", line_num)
            continue

        if kind == "speak":
            if statement["literal"]:
                print(statement["value"])
            else:
                value = expression_to_python(statement["expr"], line_num, memory_stack)
                print(value)
            continue

        if kind == "listen":
            user_input = input("> ")
            if user_input.isdigit():
                memory_stack[-1][statement["target"]] = int(user_input)
            else:
                memory_stack[-1][statement["target"]] = user_input
            continue

        if kind == "give":
            value = expression_to_python(statement["expr"], line_num, memory_stack)
            raise ReturnException(value)

        if kind in ("run", "open"):
            if statement["literal"]:
                command = statement["command"]
            else:
                name = statement["command"]
                for frame in reversed(memory_stack):
                    if name in frame:
                        command = frame[name]
                        break
                else:
                    raise_error(f"Unknown variable '{name}'.", line_num)
            if not isinstance(command, str):
                raise_error(f"'{kind}' command must be a string, got {type(command).__name__}.", line_num)
            try:
                if kind == "run":
                    subprocess.Popen(command, shell=True)
                else:
                    if sys.platform == "win32":
                        os.startfile(command)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", command])
                    else:
                        subprocess.Popen(["xdg-open", command])
            except Exception as exc:
                raise_error(f"Failed to {kind} '{command}': {exc}", line_num)
            continue

        if kind == "forget":
            target = statement["target"]
            for frame in reversed(memory_stack):
                if target in frame:
                    del frame[target]
                    break
            else:
                raise_error(f"Cannot forget '{target}'; it does not exist.", line_num)
            continue

        if kind == "flush_memory":
            memory_stack[-1].clear()
            continue

        if kind == "show_memory":
            print("\n--- 🧠 SMPL STACK MEMORY LAYOUT ---")
            for index, frame in enumerate(reversed(memory_stack)):
                scope_name = "LOCAL FRAME" if index != len(memory_stack) - 1 else "GLOBAL FRAME"
                print(f" [{scope_name}]")
                if not frame:
                    print("    (empty)")
                for name, value in frame.items():
                    print(f"    {name} => {value} ({type(value).__name__})")
            print("-----------------------------------")
            continue

        if kind == "save":
            target = statement["target"]
            value = None
            for frame in reversed(memory_stack):
                if target in frame:
                    value = frame[target]
                    break
            if value is None:
                raise_error(f"Cannot save unknown variable '{target}'.", line_num)
            with open("memory.dat", "w", encoding="utf-8") as fh:
                fh.write(str(value))
            continue

        if kind == "load":
            target = statement["target"]
            if not os.path.exists("memory.dat"):
                print(f"No save file found. Setting '{target}' to 0.")
                memory_stack[-1][target] = 0
                continue
            with open("memory.dat", "r", encoding="utf-8") as fh:
                raw_value = fh.read()
            value = int(raw_value) if raw_value.isdigit() else raw_value
            memory_stack[-1][target] = value
            continue

        if kind == "if":
            for branch in statement.get("branches", []):
                condition = expression_to_python(branch["condition"], line_num, memory_stack)
                if condition:
                    execute_statements(branch["body"], memory_stack)
                    break
            else:
                execute_statements(statement.get("else", []), memory_stack)
            continue

        if kind == "repeat":
            while expression_to_python(statement["condition"], line_num, memory_stack):
                execute_statements(statement["body"], memory_stack)
            continue

        if kind == "call":
            task_name = statement["name"]
            _ = evaluate_task_call(task_name, statement.get("args", []), memory_stack, line_num)
            continue

        if kind == "stop":
            raise StopExecution()

        raise_error(f"Unsupported statement type '{kind}'.", line_num)


def collect_tasks(statements: List[Statement]) -> None:
    for statement in statements:
        if statement["type"] == "task":
            functions[statement["name"]] = {"args": statement.get("args", []), "body": statement["body"]}
        elif statement["type"] == "if":
            for branch in statement.get("branches", []):
                collect_tasks(branch["body"])
            collect_tasks(statement.get("else", []))
        elif statement["type"] == "repeat":
            collect_tasks(statement["body"])


def run_smpl(tokens: List[Token], memory_stack: List[Dict[str, Any]] = None) -> None:
    if memory_stack is None:
        memory_stack = [{}]
    functions.clear()
    statements, _ = parse_block(tokens, 0, ())
    collect_tasks(statements)
    try:
        execute_statements(statements, memory_stack)
    except StopExecution:
        return


def print_help() -> None:
    print("SMPL interpreter")
    print("Usage: smpl [--run script.smpl] [script.smpl] [--help] [--version]")
    print("       smpl.bat [--run script.smpl] ...      (Windows)")
    print("       ./smpl [--run script.smpl] ...        (Linux/macOS)")
    print()
    print("Options:")
    print("  --run <script.smpl>   Execute a specified SMPL script")
    print("  -r, --run             Alias for --run")
    print("  --help                Show this help message")
    print("  -h                    Show this help message")
    print("  --version             Print the SMPL version")
    print("  -v                    Print the SMPL version")
    print()
    print("If no script is provided, this help text is shown.")


def main() -> None:
    if len(sys.argv) == 1:
        print_help()
        return

    arg = sys.argv[1]
    if arg in ("-h", "--help"):
        print_help()
        return
    if arg in ("-v", "--version"):
        print(VERSION)
        return

    if arg in ("-r", "--run"):
        if len(sys.argv) < 3:
            print("Error: --run requires a script file.")
            print_help()
            sys.exit(1)
        path = sys.argv[2]
    else:
        path = arg

    if not os.path.exists(path):
        print(f"Error: Could not find '{path}'!")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as file:
        source = file.read()

    run_smpl(tokenize(source))


if __name__ == "__main__":
    main()
