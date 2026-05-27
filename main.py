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
    def __init__(self, value, type_, shift=None, is_function=False, is_struct=False):
        self.value = value
        self.type = type_
        self.shift = shift
        self.is_function = is_function
        # is_struct = True somente para a *definição* de struct (o nó StructDec
        # vive na SymbolTable raiz). Instâncias de struct usam um Variable
        # normal cujo `value` é a SymbolTable contendo os campos.
        self.is_struct = is_struct


class SymbolTable:
    def __init__(self, parent=None):
        self.table: dict[str, Variable] = {}
        self.next_shift = 0
        self.parent = parent

    def get_value(self, name: str) -> Variable:
        if name in self.table:
            variable = self.table[name]
            if (
                variable.value is None
                and not variable.is_function
                and not variable.is_struct
            ):
                raise ValueError(
                    f"[Semantic] Variable '{name}' declared but not assigned"
                )
            return Variable(
                variable.value,
                variable.type,
                variable.shift,
                variable.is_function,
                variable.is_struct,
            )
        if self.parent is not None:
            return self.parent.get_value(name)
        raise ValueError(f"[Semantic] Variable '{name}' not declared")

    def create_variable(self, name: str, type_: str) -> Variable:
        if name in self.table:
            raise ValueError(f"[Semantic] Variable '{name}' already declared")
        self.next_shift += 4
        variable = Variable(None, type_, self.next_shift)
        self.table[name] = variable
        return variable

    def set_value(self, name: str, variable: Variable) -> None:
        if name in self.table:
            current = self.table[name]
            if current.is_function:
                raise ValueError(
                    f"[Semantic] '{name}' is a function and cannot be reassigned"
                )
            if current.is_struct:
                raise ValueError(
                    f"[Semantic] '{name}' is a struct type and cannot be reassigned"
                )
            if current.type != variable.type:
                raise ValueError(
                    f"[Semantic] Type mismatch in assignment to '{name}': "
                    f"expected {current.type}, got {variable.type}"
                )
            current.value = variable.value
            return
        if self.parent is not None:
            self.parent.set_value(name, variable)
            return
        raise ValueError(f"[Semantic] Variable '{name}' not declared")


class Code:
    instructions = []

    @staticmethod
    def append(code: str) -> None:
        Code.instructions.append(code)

    @staticmethod
    def dump(filename: str) -> None:
        header = """section .data
    format_out: db "%d", 10, 0 ; format do printf
    format_in: db "%d", 0 ; format do scanf
    scan_int: dd 0 ; 32-bits integer

section .text
    extern printf ; usar printf para Linux
    extern scanf ; usar scanf para Linux
    global _start ; início do programa




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
            file.write(header)
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
        raise ValueError("[CodeGen] Strings are not supported")


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
            raise ValueError("[CodeGen] String concatenation not supported")

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
                raise ValueError("[CodeGen] String comparison not supported")
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
            raise ValueError("[CodeGen] Strings are not supported")
        Code.append(f"    mov eax, [ebp-{variable.shift}] ; recupera {self.value}")
        return Variable(None, variable.type, variable.shift)


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
            raise ValueError("[CodeGen] Strings are not supported")
        var_value = self.children[1].generate(st)
        st.set_value(var_name, Variable(0, var_value.type))
        Code.append(f"    mov [ebp-{variable.shift}], eax ; {var_name} = eax")


# === NOVOS NÓS PARA STRUCT ============================================

NATIVE_TYPES = ("number", "string", "boolean")


def _find_root(st: SymbolTable) -> SymbolTable:
    """Sobe a cadeia de SymbolTables até a raiz (escopo global)."""
    root = st
    while root.parent is not None:
        root = root.parent
    return root


class StructDec(Node):
    """Declaração de struct.

    value    = nome da struct (string)
    children = lista de VarDec, um por campo
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        root_st = _find_root(st)
        name = self.value
        if name in root_st.table:
            raise ValueError(f"[Semantic] Struct '{name}' already declared")
        # Guarda o próprio nó como valor da "variável".
        variable = Variable(self, name, shift=None, is_struct=True)
        root_st.table[name] = variable

    def generate(self, st: SymbolTable) -> None:
        raise NotImplementedError("[CodeGen] Struct declarations not yet supported")


