### Objetivo do Projeto

Produzir um mapa visual mostrando padrões de citações entre países em casos de litigância climática, especificamente destacando que os EUA são regularmente citados mas raramente citam outros países. O entregável inclui uma versão estética do mapa acompanhada de 2-3 parágrafos descritivos e reflexivos sobre o fenômeno.

### Fonte de Dados e Contexto

A equipe está trabalhando com a base de dados do Sabin (Centro de Mudança Climática), que contém documentos de casos de litigância climática com metadados incluindo Case ID e Document ID. Foram identificadas inconsistências e erros nos metadados existentes, particularmente em classificações de tipo de documento e país.

### Abordagem Metodológica

**Preocupações com Qualidade:**

A equipe expressou receio sobre usar os dados existentes sem refinamento devido à importância da publicação. Discussão sobre potencial reclassificação dos metadados do Sabin, mas decisão de focar apenas no necessário devido a restrições de tempo e budget.

**Estratégia de Extração de Citações:**

Debate sobre duas abordagens: (1) buscar todas as citações e depois filtrar, versus (2) usar knowledge base para buscar citações específicas de casos conhecidos no Sabin. A segunda abordagem foi considerada mais eficiente, similar a projeto anterior bem-sucedido.

**Fluxo de Identificação:**

- Primeiro, identificar todas as citações jurisprudenciais no documento
- Segundo, verificar se a citação está na base do Sabin
- Terceiro, se estiver no Sabin, usar os metadados para identificar país de origem
- Comparar origem do documento analisado com origem da citação para determinar se é estrangeira

**Considerações sobre Snippets:**

Discussão sobre extrair snippets (trechos) das citações para facilitar validação posterior, usando método de contagem de caracteres ao invés de fazer a LLM processar e reescrever as citações. Decisão de só extrair snippets das citações que serão mantidas após filtragem.

### Pipeline de Processamento (Steps Definidos)

**Step 0 - Database Initialization:**

- Adicionar Case ID às tabelas
- Adaptar scripts posteriores para usar IDs

**Step 1 - Download e Preparação:**

- Versão atualizada da tabela
- Download dos PDFs

**Step 2 - Conversão:**

- Converter PDFs para Markdown

**Step 3 - Análise com LLM (fase complexa):**

- Task 1: Identificar todas as citações jurisprudenciais no documento
- Task 2: Verificar quais citações correspondem a casos do Sabin
- Task 3: Comparar origem do documento com origem das citações para identificar citações estrangeiras
- Usar todo o contexto disponível e knowledge base para análise eficiente

**Step 4 - Export e Validação:**

- Gerar tabela/Excel para validação manual

**Resultado Final:**

- Contagem de citações por país
- Identificação de top 5 países citantes e citados
- Mapa visual dos padrões de citação

### Considerações Técnicas

**Budget e Tokens:**

Preocupação com custo de tokens para processamento via LLM. Tokens são previsíveis e preço por token é conhecido, mas volume total é incerto.

**Knowledge Base vs. Processamento Completo:**

Discussão sobre usar knowledge base indexado que permite buscar apenas informações relevantes ao invés de processar tudo em cada batch. Knowledge base seria grande (~2000 casos) mas indexação permitiria buscas eficientes.

**Limitações de Contexto:**

Reconhecimento que projeto anterior com ~25 casos coube em uma única janela de contexto, mas escala atual requer processamento em batches.

### Divisão de Trabalho

Lucas se sente confortável para fazer Steps 0, 1 e 2, incluindo trabalho com database e Aegis. O parceiro focará no Step 3 mais complexo que envolve a análise com LLM.

Ambos reconhecem que trabalho é iterativo com erros e bugs esperados, requerendo revisão e ajustes contínuos. O parceiro precisará revisar o trabalho de Lucas para entender e dar continuidade.

### Comunicação e Cronograma

Estabelecida rotina de touchpoints diários com reunião de manhã para alinhamento e revisão fim do dia. Canal Teams/Discord ficará aberto durante horário de trabalho para comunicação contínua e suporte sob demanda.

Lucas estará disponível a partir de amanhã cedo e criará a sala de reunião. Trabalho começa imediatamente com objetivo de "harmonizar" o projeto.

### Disclaimer e Qualidade

Importante incluir disclaimer sobre margem de erro na análise, reconhecendo que processamento não será perfeito mas estará dentro do escopo do que está no Sabin. A equipe está mais confortável apresentando top 5 do que números absolutos detalhados devido a possíveis inconsistências.
