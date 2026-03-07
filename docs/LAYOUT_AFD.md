# Layout AFD — Arquivo Fonte de Dados
**Portaria MTP nº 671/2021 — Anexo V**  
**Fonte oficial:** https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/fiscalizacao-do-trabalho/leiaute-do-arquivo-fonte-de-dados-afd.pdf  

---

## Regras Gerais do Arquivo

1. Formato texto, codificado em **ISO 8859-1**
2. Cada linha corresponde a um registro, terminando com **CR LF** (caracteres ASCII 13 e 10)
3. Registros ordenados pelo **NSR** (Número Sequencial de Registro)
4. Sem linhas em branco
5. Preenchimento dos campos iniciado pela **esquerda** — posições não utilizadas preenchidas com **espaço**
6. Para registros tipos "1" a "5": gravar **CRC-16** (padrão CRC16 CCITT-TRUE / CRC-16/KERMIT)
7. Para o registro tipo "7": usar **SHA-256** no campo código hash

### Tipos de dados
| Tipo | Formato |
|---|---|
| N | Numérico |
| A | Alfanumérico |
| D | Data: `AAAA-MM-dd` |
| DH | Data e hora: `AAAA-MM-ddThh:mm:00ZZZZZ` (ex: `2021-04-27T16:44:00-0300`) |

### Nomenclatura do arquivo (REP-P)
```
AFD{numero_registro_INPI}{CNPJ_empregador}REP_P.txt
```

---

## Registro Tipo "1" — Cabeçalho

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | `000000000` (fixo) |
| 2 | 010–010 | 1 | N | Tipo do registro — preencher com `1` |
| 3 | 011–011 | 1 | N | Tipo de identificador do empregador: `1`=CNPJ, `2`=CPF |
| 4 | 012–025 | 14 | N | CNPJ ou CPF do empregador |
| 5 | 026–039 | 14 | N | CNO ou CAEPF, quando existir |
| 6 | 040–189 | 150 | A | Razão social ou nome do empregador |
| 7 | 190–206 | 17 | N | Número de registro no INPI (REP-P) |
| 8 | 207–216 | 10 | D | Data inicial dos registros no arquivo |
| 9 | 217–226 | 10 | D | Data final dos registros no arquivo |
| 10 | 227–250 | 24 | DH | Data e hora da geração do arquivo |
| 11 | 251–253 | 3 | N | Versão do leiaute. Preencher com `003` |
| 12 | 254–254 | 1 | N | Tipo de identificador do fabricante/desenvolvedor: `1`=CNPJ, `2`=CPF |
| 13 | 255–268 | 14 | N | CNPJ ou CPF do fabricante ou desenvolvedor do REP |
| 14 | 269–298 | 30 | A | Modelo (REP-C) — deixar em branco para REP-P |
| 15 | 299–302 | 4 | A | CRC-16 do registro (hexadecimal sem `0x`) |

**Tamanho total da linha: 302 caracteres + CRLF**

---

## Registro Tipo "2" — Inclusão ou Alteração da Identificação da Empresa no REP

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | N | Tipo do registro — preencher com `2` |
| 3 | 011–034 | 24 | DH | Data e hora da gravação do registro |
| 4 | 035–048 | 14 | N | CPF do responsável pela inclusão ou alteração |
| 5 | 049–049 | 1 | N | Tipo de identificador do empregador: `1`=CNPJ, `2`=CPF |
| 6 | 050–063 | 14 | N | CNPJ ou CPF do empregador |
| 7 | 064–077 | 14 | N | CNO ou CAEPF, quando existir |
| 8 | 078–227 | 150 | A | Razão social ou nome do empregador |
| 9 | 228–327 | 100 | A | Local de prestação de serviços |
| 10 | 328–331 | 4 | A | CRC-16 do registro (hexadecimal sem `0x`) |

**Tamanho total da linha: 331 caracteres + CRLF**

---

## Registro Tipo "3" — Marcação de Ponto para REP-C e REP-A

> ⚠️ Não utilizado no REP-P. Documentado apenas para referência.

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | A | Tipo do registro — preencher com `3` |
| 3 | 011–034 | 24 | DH | Data e hora da marcação de ponto |
| 4 | 035–046 | 12 | N | CPF do empregado |
| 5 | 047–050 | 4 | A | CRC-16 do registro (hexadecimal sem `0x`) |

**Tamanho total da linha: 50 caracteres + CRLF**

---

## Registro Tipo "4" — Ajuste do Relógio

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | N | Tipo do registro — preencher com `4` |
| 3 | 011–034 | 24 | DH | Data e hora antes do ajuste |
| 4 | 035–058 | 24 | DH | Data e hora ajustada |
| 5 | 059–069 | 11 | N | CPF do responsável pela alteração |
| 6 | 070–073 | 4 | A | CRC-16 do registro (hexadecimal sem `0x`) |

**Tamanho total da linha: 73 caracteres + CRLF**

---

