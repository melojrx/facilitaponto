# Layout AEJ — Arquivo Eletrônico de Jornada
**Portaria MTP nº 671/2021 — Anexo VI**  
**Fonte oficial:** https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/fiscalizacao-do-trabalho/leiaute-do-arquivo-eletronico-de-jornada-aej.pdf  

---

## Regras Gerais do Arquivo

1. Formato texto, codificado em **ISO 8859-1**
2. Cada linha corresponde a um registro, terminando com **CR LF** (caracteres ASCII 13 e 10)
3. Ao final de cada campo, com exceção do último campo do registro, deve ser inserido o delimitador **`|`** (pipe)
4. Sem linhas em branco
5. Preenchimento dos campos iniciado pela **esquerda** — posições não utilizadas preenchidas com **espaço**

### Diferença fundamental em relação ao AFD
O AFD é posicional (tamanho fixo por campo). O AEJ usa **pipe `|` como delimitador** entre campos — estrutura mais flexível.

### Tipos de dados
| Tipo | Formato |
|---|---|
| N | Numérico |
| A | Alfanumérico |
| H | Hora: `hhmm` |
| D | Data: `AAAA-MM-dd` |
| DH | Data e hora: `AAAA-MM-ddThh:mm:00ZZZZZ` (ex: `2021-04-27T16:44:00-0300`) |

### Ordem dos registros no arquivo
```
01 → Cabeçalho (1 registro)
02 → REPs utilizados (1 ou mais)
03 → Vínculos / Empregados (1 por funcionário)
04 → Horários contratuais (1 por tipo de jornada)
05 → Marcações (N registros — o core do arquivo)
06 → Matrícula eSocial (quando funcionário tem mais de um vínculo — opcional)
07 → Ausências e banco de horas (quando houver)
08 → Identificação do PTRP (1 registro — dados do nosso sistema)
99 → Trailer (1 registro)
Assinatura digital (última linha)
```

---

## Registro Tipo "01" — Cabeçalho

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `01` |
| 2 | tpIdtEmpregador | 1 | N | `1`=CNPJ, `2`=CPF |
| 3 | idtEmpregador | 11 ou 14 | N | CNPJ ou CPF do empregador |
| 4 | caepf | 14 | N | CAEPF, caso exista |
| 5 | cno | 12 | N | CNO, caso exista |
| 6 | razaoOuNome | 1 a 150 | A | Razão social ou nome do empregador |
| 7 | dataInicialAej | 10 | D | Data inicial dos registros no AEJ |
| 8 | dataFinalAej | 10 | D | Data final dos registros no AEJ |
| 9 | dataHoraGerAej | 24 | DH | Data e hora da geração do AEJ |
| 10 | versaoAej | 3 | A | Versão do leiaute. Preencher com `001` |

**Exemplo:**
```
01|1|12345678000195||Empresa Teste Ltda|2024-01-01|2024-01-31|2024-01-31T23:59:00-0300|001
```

---

## Registro Tipo "02" — REPs Utilizados

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `02` |
| 2 | idRepAej | 1 a 9 | N | Identificador do REP no AEJ (sequencial interno) |
| 3 | tpRep | 1 | N | `1`=REP-C, `2`=REP-A, `3`=REP-P |
| 4 | nrRep | 17 | N | Número de registro no INPI (REP-P) |

**Exemplo (REP-P):**
```
02|1|3|00001XXXXXXXXINPI
```

---

## Registro Tipo "03" — Vínculos (Empregados)

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `03` |
| 2 | idtVinculoAej | 1 a 9 | N | Identificador do vínculo no AEJ (sequencial interno por funcionário) |
| 3 | cpf | 11 | N | CPF do empregado |
| 4 | nomeEmp | 1 a 150 | A | Nome do empregado |

**Exemplo:**
```
03|1|01234567890|João da Silva
03|2|09876543210|Maria Souza
```

---

## Registro Tipo "04" — Horário Contratual

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `04` |
| 2 | codHorContratual | 1 a 30 | A | Código do horário contratual no AEJ |
| 3 | durJornada | 1 a 12 | N | Duração da jornada em **minutos** |
| 4 | hrEntrada01 | 4 | H | Hora da primeira entrada (`hhmm`) |
| 5 | hrSaida01 | 4 | H | Hora da primeira saída (`hhmm`) |
| 6 | hrEntrada02 | 0 ou 4 | H | Hora da segunda entrada (opcional) |
| 7 | hrSaida02 | 0 ou 4 | H | Hora da segunda saída (opcional) |

