import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r})"


@dataclass
class Variable:
    value: int
    mutable: bool = True


class SymbolTable:
    def __init__(self):
        self._table: dict[str, Variable] = {}

    @property
    def table(self) -> dict[str, Variable]:
        return self._table

    @table.setter
    def table(self, value: dict[str, Variable]) -> None:
        self._table = value

    def get(self, name: str) -> int:
        if name not in self._table:
            raise ValueError(f"[Semantic] Variable '{name}' does not exist")
        return self._table[name].value

    def set(self, name: str, value: int) -> None:
        if name in self._table:
            variable = self._table[name]
            if not variable.mutable:
                raise ValueError(f"[Semantic] Cannot change the value of {name}")
            variable.value = value
            return

        self._table[name] = Variable(value=value, mutable=True)

    def declare_immutable(self, name: str, value: int) -> None:
        if name in self._table:
            raise ValueError(f"[Semantic] Variable '{name}' already exists")
        self._table[name] = Variable(value=value, mutable=False)


class PrePro:
    RESERVED_WORDS = {
        "print",
        "const",
        "imut",
        "if",
        "then",
        "else",
        "while",
        "do",
        "end",
        "and",
        "or",
        "not",
        "read",
        "for",
    }
    IDENTIFIER_RE = r"[A-Za-z][A-Za-z0-9_]*"

    @staticmethod
    def filter(code: str) -> str:
        """
        Removes inline comments and resolves constants before lexical analysis.

        Constant syntax:
            const NAME VALUE

        Example:
            const N 1
            print(N)

        After preprocessing, this becomes:
            print(1)
        """
        # Remove inline comments, preserving line breaks.
        code_without_comments = re.sub(r"--[^\n]*", "", code)

        constants: dict[str, str] = {}
        lines_without_const_declarations: list[str] = []

        for raw_line in code_without_comments.splitlines(keepends=True):
            has_newline = raw_line.endswith("\n")
            line = raw_line[:-1] if has_newline else raw_line
            stripped = line.strip()

            if not stripped:
                lines_without_const_declarations.append(raw_line)
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
                    raise ValueError(f"[PrePro] Reserved word '{name}' cannot be used as a constant")
                if name in constants:
                    raise ValueError(f"[PrePro] Constant '{name}' already exists")

                constants[name] = value
                # Remove the constant declaration from the code, but keep the line advance.
                lines_without_const_declarations.append("\n" if has_newline else "")
                continue

            lines_without_const_declarations.append(raw_line)

        filtered_code = "".join(lines_without_const_declarations)

        # Replace constants only when they appear as full identifiers.
        for name, value in constants.items():
            filtered_code = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                value,
                filtered_code,
            )

        return filtered_code


class Node(ABC):
    def __init__(self, value, children=None):
        self.value = value
        self.children = children if children is not None else []

    @abstractmethod
    def evaluate(self, st: SymbolTable):
        pass


class IntVal(Node):
    def evaluate(self, st: SymbolTable) -> int:
        return self.value


class Identifier(Node):
    def evaluate(self, st: SymbolTable) -> int:
        return st.get(self.value)


class UnOp(Node):
    def evaluate(self, st: SymbolTable) -> int:
        child_val = self.children[0].evaluate(st)

        if self.value == "+":
            return +child_val
        if self.value == "-":
            return -child_val
        if self.value == "not":
            return 1 if child_val == 0 else 0
        if self.value == "!":
            if child_val < 0:
                raise ValueError("[Semantic] Factorial of negative number")
            result = 1
            for i in range(1, child_val + 1):
                result *= i
            return result

        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def evaluate(self, st: SymbolTable) -> int:
        left_val = self.children[0].evaluate(st)
        right_val = self.children[1].evaluate(st)

        if self.value == "+":
            return left_val + right_val
        if self.value == "-":
            return left_val - right_val
        if self.value == "*":
            return left_val * right_val
        if self.value == "/":
            if right_val == 0:
                raise ValueError("[Semantic] Division by zero")
            return int(left_val / right_val)
        if self.value == "==":
            return 1 if left_val == right_val else 0
        if self.value == ">":
            return 1 if left_val > right_val else 0
        if self.value == "<":
            return 1 if left_val < right_val else 0
        if self.value == "and":
            return 1 if left_val != 0 and right_val != 0 else 0
        if self.value == "or":
            return 1 if left_val != 0 or right_val != 0 else 0

        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class ConditionalExpression(Node):
    """Extra credit: if-expression / ternary conditional.

    Syntax:
        if condition then true_expression else false_expression end
    """

    def evaluate(self, st: SymbolTable) -> int:
        condition = self.children[0].evaluate(st)
        if condition != 0:
            return self.children[1].evaluate(st)
        return self.children[2].evaluate(st)


class Assignment(Node):
    def evaluate(self, st: SymbolTable):
        identifier = self.children[0].value
        value = self.children[1].evaluate(st)
        st.set(identifier, value)


class ImmutableAssignment(Node):
    def evaluate(self, st: SymbolTable):
        identifier = self.children[0].value
        value = self.children[1].evaluate(st)
        st.declare_immutable(identifier, value)


class Print(Node):
    def evaluate(self, st: SymbolTable):
        print(self.children[0].evaluate(st))


class Read(Node):
    def evaluate(self, st: SymbolTable) -> int:
        try:
            return int(input())
        except EOFError as exc:
            raise ValueError("[Semantic] Expected integer input for read()") from exc
        except ValueError as exc:
            raise ValueError("[Semantic] read() expects an integer") from exc


