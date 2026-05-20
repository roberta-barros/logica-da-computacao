import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r})"


@dataclass
class Variable:
    value: Any
    type: Optional[str]  # "number", "string", "boolean", or None (void function)
    is_function: bool = False
    mutable: bool = True


class ReturnValue:
    """Sentinel that propagates a return through nested blocks up to the call site."""

    def __init__(self, value: Any, type_: Optional[str]):
        self.value = value
        self.type = type_


class SymbolTable:
    """Reverse-linked-list of scopes. The root has parent=None."""

    def __init__(self, parent: Optional["SymbolTable"] = None):
        self._table: dict[str, Variable] = {}
        self._parent = parent

    @property
    def parent(self) -> Optional["SymbolTable"]:
        return self._parent

    def get_variable(self, name: str) -> Variable:
        """Walks the scope chain to locate the Variable. Raises if not found."""
        if name in self._table:
            return self._table[name]
        if self._parent is not None:
            return self._parent.get_variable(name)
        raise ValueError(f"[Semantic] Variable '{name}' does not exist")

    def get(self, name: str) -> tuple[Any, Optional[str]]:
        var = self.get_variable(name)
        return (var.value, var.type)

    def set(self, name: str, value: Any, value_type: Optional[str]) -> None:
        """Assigns to an existing variable in the nearest scope where it lives."""
        if name in self._table:
            variable = self._table[name]
            if variable.is_function:
                raise ValueError(f"[Semantic] '{name}' is a function and cannot be reassigned")
            if not variable.mutable:
                raise ValueError(f"[Semantic] Cannot change the value of '{name}'")
            if (
                variable.type is not None
                and value_type is not None
                and variable.type != value_type
            ):
                raise ValueError(
                    f"[Semantic] Cannot assign {value_type} value to {variable.type} variable '{name}'"
                )
            variable.value = value
            return

        if self._parent is not None:
            self._parent.set(name, value, value_type)
            return

        raise ValueError(f"[Semantic] Variable '{name}' does not exist")

    def create_variable(
        self,
        name: str,
        value: Any,
        type_: Optional[str],
        is_function: bool = False,
        mutable: bool = True,
    ) -> None:
        """Declares a new variable in the CURRENT scope. Re-declaration in the same scope is an error."""
        if name in self._table:
            raise ValueError(
                f"[Semantic] Variable '{name}' is already declared in this scope"
            )
        self._table[name] = Variable(
            value=value, type=type_, is_function=is_function, mutable=mutable
        )


class PrePro:
    RESERVED_WORDS = {
        "print", "const", "imut", "if", "then", "else", "while", "do", "end",
        "and", "or", "not", "read", "for",
        "function", "return", "local", "number", "string", "boolean", "true", "false",
    }
    IDENTIFIER_RE = r"[A-Za-z][A-Za-z0-9_]*"

    @staticmethod
    def filter(code: str) -> str:
        """Strips line comments and resolves `const NAME VALUE` declarations."""
        code_without_comments = re.sub(r"--[^\n]*", "", code)

        constants: dict[str, str] = {}
        out_lines: list[str] = []

        for raw_line in code_without_comments.splitlines(keepends=True):
            has_newline = raw_line.endswith("\n")
            line = raw_line[:-1] if has_newline else raw_line
            stripped = line.strip()

            if not stripped:
                out_lines.append(raw_line)
                continue

            if re.match(r"^const\b", stripped):
                match = re.fullmatch(
                    rf"const\s+({PrePro.IDENTIFIER_RE})\s+([+-]?\d+)\s*",
                    stripped,
                )
                if match is None:
                    raise ValueError("[PrePro] Invalid constant declaration. Use: const NAME VALUE")

                name, value = match.group(1), match.group(2)
                if name in PrePro.RESERVED_WORDS:
                    raise ValueError(
                        f"[PrePro] Reserved word '{name}' cannot be used as a constant"
                    )
                if name in constants:
                    raise ValueError(f"[PrePro] Constant '{name}' already exists")

                constants[name] = value
                out_lines.append("\n" if has_newline else "")
                continue

            out_lines.append(raw_line)

        filtered_code = "".join(out_lines)

        for name, value in constants.items():
            filtered_code = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                value,
                filtered_code,
            )

        return filtered_code


