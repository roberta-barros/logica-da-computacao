import sys
import os
import re
from abc import ABC, abstractmethod


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value


class PrePro:
    @staticmethod
    def filter(code: str) -> str:
        # Remove comentários inline: de "--" até "\n"
        return re.sub(r"--[^\n]*", "", code)


class Variable:
    def __init__(self, value, type_, shift=None, is_param=False):
        self.value = value
        self.type = type_
        self.shift = shift
        self.is_param = is_param

    def address(self) -> str:
        """Retorna o endereço relativo a EBP. Parâmetros estão em [ebp+N],
        locais em [ebp-N]."""
        if self.is_param:
            return f"ebp+{self.shift}"
        return f"ebp-{self.shift}"


class SymbolTable:
    def __init__(self):
        self.table: dict[str, Variable] = {}
        self.next_shift = 0

    def get_value(self, name: str) -> Variable:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        variable = self.table[name]
        if variable.value is None:
            raise ValueError(f"[Semantic] Variable '{name}' declared but not assigned")
        return Variable(variable.value, variable.type, variable.shift, variable.is_param)

    def create_variable(self, name: str, type_: str) -> Variable:
        if name in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' already declared")
        self.next_shift += 4
        variable = Variable(None, type_, self.next_shift, is_param=False)
        self.table[name] = variable
        return variable

    def create_parameter(self, name: str, type_: str, offset: int) -> Variable:
        """Registra um parâmetro de função com offset positivo a partir de EBP."""
        if name in self.table:
            raise ValueError(f"[Semantic] Parameter '{name}' already declared")
        # Valor placeholder (0) para o generate() não disparar a verificação
        # de "declared but not assigned"; em tempo de execução, o valor real
        # vem da pilha (foi empilhado pelo chamador antes do call).
        variable = Variable(0, type_, offset, is_param=True)
        self.table[name] = variable
        return variable

    def set_value(self, name: str, variable: Variable) -> None:
        if name not in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' not declared")
        current = self.table[name]
        if current.type != variable.type:
            raise ValueError(
                f"[Semantic] Type mismatch in assignment to '{name}': "
                f"expected {current.type}, got {variable.type}"
            )
        current.value = variable.value


class FuncTable:
    """Tabela global de funções definidas pelo usuário."""
    functions: dict = {}

    @staticmethod
    def declare(name: str, node) -> None:
        if name in FuncTable.functions:
            raise ValueError(f"[Semantic] Function '{name}' already declared")
        FuncTable.functions[name] = node

    @staticmethod
    def get(name: str):
        if name not in FuncTable.functions:
            raise ValueError(f"[Semantic] Function '{name}' not declared")
        return FuncTable.functions[name]

    @staticmethod
    def reset() -> None:
        FuncTable.functions = {}


class ReturnException(Exception):
    """Usado no evaluate() para "desempilhar" o corpo da função em um return."""
    def __init__(self, value, type_):
        super().__init__()
        self.value = value
        self.type = type_


class Code:
    instructions = []   # corpo do _start (código principal)
    functions = []      # código de funções definidas pelo usuário
    current_target = "main"  # "main" ou "function"

    @staticmethod
    def append(code: str) -> None:
        if Code.current_target == "function":
            Code.functions.append(code)
        else:
            Code.instructions.append(code)

    @staticmethod
    def reset() -> None:
        Code.instructions = []
        Code.functions = []
        Code.current_target = "main"

    @staticmethod
    def dump(filename: str) -> None:
        data_section = """section .data
    format_out: db "%d", 10, 0 ; format do printf
    format_in: db "%d", 0 ; format do scanf
    scan_int: dd 0 ; 32-bits integer

section .text
    extern printf ; usar printf para Linux
    extern scanf ; usar scanf para Linux
    global _start ; início do programa
"""

        start_header = """
_start:
    push ebp ; guarda o EBP
    mov ebp, esp ; zera a pilha

    ; aqui começa o código gerado:"""

        footer = """

    ; aqui termina o código gerado

    mov esp, ebp ; reestabelece a pilha
    pop ebp

    ; chamada da interrupcao de saida (Linux)
    mov eax, 1
    xor ebx, ebx
    int 0x80
"""

        with open(filename, "w") as file:
            file.write(data_section)
            if Code.functions:
                file.write("\n")
                file.write("\n".join(Code.functions))
                file.write("\n")
            file.write(start_header)
            if Code.instructions:
                file.write("\n")
                file.write("\n".join(Code.instructions))
            file.write(footer)


