section .data
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

    ; aqui começa o código gerado:
    sub esp, 4 ; var a number [EBP-4]
    push scan_int ; endereço de memória de suporte
    push format_in ; formato de entrada (int)
    call scanf
    add esp, 8 ; remove os argumentos da pilha
    mov eax, dword [scan_int] ; retorna o valor lido em EAX
    mov [ebp-4], eax ; a = eax
    mov eax, [ebp-4] ; recupera a
    push eax ; empilha valor do print
    push format_out ; formato int de saída
    call printf
    add esp, 8 ; limpa os argumentos

    ; aqui termina o código gerado

    mov esp, ebp ; reestabelece a pilha
    pop ebp

    ; chamada da interrupcao de saida (Linux)
    mov eax, 1
    xor ebx, ebx
    int 0x80