# =====================================================================================
#                                       AST
# =====================================================================================


class Node(ABC):
    def __init__(self, value, children=None):
        self.value = value
        self.children = children if children is not None else []

    @abstractmethod
    def evaluate(self, st: SymbolTable):
        pass


def _eval_expr(node: Node, st: SymbolTable) -> tuple[Any, Optional[str]]:
    """Evaluates an expression and guarantees a (value, type) tuple is produced."""
    result = node.evaluate(st)
    if result is None:
        raise ValueError("[Semantic] Expected a value, got void (e.g. void function call in expression position)")
    if isinstance(result, ReturnValue):
        # Should not happen at expression evaluation, but guard anyway.
        return (result.value, result.type)
    return result


class IntVal(Node):
    def evaluate(self, st):
        return (self.value, "number")


class StringVal(Node):
    def evaluate(self, st):
        return (self.value, "string")


class BoolVal(Node):
    def evaluate(self, st):
        return (1 if self.value else 0, "boolean")


class Identifier(Node):
    def evaluate(self, st):
        return st.get(self.value)


class UnOp(Node):
    def evaluate(self, st):
        child_val, child_type = _eval_expr(self.children[0], st)
        op = self.value

        if op == "+":
            if child_type != "number":
                raise ValueError(f"[Semantic] Unary '+' requires number, got {child_type}")
            return (+child_val, "number")
        if op == "-":
            if child_type != "number":
                raise ValueError(f"[Semantic] Unary '-' requires number, got {child_type}")
            return (-child_val, "number")
        if op == "not":
            return (1 if child_val == 0 else 0, "boolean")
        if op == "!":
            if child_type != "number":
                raise ValueError(f"[Semantic] Factorial requires number, got {child_type}")
            if child_val < 0:
                raise ValueError("[Semantic] Factorial of negative number")
            result = 1
            for i in range(1, child_val + 1):
                result *= i
            return (result, "number")

        raise ValueError(f"[Semantic] Unknown unary operator '{op}'")


class BinOp(Node):
    def evaluate(self, st):
        left_val, left_type = _eval_expr(self.children[0], st)
        right_val, right_type = _eval_expr(self.children[1], st)
        op = self.value

        if op in ("+", "-", "*", "/"):
            if left_type != "number" or right_type != "number":
                raise ValueError(
                    f"[Semantic] '{op}' requires number operands, got {left_type} and {right_type}"
                )
            if op == "+":
                return (left_val + right_val, "number")
            if op == "-":
                return (left_val - right_val, "number")
            if op == "*":
                return (left_val * right_val, "number")
            if right_val == 0:
                raise ValueError("[Semantic] Division by zero")
            return (int(left_val / right_val), "number")

        if op in ("==", ">", "<"):
            if left_type != right_type:
                raise ValueError(f"[Semantic] Cannot compare {left_type} with {right_type}")
            if op == "==":
                return (1 if left_val == right_val else 0, "boolean")
            if op == ">":
                return (1 if left_val > right_val else 0, "boolean")
            return (1 if left_val < right_val else 0, "boolean")

        if op == "and":
            return (1 if (left_val != 0) and (right_val != 0) else 0, "boolean")
        if op == "or":
            return (1 if (left_val != 0) or (right_val != 0) else 0, "boolean")

        raise ValueError(f"[Semantic] Unknown binary operator '{op}'")


class ConditionalExpression(Node):
    """Extra credit: ternary expression `if cond then expr else expr end`."""

    def evaluate(self, st):
        cond_val, _ = _eval_expr(self.children[0], st)
        if cond_val != 0:
            return _eval_expr(self.children[1], st)
        return _eval_expr(self.children[2], st)


