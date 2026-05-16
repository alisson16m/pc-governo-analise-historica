# Guia de Revisão — review.csv

Este guia explica como editar o arquivo `data/review.csv` para corrigir ou confirmar os achados extraídos automaticamente dos PDFs.

## Fluxo de trabalho

1. Gerar o CSV: `uv run python -m src.cli revisar --gerar`
2. Abrir `data/review.csv` em um editor de planilhas (Excel, LibreOffice Calc, etc.)
3. Editar as linhas que precisam de correção
4. Marcar `revisado` como `true` nas linhas corrigidas
5. Salvar o arquivo (manter formato CSV com codificação UTF-8)
6. Aplicar as edições: `uv run python -m src.cli revisar --aplicar`
7. Reconstruir o site: `uv run python -m src.cli build`

## Colunas do arquivo

| Coluna | Pode editar? | Valores válidos | Exemplo |
|---|---|---|---|
| `relatorio_id` | **NÃO** | SHA-256 interno | `a3f8c1...` |
| `codigo` | **NÃO** | Código do achado | `III.01` |
| `municipio` | SIM | Nome do município de AL | `Maceió` |
| `ano_exercicio` | SIM | Ano com 4 dígitos | `2023` |
| `tipo` | SIM | Ver tabela abaixo | `Irregularidade` |
| `situacao` | SIM | Ver tabela abaixo | `sanado_total` |
| `descricao` | SIM | Texto livre | `Despesa sem...` |
| `recomendacao` | SIM | Texto livre ou vazio | |
| `determinacao` | SIM | Texto livre ou vazio | |
| `valor_financeiro` | SIM | Número decimal (ponto) ou vazio | `15000.00` |
| `houve_defesa` | SIM | `true` ou `false` | `true` |
| `revisado` | SIM | `true` ou `false` | `true` |

## Valores válidos para `tipo`

| Valor | Quando usar |
|---|---|
| `Irregularidade` | Infração a norma legal com potencial de dano |
| `Impropriedade` | Descumprimento de norma sem caracterizar dano |
| `Inconsistência` | Divergência entre documentos ou dados |

## Valores válidos para `situacao`

| Valor | Significado |
|---|---|
| `sanado_total` | Problema totalmente resolvido pelo gestor |
| `sanado_parcial` | Problema parcialmente resolvido |
| `afastado` | Achado afastado após análise do contraditório |
| `mantido` | Achado mantido após análise |
| `nao_consta` | Situação não informada no relatório |

## Regras importantes

- **Não altere** `relatorio_id` nem `codigo` — são as chaves que identificam cada achado no sistema.
- Apenas linhas com `revisado=true` serão aplicadas ao banco. Deixe `false` nas linhas que não precisam de alteração.
- O campo `valor_financeiro` usa **ponto** como separador decimal (ex: `15000.00`), não vírgula.
- Salve o arquivo em **UTF-8** para preservar caracteres especiais (ã, ç, é, etc.). No Excel: "Salvar como" → "CSV UTF-8 (delimitado por vírgulas)".

## Exemplo de linha editada

```
relatorio_id,codigo,municipio,ano_exercicio,tipo,situacao,...,revisado
a3f8c1...,III.03,Maceió,2023,Irregularidade,sanado_total,...,true
```