## Registro Tipo "5" — Inclusão, Alteração ou Exclusão de Empregado no REP

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | N | Tipo do registro — preencher com `5` |
| 3 | 011–034 | 24 | DH | Data e hora da gravação do registro |
| 4 | 035–035 | 1 | A | Tipo de operação: `I`=inclusão, `A`=alteração, `E`=exclusão |
| 5 | 036–047 | 12 | N | CPF do empregado |
| 6 | 048–099 | 52 | A | Nome do empregado |
| 7 | 100–103 | 4 | A | Demais dados de identificação do empregado |
| 8 | 104–114 | 11 | N | CPF do responsável pela alteração |
| 9 | 115–118 | 4 | A | CRC-16 do registro (hexadecimal sem `0x`) |

**Tamanho total da linha: 118 caracteres + CRLF**

---

## Registro Tipo "6" — Eventos Sensíveis do REP

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | N | Tipo do registro — preencher com `6` |
| 3 | 011–034 | 24 | DH | Data e hora da gravação do registro |
| 4 | 035–036 | 2 | N | Tipo de evento (ver tabela abaixo) |

### Tipos de Evento (REP-P)
| Código | Descrição |
|---|---|
| `02` | Retorno de energia |
| `07` | Disponibilidade de serviço |
| `08` | Indisponibilidade de serviço |

---

## ⭐ Registro Tipo "7" — Marcação de Ponto para REP-P

> Este é o registro central do nosso sistema. Toda marcação de ponto gera um registro tipo 7.

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | NSR |
| 2 | 010–010 | 1 | A | Tipo do registro — preencher com `7` |
| 3 | 011–034 | 24 | DH | Data e hora da marcação de ponto |
| 4 | 035–046 | 12 | N | CPF do empregado |
| 5 | 047–070 | 24 | DH | Data e hora de gravação do registro |
| 6 | 071–072 | 2 | N | Identificador do coletor da marcação (ver tabela abaixo) |
| 7 | 073–073 | 1 | N | `0`=marcação online, `1`=marcação offline |
| 8 | 074–137 | 64 | A | Código hash SHA-256 |

**Tamanho total da linha: 137 caracteres + CRLF**

### Identificadores do Coletor da Marcação
| Código | Descrição |
|---|---|
| `01` | Aplicativo mobile ← **nosso caso** |
| `02` | Browser (navegador internet) |
| `03` | Aplicativo desktop |
| `04` | Dispositivo eletrônico |
| `05` | Outro dispositivo eletrônico não especificado |

### Cálculo do Hash SHA-256 (campo 8)
O hash é calculado com base na concatenação dos seguintes campos do próprio registro:
1. NSR (campo 1)
2. Tipo do registro (campo 2)
3. Data e hora da marcação (campo 3)
4. CPF do empregado (campo 4)
5. Data e hora da gravação (campo 5)
6. Identificador do coletor (campo 6)
7. Indicação online/offline (campo 7)
8. Hash SHA-256 do **registro anterior** (quando existir — encadeamento)

---

## Registro Tipo "9" — Trailer

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–009 | 9 | N | `999999999` (fixo) |
| 2 | 010–018 | 9 | N | Quantidade de registros tipo "2" |
| 3 | 019–027 | 9 | N | Quantidade de registros tipo "3" |
| 4 | 028–036 | 9 | N | Quantidade de registros tipo "4" |
| 5 | 037–045 | 9 | N | Quantidade de registros tipo "5" |
| 6 | 046–054 | 9 | N | Quantidade de registros tipo "6" |
| 7 | 055–063 | 9 | N | Quantidade de registros tipo "7" |
| 8 | 064–064 | 1 | N | Tipo do registro — preencher com `9` |

**Tamanho total da linha: 64 caracteres + CRLF**

---

## Assinatura Digital

| Campo | Posição | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | 001–100 | 100 | A | Assinatura digital |

> Para REP-A e REP-P: preencher com o texto literal `ASSINATURA_DIGITAL_EM_ARQUIVO_P7S` e espaços à direita até completar 100 caracteres. O arquivo `.p7s` deve ser gerado separado, nomeado como `{nome_do_afd}.p7s`. Padrão: **CAdES (CMS Advanced Electronic Signature)**.

---

## Exemplo de Arquivo AFD REP-P

```
000000000 1 1 12345678000195              00000000000000Empresa Teste Ltda                                                                            0001XXXXXXXXXINPI 2024-01-012024-01-312024-01-31T08:00:00-03000031 12345678000195              003AFD
000000001 2 2024-01-31T07:55:00-0300 12345678901234 1 12345678000195              00000000000000Empresa Teste Ltda                                         Rua das Flores, 100, SP                                                                             XXXX
000000002 7 2024-01-31T08:00:00-0300 012345678901   2024-01-31T08:00:01-0300 01 0 a3f1c2d4e5b6a7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3
999999999 000000001 000000000 000000000 000000000 000000000 000000001 9
ASSINATURA_DIGITAL_EM_ARQUIVO_P7S                                                                   
```

---

## Notas Importantes para Implementação

- O arquivo deve ter **exatamente** o número de caracteres especificado por linha — sem mais, sem menos
- Para REP-P, registros de marcação são sempre **tipo 7** (nunca tipo 3)
- O hash SHA-256 é **encadeado**: cada registro referencia o hash do anterior, garantindo integridade da cadeia
- O arquivo `.p7s` de assinatura é **separado** do `.txt` mas deve acompanhá-lo sempre
- Encoding obrigatório: **ISO 8859-1** (não UTF-8)
- Quebra de linha: **CRLF** (Windows-style) — não apenas LF