class VarDec(Node):
    """Local variable declaration.

    `value`     -> variable name
    `var_type`  -> declared type ('number', 'string', or 'boolean')
    `children`  -> [] for `local name type`; [expr] for `local name type = expr`
    """

    def __init__(self, value, children=None, var_type: Optional[str] = None):
        super().__init__(value, children)
        self.var_type = var_type

    def evaluate(self, st):
        if self.children:
            val, val_type = _eval_expr(self.children[0], st)
            if (
                self.var_type is not None
                and val_type is not None
                and val_type != self.var_type
            ):
                raise ValueError(
                    f"[Semantic] Cannot initialize {self.var_type} variable '{self.value}' with {val_type} value"
                )
            st.create_variable(self.value, val, self.var_type, is_function=False)
        else:
            default: Any = 0
            if self.var_type == "string":
                default = ""
            st.create_variable(self.value, default, self.var_type, is_function=False)
        return None


class Assignment(Node):
    """Assigns to an EXISTING variable (declared earlier with `local`)."""

    def evaluate(self, st):
        name = self.children[0].value
        val, val_type = _eval_expr(self.children[1], st)
        st.set(name, val, val_type)
        return None


class ImmutableAssignment(Node):
    """Extra: `imut NAME = EXPR` creates an immutable variable in the current scope."""

    def evaluate(self, st):
        name = self.children[0].value
        val, val_type = _eval_expr(self.children[1], st)
        st.create_variable(name, val, val_type, mutable=False)
        return None


class Print(Node):
    def evaluate(self, st):
        val, _ = _eval_expr(self.children[0], st)
        print(val)
        return None


class Read(Node):
    def evaluate(self, st):
        try:
            return (int(input()), "number")
        except EOFError as exc:
            raise ValueError("[Semantic] Expected integer input for read()") from exc
        except ValueError as exc:
            raise ValueError("[Semantic] read() expects an integer") from exc


class Return(Node):
    def evaluate(self, st):
        val, val_type = _eval_expr(self.children[0], st)
        return ReturnValue(val, val_type)


class If(Node):
    def evaluate(self, st):
        cond_val, _ = _eval_expr(self.children[0], st)
        chosen_block: Optional[Node] = None
        if cond_val != 0:
            chosen_block = self.children[1]
        elif len(self.children) == 3:
            chosen_block = self.children[2]

        if chosen_block is None:
            return None

        result = chosen_block.evaluate(st)
        if isinstance(result, ReturnValue):
            return result
        return None


class While(Node):
    def evaluate(self, st):
        while True:
            cond_val, _ = _eval_expr(self.children[0], st)
            if cond_val == 0:
                break
            result = self.children[1].evaluate(st)
            if isinstance(result, ReturnValue):
                return result
        return None


class For(Node):
    """Extra credit: inclusive `for i = start, end do ... end`.

    Each iteration runs inside a fresh sub-scope so the loop variable
    is local and any `local` declarations inside the body don't collide
    across iterations.
    """

    def evaluate(self, st):
        name = self.children[0].value
        start_val, _ = _eval_expr(self.children[1], st)
        end_val, _ = _eval_expr(self.children[2], st)
        body = self.children[3]

        current = start_val
        while current <= end_val:
            iter_st = SymbolTable(parent=st)
            iter_st.create_variable(name, current, "number")
            result = body.evaluate(iter_st)
            if isinstance(result, ReturnValue):
                return result
            current += 1

        return None


class Block(Node):
    def evaluate(self, st):
        for child in self.children:
            # A Block-as-child receives its own chained scope (do/end semantics).
            if isinstance(child, Block):
                child_st = SymbolTable(parent=st)
                result = child.evaluate(child_st)
            else:
                result = child.evaluate(st)

            if isinstance(result, ReturnValue):
                return result
        return None


class NoOp(Node):
    def evaluate(self, st):
        return None


