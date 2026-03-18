import sys
from abc import ABC, abstractmethod


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


class Node(ABC):
    def __init__(self, value, children):
        self.value = value
        self.children = children

    @abstractmethod
    def evaluate(self) -> int:
        pass


class IntVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self) -> int:
        return self.value


class UnOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self) -> int:
        child_val = self.children[0].evaluate()
        if self.value == "+":
            return +child_val
        elif self.value == "-":
            return -child_val
        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self) -> int:
        left_val = self.children[0].evaluate()
        right_val = self.children[1].evaluate()
        if self.value == "+":
            return left_val + right_val
        elif self.value == "-":
            return left_val - right_val
        elif self.value == "*":
            return left_val * right_val
        elif self.value == "/":
            if right_val == 0:
                raise ValueError("[Semantic] Division by zero")
            return int(left_val / right_val)
        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        while self.position < len(s) and s[self.position].isspace():
            self.position += 1

        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

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

        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer = None

    @staticmethod
    def parse_factor() -> Node:
        if Parser.lexer.next.type == "INT":
            node = IntVal(Parser.lexer.next.value)
            Parser.lexer.select_next()
            return node

        if Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            child = Parser.parse_factor()
            return UnOp(op, [child])

        if Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(f"[Parser] Expected ')', got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return node

        raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

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
    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        tree = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

        return tree


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input()
    try:
        tree = Parser.run(code)
        print(tree.evaluate())
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()