> Se a jornada tiver mais de 2 pares entrada/saída, adicionar campos `hrEntrada03`, `hrSaida03`, etc. em sequência.
> Para jornada noturna, `durJornada` deve considerar a **redução da hora noturna**.

**Exemplo (jornada 8h, das 08:00 às 12:00 e das 13:00 às 17:00):**
```
04|CH001|480|0800|1200|1300|1700
```

**Exemplo (jornada 12x36):**
```
04|CH12X36|720|0700|1900
```

---

## ⭐ Registro Tipo "05" — Marcações

> Este é o registro central do AEJ. Representa cada marcação de ponto tratada (pós-processamento do AFD).

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `05` |
| 2 | idtVinculoAej | 1 a 9 | N | ID do vínculo (informado no tipo 03) |
| 3 | dataHoraMarc | 24 | DH | Data e hora da marcação |
| 4 | idRepAej | 0 a 9 | N | ID do REP no AEJ (informado no tipo 02) |
| 5 | tpMarc | 1 | A | Tipo da marcação (ver tabela abaixo) |
| 6 | seqEntSaida | 3 | N | Número sequencial do par entrada/saída |
| 7 | fonteMarc | 1 | A | Fonte da marcação (ver tabela abaixo) |
| 8 | codHorContratual | 0 a 30 | A | Código do horário contratual (obrigatório na primeira entrada — tpMarc=E e seqEntSaida=1) |
| 9 | motivo | 0 a 150 | A | Motivo (obrigatório quando tpMarc=D ou fonteMarc=I) |

### Tipos de Marcação (tpMarc)
| Código | Descrição |
|---|---|
| `E` | Marcação de entrada |
| `S` | Marcação de saída |
| `D` | Marcação desconsiderada |

### Fontes de Marcação (fonteMarc)
| Código | Descrição |
|---|---|
| `O` | Marcação original do REP |
| `I` | Marcação incluída manualmente |
| `P` | Marcação pré-assinalada |
| `X` | Marcação incluída (horário predefinido) para ponto por exceção |
| `T` | Outras fontes de marcação |

### Exemplo de sequência de marcações para 1 funcionário (jornada normal):
```
05|1|2024-01-31T08:02:00-0300|1|E|1|O|CH001|
05|1|2024-01-31T12:00:00-0300|1|S|1|O||
05|1|2024-01-31T13:05:00-0300|1|E|2|O||
05|1|2024-01-31T17:00:00-0300|1|S|2|O||
```

### Exemplo com marcação desconsiderada:
```
05|1|2024-01-31T07:45:00-0300|1|D|1|O||Marcação antecipada desconsiderada por política da empresa
```

---

## Registro Tipo "06" — Matrícula eSocial (opcional)

> Utilizar apenas quando o funcionário possui **mais de um vínculo** no AEJ.

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `06` |
| 2 | idtVinculoAej | 1 a 9 | N | ID do vínculo (informado no tipo 03) |
| 3 | matEsocial | 1 a 30 | A | Matrícula do vínculo no eSocial |

---

## Registro Tipo "07" — Ausências e Banco de Horas

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `07` |
| 2 | idtVinculoAej | 1 a 9 | N | ID do vínculo (informado no tipo 03) |
| 3 | tipoAusenOuComp | 1 | N | Tipo da ausência ou compensação (ver tabela abaixo) |
| 4 | data | 10 | D | Data da ausência ou compensação |
| 5 | qtMinutos | 0 a 12 | N | Quantidade de minutos (obrigatório se tipoAusenOuComp=3) |
| 6 | tipoMovBH | 0 ou 1 | N | Tipo de movimento banco de horas (obrigatório se tipoAusenOuComp=3) |

### Tipos de Ausência ou Compensação
| Código | Descrição |
|---|---|
| `1` | Descanso Semanal Remunerado (DSR) |
| `2` | Falta não justificada |
| `3` | Movimento no banco de horas |
| `4` | Folga compensatória de feriado |

### Tipos de Movimento no Banco de Horas (tipoMovBH)
| Código | Descrição |
|---|---|
| `1` | Inclusão de horas no banco |
| `2` | Compensação de horas do banco |

**Exemplo (DSR):**
```
07|1|1|2024-01-28|
```

**Exemplo (banco de horas — inclusão de 60 minutos):**
```
07|1|3|2024-01-31|60|1
```

---

## ⭐ Registro Tipo "08" — Identificação do PTRP

