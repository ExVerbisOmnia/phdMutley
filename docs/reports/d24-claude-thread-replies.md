# D24 — Claude's Thread Replies

Respostas para colar nos threads do Google Docs onde fui mencionado (@claude).
Cada resposta está rotulada pelo ID do comment que a dispara.

---

## Thread C7→C8→C9 — Lista de exclusão (o que NÃO extrair)

**Colar como resposta ao C9 (Gus: "@claude")**

> Lucas tem razão — a abordagem atual lista o que NÃO extrair (tratados, estatutos, livros...), que é um conjunto infinito. A instrução mais robusta e simples é inverter a lógica:
> 
> **"Extract ONLY references to judicial decisions (court cases). For each reference, verify it is a judgment, order, opinion, or advisory opinion issued by a court or tribunal — not a treaty, statute, regulation, academic article, or any other type of legal instrument."**
> 
> Em vez de enumerar exclusões, definimos o critério de inclusão. O LLM é muito melhor em checar "isso é uma decisão judicial?" do que lembrar uma lista longa de exclusões. Mantemos uma lista curta de falsos positivos comuns (tratados, estatutos, artigos acadêmicos) como *exemplos ilustrativos*, não como a regra em si.
> 
> Proposta: trocar a seção "What NOT to Extract" por uma definição positiva + lista curta de exemplos de falsos positivos.

---

## Thread C15→C16→C17 — Sabin Filter (complexidade do matching)

**Colar como resposta ao C17 (Gus: "@claude")**

> Concordo com o Lucas — o problema principal não é a complexidade do algoritmo em si, mas a **falta de transparência**. Se o filtro faz match de "Urgenda" com "Urgenda Foundation v. State of the Netherlands" com score 0.72, a pergunta é: esse match está certo?
> 
> Proposta: manter a lógica de matching, mas reestruturar a saída para ser **advisory** (não hard-discard):
> 
> - Coluna A: `raw_extracted_case_name` — exatamente o que o LLM extraiu (intocado)
> - Coluna B: `sabin_matched_case_name` — o case do Sabin que deu match (ou NULL)
> - Coluna C: `sabin_match_score` — score de similaridade
> - Coluna D: `sabin_match_method` — "exact" / "fuzzy_0.72" / etc.
> 
> Assim o Lucas pode filtrar por score, revisar matches borderline, e aceitar ou rejeitar. O filtro vira uma recomendação que o domain expert audita, não uma caixa-preta que descarta silenciosamente.

---

## Thread C33→C34→C35 — Seção D17 (Reporting) no documento

**Colar como resposta ao C35 (Gus: "@claude = por que incluiu esse item aqui?")**

> Incluí D17 (proporções relativas) e D22 (contagem por documento) porque ambos afetam como o pipeline *estrutura* sua saída. Mas vocês têm razão: D17 é puramente interpretativo — não afeta nenhum código. D22 fica porque está implementado na lógica de classificação (`COUNT(DISTINCT case_name)`). Vou remover D17 da próxima versão do documento.

---

## Thread C40→C41→C42 — Uso do Gemini 2.5 Pro

**Colar como resposta ao C42 (Gus: "@claude = opine sobre isso")**

> Análise por fase onde usamos o Pro:
> 
> | Fase             | Tarefa                               | Modelo Atual | Complexidade                        |
> | ---------------- | ------------------------------------ | ------------ | ----------------------------------- |
> | Phase 3 Tier 2   | Identificar origem (país/corte)      | **Pro**      | Pattern matching + knowledge recall |
> | Phases 2A, 2B, 5 | Extração, classificação, verificação | Flash        | Adequado                            |
> 
> Para **identificação de origem**: a tarefa é "dado `[2017] UKSC 5`, identificar que é do Reino Unido". Isso é pattern matching — Flash dá conta. Pro é overkill. Diferença de custo: Pro é ~8x mais caro por token.
> 
> Onde Pro **agregaria valor**: na fase de **verificação/revisão** (Phase 5), onde decidir se "Wells" no texto se refere a "R(Wells) v Secretary of State" (caso judicial) vs. "poços exploratórios" (substantivo) requer compreensão contextual mais profunda.
> 
> Proposta: downgrade Phase 3 Tier 2 para **Flash** (economia de ~87% no custo de origin ID). Se adicionarmos um "deep review" pass para citações flagged, aí sim usar Pro.
> 
> Obs: combinando com a decisão de dropar Tiers 1/1.5 (C28/C29), dependemos mais do LLM para origin ID — mas a Flash cost torna isso viável.

---

## Thread C30→C31→C32 — Revisão da tabela Global North/South

**Colar como resposta ao C32 (Gus: "@claude = revise essa tabela...")**