class FuncDec(Node):
    """Function declaration.

    `value`               -> return type ('number', 'string', 'boolean', or None for void)
    `children[0]`         -> Identifier (function name)
    `children[1 .. n]`    -> one VarDec per parameter (in order)
    `children[-1]`        -> Block (function body)
    """

    def evaluate(self, st):
        # Always register the function in the outermost (global) scope.
        root_st = st
        while root_st.parent is not None:
            root_st = root_st.parent

        name = self.children[0].value
        root_st.create_variable(
            name=name,
            value=self,
            type_=self.value,
            is_function=True,
        )
        return None


class FuncCall(Node):
    """Function call. Works both as a statement and as an expression.

    `value`     -> function name
    `children`  -> argument expressions, in order
    """

    def evaluate(self, st):
        name = self.value

        try:
            variable = st.get_variable(name)
        except ValueError:
            raise ValueError(f"[Semantic] Function '{name}' is not declared")

        if not variable.is_function:
            raise ValueError(f"[Semantic] '{name}' is not a function")

        func_dec: FuncDec = variable.value
        params: list[VarDec] = func_dec.children[1:-1]
        body: Block = func_dec.children[-1]
        return_type: Optional[str] = func_dec.value

        if len(self.children) != len(params):
            raise ValueError(
                f"[Semantic] Function '{name}' expects {len(params)} argument(s), got {len(self.children)}"
            )

        # Evaluate arguments in the CALLER's scope, type-check, then bind them in a new scope.
        evaluated_args: list[tuple[Any, Optional[str]]] = []
        for i, arg_node in enumerate(self.children):
            arg_val, arg_type = _eval_expr(arg_node, st)
            expected_type = params[i].var_type
            if (
                arg_type is not None
                and expected_type is not None
                and arg_type != expected_type
            ):
                raise ValueError(
                    f"[Semantic] Argument {i + 1} of '{name}': expected {expected_type}, got {arg_type}"
                )
            evaluated_args.append((arg_val, expected_type if expected_type else arg_type))

        # Functions only see global variables; chain the new scope to root, not to caller.
        root_st = st
        while root_st.parent is not None:
            root_st = root_st.parent

        new_st = SymbolTable(parent=root_st)

        for param, (val, _) in zip(params, evaluated_args):
            new_st.create_variable(param.value, val, param.var_type, is_function=False)

        result = body.evaluate(new_st)

        if isinstance(result, ReturnValue):
            if return_type is None:
                raise ValueError(
                    f"[Semantic] Function '{name}' is void but a value was returned"
                )
            if result.type is not None and result.type != return_type:
                raise ValueError(
                    f"[Semantic] Function '{name}' must return {return_type}, returned {result.type}"
                )
            return (result.value, return_type)

        # No return statement reached.
        if return_type is not None:
            raise ValueError(
                f"[Semantic] Function '{name}' must return a {return_type} value"
            )
        return None


# =====================================================================================
#                                      LEXER
# =====================================================================================