> Dados do nosso sistema (Programa de Tratamento de Registro de Ponto).  
> **Deve ser preenchido com os dados reais do sistema cadastrado no INPI.**

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `08` |
| 2 | nomeProg | 1 a 150 | A | Nome do PTRP (nome do nosso sistema) |
| 3 | versaoProg | 1 a 8 | A | Versão do PTRP |
| 4 | tpIdtDesenv | 1 | N | `1`=CNPJ, `2`=CPF do desenvolvedor |
| 5 | idtDesenv | 11 ou 14 | N | CNPJ ou CPF do desenvolvedor |
| 6 | razaoNomeDesenv | 1 a 150 | A | Razão social ou nome do desenvolvedor |
| 7 | emailDesenv | 1 a 50 | N | E-mail do desenvolvedor |

**Exemplo:**
```
08|PontoFacial|1.0.0|1|12345678000195|Empresa Desenvolvedora Ltda|contato@empresa.com
```

---

## Registro Tipo "99" — Trailer

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | tipoReg | 2 | N | Preencher com `99` |
| 2 | qtRegistrosTipo01 | 1 a 9 | N | Quantidade de registros tipo 01 |
| 3 | qtRegistrosTipo02 | 1 a 9 | N | Quantidade de registros tipo 02 |
| 4 | qtRegistrosTipo03 | 1 a 9 | N | Quantidade de registros tipo 03 |
| 5 | qtRegistrosTipo04 | 1 a 9 | N | Quantidade de registros tipo 04 |
| 6 | qtRegistrosTipo05 | 1 a 9 | N | Quantidade de registros tipo 05 |
| 7 | qtRegistrosTipo06 | 1 a 9 | N | Quantidade de registros tipo 06 |
| 8 | qtRegistrosTipo07 | 1 a 9 | N | Quantidade de registros tipo 07 |
| 9 | qtRegistrosTipo08 | 1 a 9 | N | Quantidade de registros tipo 08 |

**Exemplo:**
```
99|1|1|2|1|8|0|1|1
```

---

## Assinatura Digital

| # | Nome do Campo | Tamanho | Tipo | Conteúdo |
|---|---|---|---|---|
| 1 | assinDigital | 100 | A | Assinatura digital |

> Preencher com o texto literal `ASSINATURA_DIGITAL_EM_ARQUIVO_P7S` e espaços à direita até completar 100 caracteres.  
> O arquivo `.p7s` deve ser gerado separado, nomeado como `{nome_do_aej}.p7s`.  
> Padrão: **CAdES (CMS Advanced Electronic Signature)**.

---

## Exemplo Completo de Arquivo AEJ

```
01|1|12345678000195||Empresa Teste Ltda|2024-01-31|2024-01-31|2024-01-31T23:59:00-0300|001
02|1|3|00001XXXXXXXXINPI     
03|1|01234567890|João da Silva
03|2|09876543210|Maria Souza
04|CH001|480|0800|1200|1300|1700
05|1|2024-01-31T08:02:00-0300|1|E|1|O|CH001|
05|1|2024-01-31T12:00:00-0300|1|S|1|O||
05|1|2024-01-31T13:05:00-0300|1|E|2|O||
05|1|2024-01-31T17:01:00-0300|1|S|2|O||
05|2|2024-01-31T07:58:00-0300|1|E|1|O|CH001|
05|2|2024-01-31T12:02:00-0300|1|S|1|O||
05|2|2024-01-31T13:00:00-0300|1|E|2|O||
05|2|2024-01-31T17:00:00-0300|1|S|2|O||
07|1|1|2024-01-28|
07|2|1|2024-01-28|
08|PontoFacial|1.0.0|1|12345678000195|Empresa Desenvolvedora Ltda|contato@empresa.com
99|1|1|2|1|8|0|2|1
ASSINATURA_DIGITAL_EM_ARQUIVO_P7S                                                                   
```

---

## Notas Importantes para Implementação

- **AFD vs AEJ:** o AFD registra batidas brutas (como vieram do REP). O AEJ registra a jornada tratada (pós-processamento com pares entrada/saída, desconsiderações, banco de horas).
- O AEJ é gerado pelo **PTRP** (nosso sistema), não pelo REP diretamente.
- O campo `seqEntSaida` é fundamental: representa a ordem do par entrada/saída daquele dia. Entrada da manhã = 1, saída do almoço = 1, entrada do almoço = 2, saída da tarde = 2.
- Marcações **desconsideradas** (tpMarc=`D`) devem sempre ter o campo `motivo` preenchido.
- Marcações **incluídas manualmente** (fonteMarc=`I`) também exigem `motivo`.
- Encoding obrigatório: **ISO 8859-1** (não UTF-8)
- Quebra de linha: **CRLF** (Windows-style)
- O pipe `|` é o delimitador de campos — não usar espaços ao redor
