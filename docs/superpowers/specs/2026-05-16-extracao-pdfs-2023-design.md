# Spec: Melhoria da Extração de PDFs 2023 — Suporte ao Formato Tabular TCE-AL

**Data:** 2026-05-16
**Status:** Aprovado
**Escopo:** Estender o leitor automático (`parse_2024`) para reconhecer o formato de tabela dos relatórios de 2023, evitando que relatórios grandes sejam truncados pelo Gemini.

---

## Contexto

O sistema extrai achados de auditoria de PDFs do TCE-AL em duas etapas:

1. **Leitor automático** (`parse_2024.py`): rápido, sem custo de API, funciona para PDFs com tabela de formato conhecido.
2. **Gemini (IA do Google)** (`parse_legacy.py`): plano B para formatos desconhecidos; tem limite de texto por chamada.

Os PDFs de 2023 têm tabelas bem estruturadas com cabeçalho explícito, mas com nomes de colunas diferentes dos que o leitor automático conhecia. Por isso, todos os 2023 eram enviados ao Gemini — que truncava relatórios grandes. Exemplo concreto: Canapi 2023 tem 33 achados, mas apenas 20 foram extraídos por causa do corte de texto.

---

## Problema detalhado

### Nomes de colunas diferentes

O leitor automático reconhecia as colunas pelo nome. Os relatórios de 2023 usam nomes ligeiramente diferentes:

| O que o leitor conhecia | Como aparece nos PDFs de 2023 |
|---|---|
| "Descrição" / "Achado" | "Situação identificada" |
| "Tipo" | "Classificação do Achado" |
| "Situação" | "Situação após análise do Contraditório" |

Por não reconhecer esses nomes, o leitor retornava "não encontrei nada" e o Gemini assumia o trabalho.

### Tabelas com múltiplas páginas (exceção)

Em alguns relatórios, a tabela começa em uma página com cabeçalho e continua em páginas seguintes sem repetir o cabeçalho. Hoje o leitor para de ler quando não encontra cabeçalho. Isso precisa ser tratado como exceção.

### Título de seção com sufixo "– III"

O leitor usa um padrão de texto para localizar a seção correta do relatório. Alguns PDFs de 2023 têm o título `"12.1. Irregularidades, Inconsistências e Impropriedades – III"` com o sufixo `"– III"` que o padrão atual não reconhecia.

### Limite de texto do Gemini

O limite atual de 40.000 caracteres pode ser insuficiente para relatórios grandes com formatos ainda desconhecidos. Dobrar para 80.000 como rede de segurança.

---

## Solução (Opção C — Híbrido)

### Parte 1 — Ensinar o leitor os nomes de 2023 (`parse_2024.py`)

Adicionar os nomes das colunas de 2023 como sinônimos válidos. O leitor passa a entender que "Situação identificada" é a descrição do achado, que "Classificação do Achado" é o tipo, e que "Situação após análise do Contraditório" é a situação final.

Nenhuma lógica nova é necessária — apenas ampliar a lista de nomes reconhecidos.

### Parte 2 — Continuar lendo páginas sem cabeçalho (exceção) (`parse_2024.py`)

Quando o leitor encontrar um cabeçalho válido na primeira página de uma tabela, ele memoriza a ordem das colunas. Se em uma página seguinte a tabela não tiver cabeçalho mas claramente continuar os dados (primeira célula contém um código como "III.21"), o leitor reutiliza a ordem memorizada.

Esse comportamento é um tratamento de exceção — a regra continua sendo ler o cabeçalho normalmente.

### Parte 3 — Corrigir o padrão do título de seção (`parse_2024.py`)

Ajustar o padrão de busca para aceitar o sufixo opcional `"– III"` no título da seção, sem afetar os demais casos.

### Parte 4 — Ampliar limite do Gemini (`parse_legacy.py`)

Aumentar `_MAX_CHARS_GEMINI` de 40.000 para 80.000 caracteres. Isso não afeta os PDFs de 2023 (que passarão a ser processados pelo leitor automático), mas protege contra truncamento em formatos desconhecidos futuros.

---

## Fluxo após a mudança

```
PDF de 2023 com tabela explícita
  → parse_2024 reconhece cabeçalho (com novos sinônimos)
  → extrai todos os achados, incluindo páginas seguintes sem cabeçalho
  → resultado completo, sem custo de API

PDF de formato desconhecido (sem tabela estruturada)
  → parse_2024 retorna "não encontrei"
  → Gemini recebe até 80.000 caracteres (antes: 40.000)
  → resultado completo mesmo para relatórios grandes
```

---

## Arquivos afetados

| Arquivo | O que muda |
|---|---|
| `src/parse_2024.py` | Novos sinônimos de colunas; propagação de mapeamento para páginas sem cabeçalho; fix no regex do título |
| `src/parse_legacy.py` | `_MAX_CHARS_GEMINI` de 40.000 para 80.000 |

---

## Critérios de sucesso

1. Canapi 2023: extrai 33 achados (hoje: 20).
2. Todos os PDFs de 2023 com tabela explícita (que é a regra) passam a usar `"parser_2024"` no campo `fonte_extracao`.
3. Os achados de 2023 têm `tipo`, `descricao` e `situacao` preenchidos corretamente (não trocados entre si).
4. PDFs de 2024 continuam funcionando sem regressão.
5. O cache precisa ser limpo (`--forcar`) para os PDFs de 2023 após a mudança, para que sejam reprocessados com o novo leitor.

---

## Observações operacionais

- Após implementar, rodar `uv run python -m src.cli extrair --ano 2023 --forcar` para reprocessar os 2023 com o novo leitor.
- Validar os achados extraídos do Canapi contra o PDF original antes de publicar.
- O cache dos PDFs de 2024 não precisa ser refeito.
