"""Validadores e normalizadores compartilhados do app accounts."""


def only_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def is_valid_cpf(cpf: str) -> bool:
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    first_sum = sum(int(cpf[idx]) * (10 - idx) for idx in range(9))
    first_digit = ((first_sum * 10) % 11) % 10
    if first_digit != int(cpf[9]):
        return False

    second_sum = sum(int(cpf[idx]) * (11 - idx) for idx in range(10))
    second_digit = ((second_sum * 10) % 11) % 10
    return second_digit == int(cpf[10])


def is_valid_cnpj(cnpj: str) -> bool:
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    first_total = sum(int(cnpj[idx]) * first_weights[idx] for idx in range(12))
    first_remainder = first_total % 11
    first_digit = 0 if first_remainder < 2 else 11 - first_remainder
    if first_digit != int(cnpj[12]):
        return False

    second_weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_total = sum(int(cnpj[idx]) * second_weights[idx] for idx in range(13))
    second_remainder = second_total % 11
    second_digit = 0 if second_remainder < 2 else 11 - second_remainder
    return second_digit == int(cnpj[13])
