import sys


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


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
    def parse_factor() -> int:
        if Parser.lexer.next.type == "INT":
            result = Parser.lexer.next.value
            Parser.lexer.select_next()
            return result

        if Parser.lexer.next.type == "PLUS":
            Parser.lexer.select_next()
            return +Parser.parse_factor()

        if Parser.lexer.next.type == "MINUS":
            Parser.lexer.select_next()
            return -Parser.parse_factor()

        if Parser.lexer.next.type == "OPEN_PAR":
            Parser.lexer.select_next()
            result = Parser.parse_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(f"[Parser] Expected ')', got {Parser.lexer.next.type}")
            Parser.lexer.select_next()
            return result

        raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

    @staticmethod
    def parse_term() -> int:
        result = Parser.parse_factor()

        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()
            value = Parser.parse_factor()
            if op == "MULT":
                result *= value
            else:
                result = int(result / value)  # divisão inteira truncando para zero

        return result

    @staticmethod
    def parse_expression() -> int:
        result = Parser.parse_term()

        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()
            value = Parser.parse_term()
            if op == "PLUS":
                result += value
            else:
                result -= value

        return result

    @staticmethod
    def run(code: str) -> int:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        result = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type}")

        return result


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else input()
    try:
        print(Parser.run(code))
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()