class Node(ABC):
    id = 0

    def __init__(self, value, children):
        self.value = value
        self.children = children
        self.node_id = Node.new_id()

    @staticmethod
    def new_id() -> int:
        Node.id += 1
        return Node.id

    @abstractmethod
    def evaluate(self, st: SymbolTable):
        pass

    @abstractmethod
    def generate(self, st: SymbolTable):
        pass


class IntVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "number")

    def generate(self, st: SymbolTable) -> Variable:
        Code.append(f"    mov eax, {self.value}")
        return Variable(None, "number")


class BoolVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "boolean")

    def generate(self, st: SymbolTable) -> Variable:
        Code.append(f"    mov eax, {1 if self.value else 0}")
        return Variable(None, "boolean")


class StringVal(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return Variable(self.value, "string")

    def generate(self, st: SymbolTable) -> Variable:
        raise ValueError("[CodeGen] Strings are not supported in Roteiro 8")


class UnOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        child = self.children[0].evaluate(st)
        if self.value == "+":
            if child.type != "number":
                raise ValueError("[Semantic] Unary '+' expects number")
            return Variable(+child.value, "number")
        if self.value == "-":
            if child.type != "number":
                raise ValueError("[Semantic] Unary '-' expects number")
            return Variable(-child.value, "number")
        if self.value == "not":
            if child.type != "boolean":
                raise ValueError("[Semantic] Unary 'not' expects boolean")
            return Variable(not child.value, "boolean")
        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")

    def generate(self, st: SymbolTable) -> Variable:
        child = self.children[0].generate(st)

        if self.value == "+":
            if child.type != "number":
                raise ValueError("[Semantic] Unary '+' expects number")
            return Variable(None, "number")

        if self.value == "-":
            if child.type != "number":
                raise ValueError("[Semantic] Unary '-' expects number")
            Code.append("    neg eax")
            return Variable(None, "number")

        if self.value == "not":
            if child.type != "boolean":
                raise ValueError("[Semantic] Unary 'not' expects boolean")
            Code.append("    cmp eax, 0")
            Code.append("    mov eax, 0")
            Code.append("    mov ecx, 1")
            Code.append("    cmove eax, ecx")
            return Variable(None, "boolean")

        raise ValueError(f"[Semantic] Unknown unary operator '{self.value}'")


class BinOp(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        left = self.children[0].evaluate(st)
        right = self.children[1].evaluate(st)

        if self.value == "+":
            if left.type == right.type == "number":
                return Variable(left.value + right.value, "number")
            raise ValueError("[Semantic] Operator '+' expects number+number")

        if self.value == "..":
            def to_string(variable: Variable) -> str:
                if variable.type == "boolean":
                    return "true" if variable.value else "false"
                return str(variable.value)
            return Variable(to_string(left) + to_string(right), "string")

        if self.value == "-":
            if left.type == right.type == "number":
                return Variable(left.value - right.value, "number")
            raise ValueError("[Semantic] Operator '-' expects number-number")

        if self.value == "*":
            if left.type == right.type == "number":
                return Variable(left.value * right.value, "number")
            raise ValueError("[Semantic] Operator '*' expects number*number")

        if self.value == "/":
            if left.type == right.type == "number":
                if right.value == 0:
                    raise ValueError("[Semantic] Division by zero")
                return Variable(int(left.value / right.value), "number")
            raise ValueError("[Semantic] Operator '/' expects number/number")

        if self.value == "==":
            if left.type != right.type:
                raise ValueError("[Semantic] Operator '==' expects operands of the same type")
            return Variable(left.value == right.value, "boolean")

        if self.value == ">":
            if left.type == right.type == "number":
                return Variable(left.value > right.value, "boolean")
            if left.type == right.type == "string":
                return Variable(left.value > right.value, "boolean")
            raise ValueError("[Semantic] Operator '>' expects number>number or string>string")

        if self.value == "<":
            if left.type == right.type == "number":
                return Variable(left.value < right.value, "boolean")
            if left.type == right.type == "string":
                return Variable(left.value < right.value, "boolean")
            raise ValueError("[Semantic] Operator '<' expects number<number or string<string")

        if self.value == "and":
            if left.type == right.type == "boolean":
                return Variable(left.value and right.value, "boolean")
            raise ValueError("[Semantic] Operator 'and' expects boolean and boolean")

        if self.value == "or":
            if left.type == right.type == "boolean":
                return Variable(left.value or right.value, "boolean")
            raise ValueError("[Semantic] Operator 'or' expects boolean or boolean")

        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")

    def generate(self, st: SymbolTable) -> Variable:
        left = self.children[0].generate(st)
        Code.append("    push eax")
        right = self.children[1].generate(st)
        Code.append("    pop ecx")

        if self.value == "+":
            if left.type == right.type == "number":
                Code.append("    add eax, ecx")
                return Variable(None, "number")
            raise ValueError("[Semantic] Operator '+' expects number+number")

        if self.value == "..":
            raise ValueError("[CodeGen] String concatenation is not supported in Roteiro 8")

        if self.value == "-":
            if left.type == right.type == "number":
                Code.append("    sub ecx, eax")
                Code.append("    mov eax, ecx")
                return Variable(None, "number")
            raise ValueError("[Semantic] Operator '-' expects number-number")

        if self.value == "*":
            if left.type == right.type == "number":
                Code.append("    imul eax, ecx")
                return Variable(None, "number")
            raise ValueError("[Semantic] Operator '*' expects number*number")

        if self.value == "/":
            if left.type == right.type == "number":
                Code.append("    mov ebx, eax")
                Code.append("    mov eax, ecx")
                Code.append("    cdq")
                Code.append("    idiv ebx")
                return Variable(None, "number")
            raise ValueError("[Semantic] Operator '/' expects number/number")

        if self.value == "==":
            if left.type != right.type:
                raise ValueError("[Semantic] Operator '==' expects operands of the same type")
            if left.type == "string":
                raise ValueError("[CodeGen] String comparison is not supported in Roteiro 8")
            Code.append("    cmp ecx, eax")
            Code.append("    mov eax, 0")
            Code.append("    mov ecx, 1")
            Code.append("    cmove eax, ecx")
            return Variable(None, "boolean")

        if self.value == ">":
            if left.type == right.type == "number":
                Code.append("    cmp ecx, eax")
                Code.append("    mov eax, 0")
                Code.append("    mov ecx, 1")
                Code.append("    cmovg eax, ecx")
                return Variable(None, "boolean")
            raise ValueError("[Semantic] Operator '>' expects number>number")

        if self.value == "<":
            if left.type == right.type == "number":
                Code.append("    cmp ecx, eax")
                Code.append("    mov eax, 0")
                Code.append("    mov ecx, 1")
                Code.append("    cmovl eax, ecx")
                return Variable(None, "boolean")
            raise ValueError("[Semantic] Operator '<' expects number<number")

        if self.value == "and":
            if left.type == right.type == "boolean":
                Code.append("    and eax, ecx")
                return Variable(None, "boolean")
            raise ValueError("[Semantic] Operator 'and' expects boolean and boolean")

        if self.value == "or":
            if left.type == right.type == "boolean":
                Code.append("    or eax, ecx")
                return Variable(None, "boolean")
            raise ValueError("[Semantic] Operator 'or' expects boolean or boolean")

        raise ValueError(f"[Semantic] Unknown binary operator '{self.value}'")


class Identifier(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return st.get_value(self.value)

    def generate(self, st: SymbolTable) -> Variable:
        variable = st.get_value(self.value)
        if variable.type == "string":
            raise ValueError("[CodeGen] Strings are not supported in Roteiro 8")
        Code.append(f"    mov eax, [{variable.address()}] ; recupera {self.value}")
        return Variable(None, variable.type, variable.shift, variable.is_param)


class Assignment(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value
        var_value = self.children[1].evaluate(st)
        st.set_value(var_name, var_value)

    def generate(self, st: SymbolTable) -> None:
        var_name = self.children[0].value
        if var_name not in st.table:
            raise ValueError(f"[Semantic] Variable '{var_name}' not declared")
        variable = st.table[var_name]
        if variable.type == "string":
            raise ValueError("[CodeGen] Strings are not supported in Roteiro 8")
        var_value = self.children[1].generate(st)
        st.set_value(var_name, Variable(0, var_value.type))
        Code.append(f"    mov [{variable.address()}], eax ; {var_name} = eax")


class VarDec(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        name = self.children[0].value
        st.create_variable(name, self.value)
        if len(self.children) > 1:
            st.set_value(name, self.children[1].evaluate(st))

    def generate(self, st: SymbolTable) -> None:
        name = self.children[0].value
        if self.value == "string":
            raise ValueError("[CodeGen] Strings are not supported in Roteiro 8")
        variable = st.create_variable(name, self.value)
        Code.append(f"    sub esp, 4 ; var {name} {self.value} [EBP-{variable.shift}]")
        if len(self.children) > 1:
            var_value = self.children[1].generate(st)
            st.set_value(name, Variable(0, var_value.type))
            Code.append(f"    mov [{variable.address()}], eax ; {name} = eax")


class Print(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        result = self.children[0].evaluate(st)
        if result.type == "boolean":
            print("true" if result.value else "false")
        else:
            print(result.value)

    def generate(self, st: SymbolTable) -> None:
        result = self.children[0].generate(st)
        if result.type == "string":
            raise ValueError("[CodeGen] Strings are not supported in Roteiro 8")
        Code.append("    push eax ; empilha valor do print")
        Code.append("    push format_out ; formato int de saída")
        Code.append("    call printf")
        Code.append("    add esp, 8 ; limpa os argumentos")


class Read(Node):
    def __init__(self, value="read", children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        raw = input()
        if re.fullmatch(r"[+-]?\d+", raw):
            return Variable(int(raw), "number")
        if raw == "true":
            return Variable(True, "boolean")
        if raw == "false":
            return Variable(False, "boolean")
        return Variable(raw, "string")

    def generate(self, st: SymbolTable) -> Variable:
        Code.append("    push scan_int ; endereço de memória de suporte")
        Code.append("    push format_in ; formato de entrada (int)")
        Code.append("    call scanf")
        Code.append("    add esp, 8 ; remove os argumentos da pilha")
        Code.append("    mov eax, dword [scan_int] ; retorna o valor lido em EAX")
        return Variable(None, "number")


class If(Node):
    """2 ou 3 filhos: [cond, if_block, else_block?]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        cond = self.children[0].evaluate(st)
        if cond.type != "boolean":
            raise ValueError("[Semantic] If condition must be boolean")
        if cond.value:
            self.children[1].evaluate(st)
        elif len(self.children) > 2:
            self.children[2].evaluate(st)

    def generate(self, st: SymbolTable) -> None:
        label_id = self.node_id
        cond = self.children[0].generate(st)
        if cond.type != "boolean":
            raise ValueError("[Semantic] If condition must be boolean")

        if len(self.children) > 2:
            Code.append("    cmp eax, 0 ; verifica se a condição do if deu falso")
            Code.append(f"    je else_{label_id}")
            self.children[1].generate(st)
            Code.append(f"    jmp exit_{label_id}")
            Code.append(f"else_{label_id}:")
            self.children[2].generate(st)
            Code.append(f"exit_{label_id}:")
        else:
            Code.append("    cmp eax, 0 ; verifica se a condição do if deu falso")
            Code.append(f"    je exit_{label_id}")
            self.children[1].generate(st)
            Code.append(f"exit_{label_id}:")


class While(Node):
    """2 filhos: [cond, block]"""
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        while True:
            cond = self.children[0].evaluate(st)
            if cond.type != "boolean":
                raise ValueError("[Semantic] While condition must be boolean")
            if not cond.value:
                break
            self.children[1].evaluate(st)

    def generate(self, st: SymbolTable) -> None:
        label_id = self.node_id
        Code.append(f"loop_{label_id}: ; label do loop")
        cond = self.children[0].generate(st)
        if cond.type != "boolean":
            raise ValueError("[Semantic] While condition must be boolean")
        Code.append("    cmp eax, 0 ; se a condição for falsa, sai")
        Code.append(f"    je exit_{label_id}")
        self.children[1].generate(st)
        Code.append(f"    jmp loop_{label_id}")
        Code.append(f"exit_{label_id}:")


class Block(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        # Pré-registra todas as funções declaradas neste bloco para permitir
        # chamadas "forward" e recursão mútua.
        for child in self.children:
            if isinstance(child, FuncDec) and child.value not in FuncTable.functions:
                FuncTable.declare(child.value, child)
        # Executa apenas os filhos que não são FuncDec (estes já foram registrados;
        # o corpo só roda quando chamado).
        for child in self.children:
            if not isinstance(child, FuncDec):
                child.evaluate(st)

    def generate(self, st: SymbolTable) -> None:
        # Pré-registra funções para permitir chamadas forward / recursão mútua.
        for child in self.children:
            if isinstance(child, FuncDec) and child.value not in FuncTable.functions:
                FuncTable.declare(child.value, child)
        # Gera código de todos os filhos; FuncDec emite na lista 'functions',
        # os demais nós emitem na lista 'instructions'.
        for child in self.children:
            child.generate(st)


class NoOp(Node):
    def __init__(self, value=None, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        pass

    def generate(self, st: SymbolTable) -> None:
        pass


# =====================================================================
# Extra Credit: Funções
# =====================================================================

class FuncDec(Node):
    """
    Declaração de função.
      value     : nome da função (str)
      children  : [params..., body]   (params: VarDec sem inicializador; body: Block)
      return_type : tipo de retorno (str ou None)
    """
    def __init__(self, name, return_type, params, body):
        super().__init__(name, list(params) + [body])
        self.return_type = return_type
        self.n_params = len(params)

    @property
    def params(self):
        return self.children[: self.n_params]

    @property
    def body(self):
        return self.children[self.n_params]

    def evaluate(self, st: SymbolTable) -> None:
        if self.value not in FuncTable.functions:
            FuncTable.declare(self.value, self)

    def generate(self, st: SymbolTable) -> None:
        # Garante que esteja registrada (idempotente)
        if self.value not in FuncTable.functions:
            FuncTable.declare(self.value, self)

        # Troca para o "alvo" de funções: tudo que append() receber agora
        # vai para Code.functions (que é despejado antes de _start).
        old_target = Code.current_target
        Code.current_target = "function"

        Code.append("")
        Code.append(f"{self.value}: ; função {self.value}")
        Code.append("    push ebp ; salva EBP do chamador")
        Code.append("    mov ebp, esp ; novo frame")

        # Cria um escopo local novo para a função
        func_st = SymbolTable()

        # Parâmetros vivem em [EBP+8], [EBP+12], ...
        # ([EBP] = EBP antigo, [EBP+4] = endereço de retorno empilhado por 'call')
        offset = 8
        for param in self.params:
            param_name = param.children[0].value
            param_type = param.value
            if param_type == "string":
                raise ValueError("[CodeGen] String parameters are not supported in Roteiro 8")
            func_st.create_parameter(param_name, param_type, offset)
            Code.append(f"    ; param {param_name} {param_type} [EBP+{offset}]")
            offset += 4

        # Gera o corpo
        self.body.generate(func_st)

        # Epílogo padrão (caso a função não tenha return explícito no final).
        # Se houver return no caminho, ele já emite seu próprio leave/ret.
        Code.append(f"    ; epílogo padrão de {self.value} (fallthrough)")
        Code.append("    mov esp, ebp ; restaura ESP")
        Code.append("    pop ebp ; restaura EBP do chamador")
        Code.append("    ret")

        # Restaura o alvo anterior (volta para 'main' ou outro)
        Code.current_target = old_target


class FuncCall(Node):
    """
    Chamada de função.
      value    : nome da função (str)
      children : argumentos (expressões)
    """
    def __init__(self, name, args):
        super().__init__(name, args)

    def evaluate(self, st: SymbolTable) -> Variable:
        func = FuncTable.get(self.value)
        if len(self.children) != func.n_params:
            raise ValueError(
                f"[Semantic] Function '{self.value}' expects {func.n_params} "
                f"argument(s), got {len(self.children)}"
            )

        # Avalia argumentos no escopo do chamador
        arg_values = [arg.evaluate(st) for arg in self.children]

        # Cria escopo da função
        func_st = SymbolTable()
        for param, arg_val in zip(func.params, arg_values):
            param_name = param.children[0].value
            param_type = param.value
            if arg_val.type != param_type:
                raise ValueError(
                    f"[Semantic] Argument type mismatch in call to '{self.value}': "
                    f"expected {param_type}, got {arg_val.type}"
                )
            func_st.create_variable(param_name, param_type)
            func_st.set_value(param_name, arg_val)

        # Executa o corpo, capturando o return
        try:
            func.body.evaluate(func_st)
        except ReturnException as ret:
            return Variable(ret.value, ret.type)

        # Função sem return explícito: retorno "vazio" (0/number)
        return Variable(0, func.return_type or "number")

    def generate(self, st: SymbolTable) -> Variable:
        func = FuncTable.get(self.value)
        if len(self.children) != func.n_params:
            raise ValueError(
                f"[Semantic] Function '{self.value}' expects {func.n_params} "
                f"argument(s), got {len(self.children)}"
            )

        # Convenção cdecl: empilha argumentos da direita para a esquerda,
        # assim o primeiro argumento fica em [EBP+8] dentro da função.
        for arg in reversed(self.children):
            arg.generate(st)
            Code.append(f"    push eax ; arg para {self.value}")

        Code.append(f"    call {self.value}")

        # Chamador limpa a pilha (cdecl)
        n_args = len(self.children)
        if n_args > 0:
            Code.append(f"    add esp, {4 * n_args} ; limpa args de {self.value}")

        # O resultado da função vem em EAX
        return Variable(None, func.return_type or "number")


class Return(Node):
    """
    Return statement.
      children : [] (vazio) ou [expr]
    """
    def __init__(self, value="return", children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        if self.children:
            result = self.children[0].evaluate(st)
            raise ReturnException(result.value, result.type)
        raise ReturnException(0, "number")

    def generate(self, st: SymbolTable) -> None:
        if self.children:
            self.children[0].generate(st)  # resultado em EAX
        else:
            Code.append("    mov eax, 0 ; return sem valor")
        # Epílogo da função: restaura pilha e retorna ao chamador
        Code.append("    mov esp, ebp ; epílogo (return)")
        Code.append("    pop ebp")
        Code.append("    ret")


# =====================================================================
# Lexer
# =====================================================================

RESERVED_WORDS = {
    "print": "PRINT",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "then": "OPEN_IF_BRA",
    "do": "OPEN_BRA",
    "end": "CLOSE_BRA",
    "read": "READ",
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "local": "VAR",
    "true": "BOOL",
    "false": "BOOL",
    "string": "TYPE",
    "number": "TYPE",
    "boolean": "TYPE",
    "function": "FUNCTION",
    "return": "RETURN",
}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.next = Token("EOF", "")

    def select_next(self) -> None:
        s = self.source

        while self.position < len(s) and s[self.position] in (" ", "\t"):
            self.position += 1

        if self.position >= len(s):
            self.next = Token("EOF", "")
            return

        ch = s[self.position]

        if ch == "\n":
            self.position += 1
            self.next = Token("EOL", "\\n")
            return

        if ch == '"':
            self.position += 1
            string_value = ""
            while self.position < len(s) and s[self.position] != '"':
                if s[self.position] == "\n":
                    raise ValueError("[Lexer] Unterminated string literal")
                string_value += s[self.position]
                self.position += 1
            if self.position >= len(s):
                raise ValueError("[Lexer] Unterminated string literal")
            self.position += 1
            self.next = Token("STR", string_value)
            return

        if ch == ".":
            self.position += 1
            if self.position < len(s) and s[self.position] == ".":
                self.position += 1
                self.next = Token("CONCAT", "..")
                return
            raise ValueError(f"[Lexer] Invalid symbol '.' at position {self.position - 1}")

        if ch == ":":
            self.position += 1
            self.next = Token("COLON", ":")
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
        if ch == "=":
            self.position += 1
            if self.position < len(s) and s[self.position] == "=":
                self.position += 1
                self.next = Token("EQ", "==")
                return
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

        if ch.isdigit():
            num = ""
            while self.position < len(s) and s[self.position].isdigit():
                num += s[self.position]
                self.position += 1
            self.next = Token("INT", int(num))
            return

        if ch.isalpha() or ch == "_":
            word = ""
            while self.position < len(s) and (
                s[self.position].isalpha()
                or s[self.position].isdigit()
                or s[self.position] == "_"
            ):
                word += s[self.position]
                self.position += 1
            if word in RESERVED_WORDS:
                self.next = Token(RESERVED_WORDS[word], word)
            else:
                self.next = Token("IDEN", word)
            return

        raise ValueError(f"[Lexer] Invalid symbol '{ch}' at position {self.position}")


# =====================================================================
# Parser
# =====================================================================

class Parser:
    lexer = None

    @staticmethod
    def _parse_call_args() -> list:
        """Consome '(args)' e retorna a lista de nós de argumentos.
        Pressupõe que o lexer está em OPEN_PAR."""
        if Parser.lexer.next.type != "OPEN_PAR":
            raise ValueError(
                f"[Parser] Expected '(' for call args, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()
        args = []
        if Parser.lexer.next.type != "CLOSE_PAR":
            args.append(Parser.parse_bool_expression())
            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                args.append(Parser.parse_bool_expression())
        if Parser.lexer.next.type != "CLOSE_PAR":
            raise ValueError(
                f"[Parser] Expected ')' in call args, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()
        return args

    @staticmethod
    def parse_factor() -> Node:
        token = Parser.lexer.next

        if token.type == "INT":
            node = IntVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type == "BOOL":
            node = BoolVal(token.value == "true")
            Parser.lexer.select_next()
            return node

        if token.type == "STR":
            node = StringVal(token.value)
            Parser.lexer.select_next()
            return node

        if token.type in ("PLUS", "MINUS", "NOT"):
            op = token.value
            Parser.lexer.select_next()
            return UnOp(op, [Parser.parse_factor()])

        if token.type == "OPEN_PAR":
            Parser.lexer.select_next()
            node = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return node

        if token.type == "IDEN":
            name = token.value
            Parser.lexer.select_next()
            # Função chamada como expressão: nome(args)
            if Parser.lexer.next.type == "OPEN_PAR":
                args = Parser._parse_call_args()
                return FuncCall(name, args)
            return Identifier(name)

        if token.type == "READ":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after read, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after read(, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Read()

        raise ValueError(f"[Parser] Unexpected token in factor: {token.type}")

    @staticmethod
    def parse_term() -> Node:
        result = Parser.parse_factor()
        while Parser.lexer.next.type in ("MULT", "DIV"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_factor()])
        return result

    @staticmethod
    def parse_expression() -> Node:
        result = Parser.parse_term()
        while Parser.lexer.next.type in ("PLUS", "MINUS", "CONCAT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_term()])
        return result

    @staticmethod
    def parse_rel_expression() -> Node:
        result = Parser.parse_expression()
        while Parser.lexer.next.type in ("EQ", "GT", "LT"):
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_expression()])
        return result

    @staticmethod
    def parse_bool_term() -> Node:
        result = Parser.parse_rel_expression()
        while Parser.lexer.next.type == "AND":
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_rel_expression()])
        return result

    @staticmethod
    def parse_bool_expression() -> Node:
        result = Parser.parse_bool_term()
        while Parser.lexer.next.type == "OR":
            op = Parser.lexer.next.value
            Parser.lexer.select_next()
            result = BinOp(op, [result, Parser.parse_bool_term()])
        return result

    @staticmethod
    def parse_block() -> Node:
        stmts = []
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        while Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
            stmt = Parser.parse_statement()
            stmts.append(stmt)
            if Parser.lexer.next.type == "EOL":
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
            elif Parser.lexer.next.type not in ("CLOSE_BRA", "ELSE", "EOF"):
                raise ValueError(
                    f"[Parser] Expected newline inside block, got {Parser.lexer.next.type}"
                )
        return Block("block", stmts)

    @staticmethod
    def parse_param() -> Node:
        """Lê um parâmetro de função: IDEN [:] TYPE."""
        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected parameter name, got {Parser.lexer.next.type}"
            )
        iden_node = Identifier(Parser.lexer.next.value)
        Parser.lexer.select_next()

        # Aceita 'x number', 'x: number' e 'x::number'
        if Parser.lexer.next.type == "COLON":
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "COLON":
                Parser.lexer.select_next()

        if Parser.lexer.next.type != "TYPE":
            raise ValueError(
                f"[Parser] Expected type for parameter, got {Parser.lexer.next.type}"
            )
        param_type = Parser.lexer.next.value
        Parser.lexer.select_next()
        return VarDec(param_type, [iden_node])

    @staticmethod
    def parse_function_dec() -> Node:
        """'function' já foi consumido."""
        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected function name, got {Parser.lexer.next.type}"
            )
        name = Parser.lexer.next.value
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_PAR":
            raise ValueError(
                f"[Parser] Expected '(' after function name, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        params = []
        if Parser.lexer.next.type != "CLOSE_PAR":
            params.append(Parser.parse_param())
            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                params.append(Parser.parse_param())

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise ValueError(
                f"[Parser] Expected ')' after parameters, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        # Tipo de retorno opcional. Aceita:
        #   ': TYPE'   (com dois-pontos)
        #   'TYPE'     (estilo Lua-like usado pelo tester: 'function f(x number) number')
        #   nada       (procedimento, ex: 'function main()')
        return_type = None
        if Parser.lexer.next.type == "COLON":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise ValueError(
                    f"[Parser] Expected return type after ':', got {Parser.lexer.next.type}"
                )
            return_type = Parser.lexer.next.value
            Parser.lexer.select_next()
        elif Parser.lexer.next.type == "TYPE":
            return_type = Parser.lexer.next.value
            Parser.lexer.select_next()

        # Pula EOLs
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        body = Parser.parse_block()

        if Parser.lexer.next.type != "CLOSE_BRA":
            raise ValueError(
                f"[Parser] Expected 'end' to close function, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        return FuncDec(name, return_type, params, body)

    @staticmethod
    def parse_statement() -> Node:
        token = Parser.lexer.next

        if token.type in ("EOL", "EOF"):
            return NoOp()

        if token.type == "PRINT":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after print, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after print expr, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Print("print", [expr])

        if token.type == "IF":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after if cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_IF_BRA":
                raise ValueError(
                    f"[Parser] Expected 'then', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            if_block = Parser.parse_block()

            children = [cond, if_block]
            if Parser.lexer.next.type == "ELSE":
                Parser.lexer.select_next()
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
                children.append(Parser.parse_block())

            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close if, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return If("if", children)

        if token.type == "WHILE":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_PAR":
                raise ValueError(
                    f"[Parser] Expected '(' after while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            cond = Parser.parse_bool_expression()
            if Parser.lexer.next.type != "CLOSE_PAR":
                raise ValueError(
                    f"[Parser] Expected ')' after while cond, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "OPEN_BRA":
                raise ValueError(
                    f"[Parser] Expected 'do', got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close while, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return While("while", [cond, body])

        if token.type == "OPEN_BRA":
            Parser.lexer.select_next()
            while Parser.lexer.next.type == "EOL":
                Parser.lexer.select_next()
            body = Parser.parse_block()
            if Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected 'end' to close block, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return body

        if token.type == "FUNCTION":
            Parser.lexer.select_next()
            return Parser.parse_function_dec()

        if token.type == "RETURN":
            Parser.lexer.select_next()
            # 'return' sem expressão (fim de linha / fim de bloco)
            if Parser.lexer.next.type in ("EOL", "CLOSE_BRA", "ELSE", "EOF"):
                return Return()
            expr = Parser.parse_bool_expression()
            return Return("return", [expr])

        if token.type == "VAR":
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected identifier after local, got {Parser.lexer.next.type}"
                )
            iden_node = Identifier(Parser.lexer.next.value)
            Parser.lexer.select_next()

            # Aceita 'local x number', 'local x: number' e 'local x::number'
            if Parser.lexer.next.type == "COLON":
                Parser.lexer.select_next()
                if Parser.lexer.next.type == "COLON":
                    Parser.lexer.select_next()

            if Parser.lexer.next.type != "TYPE":
                raise ValueError(
                    f"[Parser] Expected type after variable name, got {Parser.lexer.next.type}"
                )
            var_type = Parser.lexer.next.value
            Parser.lexer.select_next()

            children = [iden_node]
            if Parser.lexer.next.type == "ASSIGN":
                Parser.lexer.select_next()
                children.append(Parser.parse_bool_expression())
            return VarDec(var_type, children)

        if token.type == "IDEN":
            name = token.value
            Parser.lexer.select_next()

            # Chamada de função como statement: nome(args)
            if Parser.lexer.next.type == "OPEN_PAR":
                args = Parser._parse_call_args()
                return FuncCall(name, args)

            # Atribuição: nome = expr
            iden_node = Identifier(name)
            if Parser.lexer.next.type != "ASSIGN":
                raise ValueError(
                    f"[Parser] Expected '=' or '(' after identifier, got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Assignment("=", [iden_node, Parser.parse_bool_expression()])

        raise ValueError(f"[Parser] Unexpected token in statement: {token.type}")

    @staticmethod
    def parse_program() -> Node:
        statements = []
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        while Parser.lexer.next.type != "EOF":
            stmt = Parser.parse_statement()
            statements.append(stmt)
            if Parser.lexer.next.type == "EOL":
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
            elif Parser.lexer.next.type != "EOF":
                raise ValueError(
                    f"[Parser] Expected newline or EOF, got {Parser.lexer.next.type}"
                )
        return Block("block", statements)

    @staticmethod
    def run(code: str) -> Node:
        Parser.lexer = Lexer(code)
        Parser.lexer.select_next()
        tree = Parser.parse_program()
        if Parser.lexer.next.type != "EOF":
            raise ValueError(
                f"[Parser] Unexpected token after program: {Parser.lexer.next.type}"
            )
        return tree


def main():
    if len(sys.argv) < 2:
        print("[Main] Usage: python3 main.py <filename.lua>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename, "r") as f:
        code = f.read()
    code += "\n"

    code = PrePro.filter(code)
    tree = Parser.run(code)

    st = SymbolTable()
    Code.reset()
    FuncTable.reset()
    tree.generate(st)

    output_filename = os.path.splitext(filename)[0] + ".asm"
    Code.dump(output_filename)
    print(f"[Main] Assembly generated: {output_filename}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)