class Lexer:
    RESERVED_WORDS = {
        "print": "PRINT",
        "imut": "IMUT",
        "const": "CONST",
        "if": "IF",
        "then": "OPEN_IF_BRA",
        "else": "ELSE",
        "while": "WHILE",
        "do": "OPEN_BRA",
        "end": "CLOSE_BRA",
        "and": "AND",
        "or": "OR",
        "not": "NOT",
        "read": "READ",
        "for": "FOR",
        "function": "FUNC",
        "return": "RETURN",
        "local": "LOCAL",
        "number": "TYPE",
        "string": "TYPE",
        "boolean": "TYPE",
        "true": "BOOL",
        "false": "BOOL",
    }

    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    @staticmethod
    def is_letter(ch: str) -> bool:
        return ch.isascii() and ch.isalpha()

    @staticmethod
    def is_identifier_char(ch: str) -> bool:
        return ch.isascii() and (ch.isalnum() or ch == "_")

    def select_next(self) -> None:
        s = self.source

        # Skip horizontal whitespace; newlines are significant tokens.
        while self.position < len(s) and s[self.position] in " \t\r":
            self.position += 1

        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        if ch == "\n":
            self.position += 1
            self.next = Token("END", "\n")
            return
        if ch == "=" and self.position + 1 < len(s) and s[self.position + 1] == "=":
            self.position += 2
            self.next = Token("EQ", "==")
            return
        if ch == "=":
            self.position += 1
            self.next = Token("ASSIGN", "=")
            return
        if ch == ">":
            self.position += 1
            self.next = Token("GT", ">")
            return
        if ch == "<":
            self.position += 1
            self.next = Token("LT", "<")
            return
        if ch == ",":
            self.position += 1
            self.next = Token("COMMA", ",")
            return
        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return
        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return
        if ch == "*":
            self.position += 1
            self.next = Token("MULT", "*")
            return
        if ch == "/":
            self.position += 1
            self.next = Token("DIV", "/")
            return
        if ch == "(":
            self.position += 1
            self.next = Token("OPEN_PAR", "(")
            return
        if ch == ")":
            self.position += 1
            self.next = Token("CLOSE_PAR", ")")
            return
        if ch == "!":
            self.position += 1
            self.next = Token("FACT", "!")
            return

        if ch == '"':
            self.position += 1
            literal = ""
            while self.position < len(s) and s[self.position] != '"':
                if s[self.position] == "\n":
                    raise ValueError("[Lexer] Unterminated string literal")
                literal += s[self.position]
                self.position += 1
            if self.position >= len(s):
                raise ValueError("[Lexer] Unterminated string literal")
            self.position += 1  # consume closing quote
            self.next = Token("STRING", literal)
            return

        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

        if Lexer.is_letter(ch):
            identifier = ""
            while self.position < len(s) and Lexer.is_identifier_char(s[self.position]):
                identifier += s[self.position]
                self.position += 1

            token_type = Lexer.RESERVED_WORDS.get(identifier, "IDEN")
            if token_type == "BOOL":
                self.next = Token(token_type, identifier == "true")
            else:
                self.next = Token(token_type, identifier)
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


# =====================================================================================
#                                      PARSER
# =====================================================================================