class MemberAccess(Node):
    """Acesso a um campo: a.b ou a.b.c ...

    children = lista de Identifier, sendo o primeiro a variável base
               e os demais os nomes dos campos.
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        base_name = self.children[0].value
        # get_value normalmente checa "declarada mas sem valor"; para a base
        # de um struct isso é OK porque o valor é a SymbolTable da instância.
        base_var = st.get_value(base_name)

        current = base_var
        path = [base_name]

        for i in range(1, len(self.children)):
            field_name = self.children[i].value

            if not isinstance(current.value, SymbolTable):
                raise ValueError(
                    f"[Semantic] '{'.'.join(path)}' is not a struct instance"
                )
            field_st = current.value
            if field_name not in field_st.table:
                raise ValueError(
                    f"[Semantic] Struct has no field '{field_name}' "
                    f"(accessing '{'.'.join(path + [field_name])}')"
                )

            field_var = field_st.table[field_name]
            # Campo primitivo sem valor atribuído.
            if (
                field_var.value is None
                and not field_var.is_function
                and not field_var.is_struct
            ):
                raise ValueError(
                    f"[Semantic] Field '{'.'.join(path + [field_name])}' "
                    f"not assigned"
                )
            current = field_var
            path.append(field_name)

        return Variable(current.value, current.type)

    def generate(self, st: SymbolTable) -> Variable:
        raise NotImplementedError("[CodeGen] Member access not yet supported")


class MemberAssignment(Node):
    """Atribuição a um campo: a.b = expr  ou  a.b.c = expr ...

    children[0..-2] = Identifiers (caminho de acesso, base + campos)
    children[-1]    = expressão a ser atribuída
    """
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        # 1. Avalia a expressão no escopo do chamador.
        expr_value = self.children[-1].evaluate(st)

        # 2. Navega da base até o struct que contém o campo final.
        base_name = self.children[0].value
        current = st.get_value(base_name)
        path = [base_name]

        # Identifiers intermediários: do índice 1 até len(children) - 3 inclusive.
        for i in range(1, len(self.children) - 2):
            field_name = self.children[i].value
            if not isinstance(current.value, SymbolTable):
                raise ValueError(
                    f"[Semantic] '{'.'.join(path)}' is not a struct instance"
                )
            field_st = current.value
            if field_name not in field_st.table:
                raise ValueError(
                    f"[Semantic] Struct has no field '{field_name}' "
                    f"(accessing '{'.'.join(path + [field_name])}')"
                )
            current = field_st.table[field_name]
            path.append(field_name)

        # 3. current.value precisa ser a SymbolTable do struct que tem o campo final.
        if not isinstance(current.value, SymbolTable):
            raise ValueError(
                f"[Semantic] '{'.'.join(path)}' is not a struct instance"
            )

        final_field = self.children[-2].value
        target_st = current.value
        if final_field not in target_st.table:
            raise ValueError(
                f"[Semantic] Struct has no field '{final_field}' "
                f"(assigning to '{'.'.join(path + [final_field])}')"
            )

        field_var = target_st.table[final_field]
        if field_var.is_function:
            raise ValueError(
                f"[Semantic] Field '{final_field}' is a function and cannot be reassigned"
            )
        if field_var.type != expr_value.type:
            raise ValueError(
                f"[Semantic] Type mismatch in assignment to "
                f"'{'.'.join(path + [final_field])}': "
                f"expected {field_var.type}, got {expr_value.type}"
            )
        field_var.value = expr_value.value

    def generate(self, st: SymbolTable) -> None:
        raise NotImplementedError("[CodeGen] Member assignment not yet supported")


# ======================================================================


class VarDec(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        name = self.children[0].value
        var_type = self.value

        # Tipo nativo: cria variável e (opcionalmente) atribui valor inicial.
        if var_type in NATIVE_TYPES:
            variable = st.create_variable(name, var_type)
            variable.is_function = False
            variable.is_struct = False
            if len(self.children) > 1:
                st.set_value(name, self.children[1].evaluate(st))
            return

        # Tipo customizado: deve ser uma struct declarada na raiz.
        root_st = _find_root(st)
        if var_type not in root_st.table:
            raise ValueError(f"[Semantic] Type '{var_type}' not declared")

        struct_var = root_st.table[var_type]
        if not struct_var.is_struct:
            raise ValueError(
                f"[Semantic] '{var_type}' is not a valid type "
                f"(declaring '{name}')"
            )

        # Inicialização na declaração não é permitida para structs.
        if len(self.children) > 1:
            raise ValueError(
                f"[Semantic] Struct variable '{name}' cannot be initialized "
                f"at declaration"
            )

        # Instancia a struct: cria uma nova SymbolTable encadeada à raiz
        # (para que os campos possam resolver tipos struct aninhados na raiz).
        # O acesso aos campos é feito por table direta, não por get_value,
        # então não há vazamento de nomes do escopo global.
        instance_st = SymbolTable(parent=root_st)
        struct_dec = struct_var.value  # nó StructDec
        for field_dec in struct_dec.children:
            field_dec.evaluate(instance_st)

        if name in st.table:
            raise ValueError(f"[Semantic] Variable '{name}' already declared")
        new_var = Variable(instance_st, var_type)
        new_var.is_function = False
        new_var.is_struct = False
        st.table[name] = new_var

    def generate(self, st: SymbolTable) -> None:
        name = self.children[0].value
        if self.value == "string":
            raise ValueError("[CodeGen] Strings are not supported")
        if self.value not in NATIVE_TYPES:
            raise NotImplementedError("[CodeGen] Structs are not supported")
        variable = st.create_variable(name, self.value)
        Code.append(f"    sub esp, 4 ; var {name} {self.value} [EBP-{variable.shift}]")
        if len(self.children) > 1:
            var_value = self.children[1].generate(st)
            st.set_value(name, Variable(0, var_value.type))
            Code.append(f"    mov [ebp-{variable.shift}], eax ; {name} = eax")


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
            raise ValueError("[CodeGen] Strings are not supported")
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

    def evaluate(self, st: SymbolTable):
        cond = self.children[0].evaluate(st)
        if cond.type != "boolean":
            raise ValueError("[Semantic] If condition must be boolean")
        if cond.value:
            return self.children[1].evaluate(st)
        if len(self.children) > 2:
            return self.children[2].evaluate(st)
        return None

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

    def evaluate(self, st: SymbolTable):
        while True:
            cond = self.children[0].evaluate(st)
            if cond.type != "boolean":
                raise ValueError("[Semantic] While condition must be boolean")
            if not cond.value:
                break
            result = self.children[1].evaluate(st)
            if result is not None:
                return result
        return None

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

    def evaluate(self, st: SymbolTable):
        for child in self.children:
            if isinstance(child, Return):
                return child.evaluate(st)

            if isinstance(child, Block):
                new_st = SymbolTable(parent=st)
                result = child.evaluate(new_st)
                if result is not None:
                    return result
                continue

            if isinstance(child, (If, While)):
                result = child.evaluate(st)
                if result is not None:
                    return result
                continue

            child.evaluate(st)
        return None

    def generate(self, st: SymbolTable) -> None:
        for child in self.children:
            child.generate(st)


class NoOp(Node):
    def __init__(self, value=None, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        pass

    def generate(self, st: SymbolTable) -> None:
        pass


class Return(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> Variable:
        return self.children[0].evaluate(st)

    def generate(self, st: SymbolTable) -> None:
        raise NotImplementedError("[CodeGen] Return not yet supported")


class FuncDec(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable) -> None:
        root_st = _find_root(st)
        name = self.children[0].value
        variable = root_st.create_variable(name, self.value)
        variable.value = self
        variable.is_function = True

    def generate(self, st: SymbolTable) -> None:
        raise NotImplementedError("[CodeGen] Function declarations not yet supported")


class FuncCall(Node):
    def __init__(self, value, children=None):
        super().__init__(value, children if children is not None else [])

    def evaluate(self, st: SymbolTable):
        name = self.value

        try:
            func_var = st.get_value(name)
        except ValueError:
            raise ValueError(f"[Semantic] Function '{name}' not declared")
        if not func_var.is_function:
            raise ValueError(f"[Semantic] '{name}' is not a function")

        func_dec = func_var.value
        return_type = func_var.type
        params = func_dec.children[1:-1]
        body = func_dec.children[-1]

        if len(self.children) != len(params):
            raise ValueError(
                f"[Semantic] Function '{name}' expects {len(params)} "
                f"argument(s), got {len(self.children)}"
            )

        evaluated_args = []
        for i, arg_node in enumerate(self.children):
            arg_var = arg_node.evaluate(st)
            expected_type = params[i].value
            if arg_var.type != expected_type:
                raise ValueError(
                    f"[Semantic] Argument {i + 1} of '{name}': "
                    f"expected {expected_type}, got {arg_var.type}"
                )
            evaluated_args.append(arg_var)

        root_st = _find_root(st)
        new_st = SymbolTable(parent=root_st)

        for param, arg_var in zip(params, evaluated_args):
            param_name = param.children[0].value
            param_type = param.value
            new_st.create_variable(param_name, param_type)
            new_st.set_value(param_name, Variable(arg_var.value, param_type))

        result = body.evaluate(new_st)

        if result is not None:
            if return_type is None:
                raise ValueError(
                    f"[Semantic] Function '{name}' is void but returned a value"
                )
            if result.type != return_type:
                raise ValueError(
                    f"[Semantic] Function '{name}' must return {return_type}, "
                    f"returned {result.type}"
                )
            return Variable(result.value, return_type)

        if return_type is not None:
            raise ValueError(
                f"[Semantic] Function '{name}' must return a {return_type} value"
            )
        return None

    def generate(self, st: SymbolTable) -> None:
        raise NotImplementedError("[CodeGen] Function calls not yet supported")


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
    "function": "FUNC",
    "return": "RETURN",
    "struct": "STRUCT",
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
            # Ponto único: acesso a campo de struct.
            self.next = Token("DOT", ".")
            return

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


class Parser:
    lexer = None

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

            # Chamada de função como expressão: IDEN ( args )
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise ValueError(
                        f"[Parser] Expected ')' to close call to '{name}', "
                        f"got {Parser.lexer.next.type}"
                    )
                Parser.lexer.select_next()
                return FuncCall(name, args)

            # Acesso a campo de struct: IDEN . IDEN [. IDEN]*
            if Parser.lexer.next.type == "DOT":
                identifiers = [Identifier(name)]
                while Parser.lexer.next.type == "DOT":
                    Parser.lexer.select_next()
                    if Parser.lexer.next.type != "IDEN":
                        raise ValueError(
                            f"[Parser] Expected field name after '.', "
                            f"got {Parser.lexer.next.type}"
                        )
                    identifiers.append(Identifier(Parser.lexer.next.value))
                    Parser.lexer.select_next()
                return MemberAccess(None, identifiers)

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
    def parse_var_declaration() -> Node:
        if Parser.lexer.next.type != "VAR":
            raise ValueError(
                f"[Parser] Expected 'local', got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected identifier after local, got {Parser.lexer.next.type}"
            )
        iden_node = Identifier(Parser.lexer.next.value)
        Parser.lexer.select_next()

        # Aceita 'local x number', 'local x: number' e 'local x::number'.
        if Parser.lexer.next.type == "COLON":
            Parser.lexer.select_next()
            if Parser.lexer.next.type == "COLON":
                Parser.lexer.select_next()

        # Aceita TYPE (number/string/boolean) ou IDEN (nome de struct).
        if Parser.lexer.next.type == "TYPE":
            var_type = Parser.lexer.next.value
        elif Parser.lexer.next.type == "IDEN":
            var_type = Parser.lexer.next.value
        else:
            raise ValueError(
                f"[Parser] Expected type after variable name, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        children = [iden_node]
        if Parser.lexer.next.type == "ASSIGN":
            Parser.lexer.select_next()
            children.append(Parser.parse_bool_expression())
        return VarDec(var_type, children)

    @staticmethod
    def parse_func_declaration() -> Node:
        if Parser.lexer.next.type != "FUNC":
            raise ValueError(
                f"[Parser] Expected 'function', got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected function name, got {Parser.lexer.next.type}"
            )
        name_node = Identifier(Parser.lexer.next.value)
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "OPEN_PAR":
            raise ValueError(
                f"[Parser] Expected '(' after function name, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        params = []
        if Parser.lexer.next.type != "CLOSE_PAR":
            if Parser.lexer.next.type != "IDEN":
                raise ValueError(
                    f"[Parser] Expected parameter name, got {Parser.lexer.next.type}"
                )
            pname = Parser.lexer.next.value
            Parser.lexer.select_next()
            if Parser.lexer.next.type != "TYPE":
                raise ValueError(
                    f"[Parser] Expected type for parameter '{pname}', "
                    f"got {Parser.lexer.next.type}"
                )
            ptype = Parser.lexer.next.value
            Parser.lexer.select_next()
            params.append(VarDec(ptype, [Identifier(pname)]))

            while Parser.lexer.next.type == "COMMA":
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "IDEN":
                    raise ValueError(
                        f"[Parser] Expected parameter name, got {Parser.lexer.next.type}"
                    )
                pname = Parser.lexer.next.value
                Parser.lexer.select_next()
                if Parser.lexer.next.type != "TYPE":
                    raise ValueError(
                        f"[Parser] Expected type for parameter '{pname}', "
                        f"got {Parser.lexer.next.type}"
                    )
                ptype = Parser.lexer.next.value
                Parser.lexer.select_next()
                params.append(VarDec(ptype, [Identifier(pname)]))

        if Parser.lexer.next.type != "CLOSE_PAR":
            raise ValueError(
                f"[Parser] Expected ')' to close parameter list, "
                f"got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        return_type = None
        if Parser.lexer.next.type == "TYPE":
            return_type = Parser.lexer.next.value
            Parser.lexer.select_next()

        if Parser.lexer.next.type != "EOL":
            raise ValueError(
                f"[Parser] Expected newline after function signature, "
                f"got {Parser.lexer.next.type}"
            )
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        body = Parser.parse_block()

        if Parser.lexer.next.type != "CLOSE_BRA":
            raise ValueError(
                f"[Parser] Expected 'end' to close function, got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        return FuncDec(return_type, [name_node] + params + [body])

    @staticmethod
    def parse_struct_declaration() -> Node:
        if Parser.lexer.next.type != "STRUCT":
            raise ValueError(
                f"[Parser] Expected 'struct', got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "IDEN":
            raise ValueError(
                f"[Parser] Expected struct name, got {Parser.lexer.next.type}"
            )
        struct_name = Parser.lexer.next.value
        Parser.lexer.select_next()

        if Parser.lexer.next.type != "EOL":
            raise ValueError(
                f"[Parser] Expected newline after struct name, "
                f"got {Parser.lexer.next.type}"
            )
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        fields = []
        while Parser.lexer.next.type == "VAR":
            field = Parser.parse_var_declaration()
            if len(field.children) > 1:
                raise ValueError(
                    f"[Parser] Struct fields cannot have initialization "
                    f"(field '{field.children[0].value}' of struct '{struct_name}')"
                )
            fields.append(field)
            if Parser.lexer.next.type == "EOL":
                while Parser.lexer.next.type == "EOL":
                    Parser.lexer.select_next()
            elif Parser.lexer.next.type != "CLOSE_BRA":
                raise ValueError(
                    f"[Parser] Expected newline inside struct body, "
                    f"got {Parser.lexer.next.type}"
                )

        if Parser.lexer.next.type != "CLOSE_BRA":
            raise ValueError(
                f"[Parser] Expected 'end' to close struct '{struct_name}', "
                f"got {Parser.lexer.next.type}"
            )
        Parser.lexer.select_next()

        return StructDec(struct_name, fields)

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
            cond = Parser.parse_bool_expression()
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
            cond = Parser.parse_bool_expression()
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

        if token.type == "VAR":
            return Parser.parse_var_declaration()

        if token.type == "RETURN":
            Parser.lexer.select_next()
            expr = Parser.parse_bool_expression()
            return Return("return", [expr])

        if token.type == "IDEN":
            name = token.value
            Parser.lexer.select_next()

            # IDEN ( ... )  -> chamada de função como statement
            if Parser.lexer.next.type == "OPEN_PAR":
                Parser.lexer.select_next()
                args = []
                if Parser.lexer.next.type != "CLOSE_PAR":
                    args.append(Parser.parse_bool_expression())
                    while Parser.lexer.next.type == "COMMA":
                        Parser.lexer.select_next()
                        args.append(Parser.parse_bool_expression())
                if Parser.lexer.next.type != "CLOSE_PAR":
                    raise ValueError(
                        f"[Parser] Expected ')' to close call to '{name}', "
                        f"got {Parser.lexer.next.type}"
                    )
                Parser.lexer.select_next()
                return FuncCall(name, args)

            # IDEN . IDEN [. IDEN]* = expr  -> atribuição a campo de struct
            if Parser.lexer.next.type == "DOT":
                identifiers = [Identifier(name)]
                while Parser.lexer.next.type == "DOT":
                    Parser.lexer.select_next()
                    if Parser.lexer.next.type != "IDEN":
                        raise ValueError(
                            f"[Parser] Expected field name after '.', "
                            f"got {Parser.lexer.next.type}"
                        )
                    identifiers.append(Identifier(Parser.lexer.next.value))
                    Parser.lexer.select_next()

                if Parser.lexer.next.type != "ASSIGN":
                    raise ValueError(
                        f"[Parser] Expected '=' after field access in statement, "
                        f"got {Parser.lexer.next.type}"
                    )
                Parser.lexer.select_next()
                expr = Parser.parse_bool_expression()
                return MemberAssignment("=", identifiers + [expr])

            # IDEN = ...    -> atribuição
            if Parser.lexer.next.type != "ASSIGN":
                raise ValueError(
                    f"[Parser] Expected '=' or '(' after identifier '{name}', "
                    f"got {Parser.lexer.next.type}"
                )
            Parser.lexer.select_next()
            return Assignment("=", [Identifier(name), Parser.parse_bool_expression()])

        raise ValueError(f"[Parser] Unexpected token in statement: {token.type}")

    @staticmethod
    def parse_program() -> Node:
        statements = []
        while Parser.lexer.next.type == "EOL":
            Parser.lexer.select_next()

        while Parser.lexer.next.type != "EOF":
            if Parser.lexer.next.type == "FUNC":
                statements.append(Parser.parse_func_declaration())
            elif Parser.lexer.next.type == "STRUCT":
                statements.append(Parser.parse_struct_declaration())
            else:
                statements.append(Parser.parse_statement())

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
    tree.evaluate(st)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)