class If(Node):
    def evaluate(self, st: SymbolTable):
        condition = self.children[0].evaluate(st)
        if condition != 0:
            self.children[1].evaluate(st)
        elif len(self.children) == 3:
            self.children[2].evaluate(st)


class While(Node):
    def evaluate(self, st: SymbolTable):
        while self.children[0].evaluate(st) != 0:
            self.children[1].evaluate(st)


class For(Node):
    """Extra credit: inclusive for loop.

    Syntax:
        for i = start_expression, end_expression do
            statement
        end

    The final value is included, as requested by the roteiro.
    """

    def evaluate(self, st: SymbolTable):
        identifier = self.children[0].value
        start_value = self.children[1].evaluate(st)
        end_value = self.children[2].evaluate(st)
        block = self.children[3]

        current = start_value
        while current <= end_value:
            st.set(identifier, current)
            block.evaluate(st)
            current += 1

        # After an inclusive for, the control variable keeps the first value
        # outside the interval. Example: for i = 0, n do ... end leaves i == n + 1.
        st.set(identifier, current)


class Block(Node):
    def evaluate(self, st: SymbolTable):
        for child in self.children:
            child.evaluate(st)


class NoOp(Node):
    def evaluate(self, st: SymbolTable):
        pass


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
            self.next = Token(token_type, identifier)
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer: Lexer | None = None

    @staticmethod
    def expect(token_type: str) -> None:
        if Parser.lexer.next.type != token_type:
            raise ValueError(f"[Parser] Expected {token_type}, got {Parser.lexer.next.type}")
        Parser.lexer.select_next()

    @staticmethod
    def skip_end_lines() -> None:
        while Parser.lexer.next.type == "END":
            Parser.lexer.select_next()

    @staticmethod
    def parse_primary() -> Node:
        if Parser.lexer.next.type == "INT":
            node = IntVal(Parser.lexer.next.value)
            Parser.lexer.select_next()
            return node

        if Parser.lexer.next.type == "IDEN":
            node = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            return node

        if Parser.lexer.next.type == "READ":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            Parser.expect("CLOSE_PAR")
            return Read("read")

        if Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
            return node

        # Extra credit: if-expression with high precedence, parsed as a factor.
        if Parser.lexer.next.type == "IF":
            Parser.lexer.select_next()
            condition = Parser.parse_bool_expression()
            Parser.expect("OPEN_IF_BRA")
            true_expression = Parser.parse_bool_expression()
            Parser.expect("ELSE")
            false_expression = Parser.parse_bool_expression()
            Parser.expect("CLOSE_BRA")
            return ConditionalExpression("if_expression", [condition, true_expression, false_expression])

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

    @staticmethod
    def parse_statement() -> Node:
        if Parser.lexer.next.type == "IDEN":
            identifier = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            Parser.expect("ASSIGN")
            expression = Parser.parse_bool_expression()
            return Assignment("=", [identifier, expression])

        if Parser.lexer.next.type == "PRINT":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            expression = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
            return Print("print", [expression])

        if Parser.lexer.next.type == "IMUT":
            Parser.lexer.select_next()

            if Parser.lexer.next.type != "IDEN":
                raise ValueError(f"[Parser] Expected identifier after imut, got {Parser.lexer.next.type}")

            identifier = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            Parser.expect("ASSIGN")
            expression = Parser.parse_bool_expression()
            return ImmutableAssignment("imut", [identifier, expression])

        if Parser.lexer.next.type == "IF":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            condition = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
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

        if Parser.lexer.next.type == "WHILE":
            Parser.lexer.select_next()
            Parser.expect("OPEN_PAR")
            condition = Parser.parse_bool_expression()
            Parser.expect("CLOSE_PAR")
            Parser.expect("OPEN_BRA")
            Parser.skip_end_lines()
            block = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
            Parser.expect("CLOSE_BRA")
            return While("while", [condition, block])

        if Parser.lexer.next.type == "FOR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(f"[Parser] Expected identifier after for, got {Parser.lexer.next.type}")
            identifier = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()
            Parser.expect("ASSIGN")
            start_expression = Parser.parse_bool_expression()
            Parser.expect("COMMA")
            end_expression = Parser.parse_bool_expression()
            Parser.expect("OPEN_BRA")
            Parser.skip_end_lines()
            block = Parser.parse_block(stop_tokens={"CLOSE_BRA"})
            Parser.expect("CLOSE_BRA")
            return For("for", [identifier, start_expression, end_expression, block])

        if Parser.lexer.next.type == "CONST":
            raise ValueError("[Parser] Constants must be declared as: const NAME VALUE")

        raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type} at start of statement")

    @staticmethod
    def parse_block(stop_tokens=None) -> Node:
        if stop_tokens is None:
            stop_tokens = {"EOF"}

        children = []

        while Parser.lexer.next.type not in stop_tokens and Parser.lexer.next.type != "EOF":
            if Parser.lexer.next.type == "END":
                children.append(NoOp(None))
                Parser.lexer.select_next()
                continue

            children.append(Parser.parse_statement())

            if Parser.lexer.next.type == "END":
                Parser.skip_end_lines()
            elif Parser.lexer.next.type not in stop_tokens and Parser.lexer.next.type != "EOF":
                raise ValueError(f"[Parser] Expected end of line, got {Parser.lexer.next.type}")

        return Block(None, children)

    @staticmethod
    def parse_program() -> Node:
        block = Parser.parse_block(stop_tokens={"EOF"})
        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")
        return block

    @staticmethod
    def run(code: str) -> Node:
        filtered_code = PrePro.filter(code)
        Parser.lexer = Lexer(filtered_code)
        Parser.lexer.select_next()
        return Parser.parse_program()


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