class Parser:
    lexer: Optional[Lexer] = None

    @staticmethod
    def expect(token_type: str) -> Token:
        if Parser.lexer.next.type != token_type:
            raise ValueError(
                f"[Parser] Expected {token_type}, got {Parser.lexer.next.type}"
            )
        tok = Parser.lexer.next
        Parser.lexer.select_next()
        return tok

    @staticmethod
    def skip_end_lines() -> None:
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()

    # ----- expression layer ----------------------------------------------------------

    @staticmethod
    def parse_primary() -> Node:
        tok = Parser.lexer.next

        if tok.type == "INT":
            Parser.lexer.select_next()
            return IntVal(tok.value)

        if tok.type == "STRING":
            Parser.lexer.select_next()
            return StringVal(tok.value)

        if tok.type == "BOOL":
            Parser.lexer.select_next()
            return BoolVal(tok.value)

        if tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "OPEN_PAR":
                # function call as factor
                Parser.lexer.select_next()
                args: list[Node] = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                Parser.expect("CLOSE_PAR")
                return FuncCall(name, args)
            return Identifier(name)

        if tok.type == "READ":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            Parser.expect("CLOSE_PAR")
            return Read("read")

        if tok.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
            return node

        if tok.type == "IF":
            # Extra credit: ternary `if cond then expr else expr end`
            Parser.lexer.select_next()
            condition = Parser.parse_bool_expression()
            Parser.expect("OPEN_IF_BRA")
            true_expression = Parser.parse_bool_expression()
            Parser.expect("ELSE")
            false_expression = Parser.parse_bool_expression()
            Parser.expect("CLOSE_BRA")
            return ConditionalExpression(
                "if_expression", [condition, true_expression, false_expression]
            )

        raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

    @staticmethod
    def parse_atom() -> Node:
        node = Parser.parse_primary()
        while Parser.lexer.next.type == "FACT":
            Parser.lexer.select_next()
            node = UnOp("!", [node])
        return node

    @staticmethod
    def parse_factor() -> Node:
        if Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            child = Parser.parse_factor()
            return UnOp(op, [child])

        if Parser.lexer.next.type == "NOT":
            Parser.lexer.select_next()
            child = Parser.parse_factor()
            return UnOp("not", [child])

        return Parser.parse_atom()

    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_factor()
            result = BinOp(op, [result, right])
        return result

    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_term()
            result = BinOp(op, [result, right])
        return result

    @staticmethod
    def parse_rel_expression() -> Node:
        result = Parser.parse_expression()
        while Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            right = Parser.parse_expression()
            result = BinOp(op, [result, right])
        return result

    @staticmethod
    def parse_bool_term() -> Node:
        result = Parser.parse_rel_expression()
        while Parser.lexer.next.type == "AND":
            Parser.lexer.select_next()
            right = Parser.parse_rel_expression()
            result = BinOp("and", [result, right])
        return result

    @staticmethod
    def parse_bool_expression() -> Node:
        result = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            Parser.lexer.select_next()
            right = Parser.parse_bool_term()
            result = BinOp("or", [result, right])
        return result

    # ----- function machinery --------------------------------------------------------

    @staticmethod
    def parse_param() -> VarDec:
        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected parameter name, got {Parser.lexer.next.type}"
            )
        name = Parser.lexer.next.value
        Parser.lexer.select_next()
        if Parser.lexer.next.type != "TYPE":
            raise ValueError(
                f"[Parser] Expected type after parameter '{name}', got {Parser.lexer.next.type}"
            )
        param_type = Parser.lexer.next.value
        Parser.lexer.select_next()
        return VarDec(name, [], var_type=param_type)

    @staticmethod
    def parse_func_declaration() -> Node:
        Parser.expect("FUNC")

        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected function name, got {Parser.lexer.next.type}"
            )
        name_node = Identifier(Parser.lexer.next.value)
        Parser.lexer.select_next()

        Parser.expect("OPEN_PAR")

        params: list[VarDec] = []
        if Parser.lexer.next.type != "CLOSE_PAR":
            params.append(Parser.parse_param())
            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                params.append(Parser.parse_param())

        Parser.expect("CLOSE_PAR")

        return_type: Optional[str] = None
        if Parser.lexer.next.type == "TYPE":
            return_type = Parser.lexer.next.value
            Parser.lexer.select_next()

        if Parser.lexer.next.type != "END":
            raise ValueError(
                f"[Parser] Expected newline after function signature, got {Parser.lexer.next.type}"
            )
        Parser.skip_end_lines()

        body = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
        Parser.expect("CLOSE_BRA")

        return FuncDec(return_type, [name_node] + params + [body])

    # ----- statements ----------------------------------------------------------------

    @staticmethod
    def parse_statement() -> Node:
        tok = Parser.lexer.next

        if tok.type == "LOCAL":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected identifier after 'local', got {Parser.lexer.next.type}"
                )
            var_name = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise ValueError(
                    f"[Parser] Expected type after 'local {var_name}', got {Parser.lexer.next.type}"
                )
            var_type = Parser.lexer.next.value
            Parser.lexer.select_next()

            children: list[Node] = []
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                children.append(Parser.parse_bool_expression())

            return VarDec(var_name, children, var_type=var_type)

        if tok.type == "IDEN":
            name = tok.value
            Parser.lexer.select_next()

            if Parser.lexer.next.type == "OPEN_PAR":
                # function call as a standalone statement
                Parser.lexer.select_next()
                args: list[Node] = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                Parser.expect("CLOSE_PAR")
                return FuncCall(name, args)

            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                expression = Parser.parse_bool_expression()
                return Assignment("=", [Identifier(name), expression])

            raise ValueError(
                f"[Parser] Unexpected token {Parser.lexer.next.type} after identifier '{name}'"
            )

        if tok.type == "PRINT":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            expression = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
            return Print("print", [expression])

        if tok.type == "RETURN":
            Parser.lexer.select_next()
            expression = Parser.parse_bool_expression()
            return Return("return", [expression])

        if tok.type == "IMUT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected identifier after 'imut', got {Parser.lexer.next.type}"
                )
            identifier = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            Parser.expect("ASSIGN")
            expression = Parser.parse_bool_expression()
            return ImmutableAssignment("imut", [identifier, expression])

        if tok.type == "IF":
            Parser.lexer.select_next()
            condition = Parser.parse_bool_expression()
            Parser.expect("OPEN_IF_BRA")
            Parser.skip_end_lines()
            true_block = Parser.parse_block(stop_tokens={"ELSE", "CLOSE_BRA"})

            children = [condition, true_block]
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                Parser.skip_end_lines()
                false_block = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
                children.append(false_block)

            Parser.expect("CLOSE_BRA")
            return If("if", children)

        if tok.type == "WHILE":
            Parser.lexer.select_next()
            condition = Parser.parse_bool_expression()
            Parser.expect("OPEN_BRA")
            Parser.skip_end_lines()
            body = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
            Parser.expect("CLOSE_BRA")
            return While("while", [condition, body])

        if tok.type == "FOR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected identifier after 'for', got {Parser.lexer.next.type}"
                )
            identifier = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            Parser.expect("ASSIGN")
            start_expression = Parser.parse_bool_expression()
            Parser.expect("COMMA")
            end_expression = Parser.parse_bool_expression()
            Parser.expect("OPEN_BRA")
            Parser.skip_end_lines()
            body = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
            Parser.expect("CLOSE_BRA")
            return For("for", [identifier, start_expression, end_expression, body])

        if tok.type == "OPEN_BRA":  # standalone `do ... end`
            Parser.lexer.select_next()
            Parser.skip_end_lines()
            body = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
            Parser.expect("CLOSE_BRA")
            return body  # already a Block node

        if tok.type == "CONST":
            raise ValueError("[Parser] Constants must be declared as: const NAME VALUE")

        raise ValueError(
            f"[Parser] Unexpected token {tok.type} at start of statement"
        )

    @staticmethod
    def parse_block(stop_tokens=None) -> Block:
        if stop_tokens is None:
            stop_tokens = {"EOF"}

        children: list[Node] = []

        while (
            Parser.lexer.next.type not in stop_tokens
            and Parser.lexer.next.type != "EOF"
        ):
            if Parser.lexer.next.type == "END":
                Parser.lexer.select_next()
                continue

            children.append(Parser.parse_statement())

            if Parser.lexer.next.type == "END":
                Parser.skip_end_lines()
            elif (
                Parser.lexer.next.type not in stop_tokens
                and Parser.lexer.next.type != "EOF"
            ):
                raise ValueError(
                    f"[Parser] Expected end of line, got {Parser.lexer.next.type}"
                )

        return Block(None, children)

    @staticmethod
    def parse_program() -> Block:
        """PROGRAM = { FUNCDEC | STATEMENT } ;"""
        children: list[Node] = []
        Parser.skip_end_lines()

        while Parser.lexer.next.type != "EOF":
            if Parser.lexer.next.type == "FUNC":
                children.append(Parser.parse_func_declaration())
            else:
                children.append(Parser.parse_statement())

            if Parser.lexer.next.type == "END":
                Parser.skip_end_lines()
            elif Parser.lexer.next.type != "EOF":
                raise ValueError(
                    f"[Parser] Expected newline or EOF after top-level item, got {Parser.lexer.next.type}"
                )

        return Block(None, children)

    @staticmethod
    def run(code: str) -> Block:
        filtered_code = PrePro.filter(code)
        Parser.lexer = Lexer(filtered_code)
        Parser.lexer.select_next()
        return Parser.parse_program()


# =====================================================================================
#                                       MAIN
# =====================================================================================


def read_source_code() -> str:
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as file:
            return file.read() + "\n"
    return sys.stdin.read() + "\n"


def main():
    code = read_source_code()
    try:
        tree = Parser.run(code)
        st = SymbolTable()
        tree.evaluate(st)
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()