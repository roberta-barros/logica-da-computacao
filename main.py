from dataclasses import dataclass


@dataclass
class Token:
    type: str          # "INT" | "PLUS" | "MINUS" | "EOF"
    value: int | str   # int para INT, str para os demais (ex: "+", "-", "")


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0   # índice no source
        self.next = None    # Token mais recente separado

    def select_next(self) -> None:
        s = self.source

        # 1) Ignora espaços em branco
        while self.position < len(s) and s[self.position].isspace():
            self.position += 1

        # 2) EOF
        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        # 3) Operadores
        if ch == "+":
            self.position += 1
            self.next = Token("PLUS", "+")
            return

        if ch == "-":
            self.position += 1
            self.next = Token("MINUS", "-")
            return

        # Int
        if ch.isdigit():
            start = self.position
            while self.position < len(s) and s[self.position].isdigit():
                self.position += 1
            number_str = s[start:self.position]
            self.next = Token("INT", int(number_str))
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


class Parser:
    lexer: Lexer | None = None

    @staticmethod
    def parse_expression() -> int:
        # Espera começar com INT
        if Parser.lexer is None:
            raise RuntimeError("[Parser] Lexer not initialized")

        if Parser.lexer.next.type != "INT":
            raise ValueError(f"[Parser] Expected INT, got {Parser.lexer.next.type}")

        result = Parser.lexer.next.value  # int
        Parser.lexer.select_next()

        # Enquanto houver + ou -
        while Parser.lexer.next.type in ("PLUS", "MINUS"):
            op = Parser.lexer.next.type
            Parser.lexer.select_next()

            if Parser.lexer.next.type != "INT":
                raise ValueError(f"[Parser] Expected INT after {op}, got {Parser.lexer.next.type}")

            if op == "PLUS":
                result += Parser.lexer.next.value
            else:  # "MINUS"
                result -= Parser.lexer.next.value

            Parser.lexer.select_next()

        return result

    @staticmethod
    def run(code: str) -> int:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()

        result = Parser.parse_expression()

        if Parser.lexer.next.type != "EOF":
            raise ValueError(f"[Parser] Unexpected token {Parser.lexer.next.type} after expression")

        return result


def main():
    code = input().strip("\n")
    try:
        print(Parser.run(code))
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()