> Fiz uma pesquisa completa usando UNCTAD, UN WESP, Setzer & Higham (LSE/Grantham), Sabin Center, e Britannica. Achei um **bug crítico**: a lista existe em 3 locais no código com valores diferentes:
> 
> - `populate_metadata.py` — 28 códigos ISO (inclui POL, CZE, HUN, ROU, ISR)
> - `extract_citations.py:get_source_region()` — 26 nomes de países (FALTAM Polônia, Rep. Tcheca, Hungria, Romênia, Israel)
> - `KNOWN_FOREIGN_COURTS` — regiões hardcoded por corte
> 
> O **mesmo país pode ser classificado diferentemente** dependendo do code path. Isso explica os erros que o Lucas mencionou (países da UE como Global South).
> 
> **Proposta (detalhes completos em `docs/reports/d24-comment-review-action-items.md`):**
> 
> 1. **Unificar** em uma única fonte em `config.py`, importar em todos os locais
> 2. **Expandir** de 26 para ~44 países:
>    - Adicionar 14 estados-membros da UE faltantes: Polônia, Rep. Tcheca, Hungria, Romênia, Bulgária, Croácia, Eslováquia, Eslovênia, Estônia, Letônia, Lituânia, Luxemburgo, Malta, Chipre
>    - Adicionar: Turquia, Rússia (com footnote — contested), Israel, Taiwan (contested)
> 3. **Remover** "European Union" e "Council of Europe" da lista Global North → reclassificar como "International" (consistente com o sistema sixfold)
> 4. **Manter** estados do Golfo (UAE, Arábia Saudita, Qatar) como Global South — unânime em todas as fontes
> 
> Fontes consultadas: UNCTAD geographic definition, UN WESP 37 developed economies, Setzer & Higham Global Trends reports (LSE), Tigre/Sabin Center Global South mapping (2024), UNEP Global Climate Litigation Report (2025), Britannica, World Population Review.

---

## Thread C18→C19→C20 / C21→C22→C23 / C24→C25→C26 — Artigo do Nollkaemper (Avoid/Align/Contest)

**Nota: esse comment apareceu 3 vezes no Google Docs (C18/C21/C24 são o mesmo comment do Lucas, C20/C23/C26 são a mesma resposta do Gus). Colar UMA VEZ, no primeiro thread (C20).**

**Colar como resposta ao C20 (Gus: "@claude = pesquise esse artigo...")**

> Artigo encontrado e sintetizado. Detalhes completos em: **`docs/reports/nollkaemper-avoid-align-contest-synthesis.md`**
> 
> **Citação:** Andre Nollkaemper, "Avoid, Align or Contest? An Examination of National Courts' Postures in International Climate Law Litigation," *Transnational Environmental Law*, Vol. 14(3), Nov 2025, pp. 469-499. DOI: 10.1017/S2047102525100058. Open Access.
> 
> **Tipologia (adaptada do ILA Study Group 2011-2016):**
> 
> - **AVOIDANCE:** Corte evita a questão de direito internacional climático (não-justiciabilidade, falta de standing, separação de poderes)
> - **ALIGNMENT:** Corte interpreta direito doméstico à luz do direito internacional climático (fair weather alignment, consubstantial alignment via direitos humanos/Paris Agreement, overriding alignment)
> - **CONTESTATION:** Corte engaja com o direito internacional mas rejeita ou reinterpreta (ex: Shell v Milieudefensie 2024)
> 
> Dataset: 148 casos, 109 com julgamento, avoidance é a postura dominante.
> 
> **Proposta de adaptação para Phase 2B (nível da citação, não do caso):**
> 
> | Categoria Atual    | Proposta    | Paralelo Nollkaemper | Definição                                                    |
> | ------------------ | ----------- | -------------------- | ------------------------------------------------------------ |
> | `parties_argument` | `invoked`   | (pré-postura)        | Citação relatada como argumento de parte                     |
> | `dismissed`        | `contested` | Contestation         | Corte engaja mas rejeita/distingue a citação                 |
> | `contributed`      | `aligned`   | Alignment            | Citação suporta o raciocínio da corte                        |
> | *(nova)*           | `avoided`   | Avoidance            | Citação mencionada mas corte declina engajamento substantivo |
> 
> Isso dá base acadêmica publicada (ILA Study Group → Nollkaemper 2025, TEL) para nossas categorias, enquanto preserva a granularidade citation-level que o pipeline precisa.
> 
> Obs: não consegui fazer download do PDF diretamente pro repositório (paywall/acesso institucional), mas a síntese completa está salva no repo.

---

*Fim das respostas. Cada bloco pode ser colado diretamente no thread correspondente do Google Docs.*
