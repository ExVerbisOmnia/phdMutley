# Meeting Summary — Touchpoint 7 Mar 2026 (18:07 GMT-3)

**Attendees:** Gustavo Rodriguez, Lucas Biasetton
**Duration:** ~19 minutes
**Context:** Evening touchpoint during social event. Pipeline extraction (Step E) at 98% completion on GCP VM.

---

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| **D16** | Count citations **per document** for Monday deliverable | If a document cites a foreign decision 15 times textually, count as 1 invocation — the *act* of invoking a foreign decision, not the number of textual references. More granular counting deferred to later thesis work. |
| **D17** | Use **relative proportions** (not absolute numbers) for public claims | Addresses Lucas's concern about making cautious claims in academic/public settings. E.g., "X% of identified citations" rather than raw counts. |
| **D18** | Monday deliverable = **factual findings only** (no thesis argumentation) | Focus on observable patterns: which jurisdictions use foreign climate decisions, and which cases are most paradigmatic globally. Thesis arguments reserved for later. |
| **D19** | Phase 8 (Full Run) **absorbed into Phase 5 / Phase 110** | The current VM extraction run (Step E) IS the full pipeline run. Phase 8 as originally planned is redundant. |
| **D20** | Phase 7 (Trial Run) **confirmed complete** | Test run of 100 docs was already executed, reviewed by Lucas, adjustments implemented, and re-tested before launching full run. |
| **D21** | **Complementary review strategy** | Lucas: manual Excel review (domain expertise, legal accuracy). Gustavo: automated DB queries + chunk inspection (technical validation). Reviews will be aligned tomorrow morning. |

## Tasks Established

| Owner | Task | Deadline |
|-------|------|----------|
| **Gustavo** | Export extraction results to Excel with direct document links and send to Lucas | Tonight (7 Mar) |
| **Lucas** | Manual review of Excel output — annotate review process (what is checked, data path followed) to enable future AI-automated review | Tonight / tomorrow morning |
| **Gustavo** | Run DB queries on citation data for automated pre-review (chunk inspection, pattern validation) | Tonight / tomorrow morning |
| **Lucas** | Align tomorrow's meeting time with Nat (arrive at Adriano's between noon and 1pm) | Tonight |
| **Both** | Morning sync at Lucas's place, then go to Adriano's for deliverable presentation | Sunday 8 Mar, morning |

## Key Numbers Discussed

- **5,513** documents classified as decisions (intentionally broad classification to capture more, filter later)
- **11,600** citations extracted so far
- **4,600** documents containing citations
- **275** documents flagged with extraction bugs (NoneType error, small portion)
- **157** documents remaining in extraction at time of call (~98% complete)

## Methodology Notes

- Classification was intentionally broad (cast wide net) — excess will be filtered in analysis phase
- Lucas will document his manual review process so it can be abstracted into AI-automated review later
- The two review approaches (manual + automated) are complementary and cover different angles

---

# 📝 Observações

7 de mar. de 2026

## touchpoint \- Global Trends

Convidados [Gustavo Rodriguez](mailto:gustavo.rodriguez@kria.vc) [lucasbiasetton@gmail.com](mailto:lucasbiasetton@gmail.com)

Anexos [touchpoint - Global Trends](https://www.google.com/calendar/event?eid=NmQzMjAzcWJuZnJvY2gzZjBuYzhzNGE4aWIgZ3VzdGF2by5yb2RyaWd1ZXpAa3JpYS52Yw) 

Registros da reunião [Transcrição](?tab=t.tc2ckzugd7zx) 

### Resumo

Projeto de extração de dados discutiu documentação metodológica e status do processo, com foco na revisão de bugs e alinhamento do plano de análise para a entrega de segunda-feira.

**Metodologia e Documentação de Issues**  
A documentação de *issues* e pontos de ação foi priorizada para garantir a reprodutibilidade e a inspeção do projeto, seguindo a metodologia acordada. O status atual do projeto é "pending in progress situation extraction V6", com a fase 7 concluída e a fase 8 incluída na fase 5, indicando que o *test running* foi realizado.

**Progresso da Extração de Citações**  
Um bug foi identificado na "phase 2 extraction," afetando 265 documentos com um *label* incorreto ou vazio, o que está sinalizado para investigação. O processo de extração de citações está 98% concluído, e o resultado será enviado em uma planilha Excel para revisão manual e anotações.

**Estratégia de Análise de Dados**  
O foco da análise será em constatações factuais sobre como jurisdições estão utilizando decisões de litígios climáticos de outros países, utilizando bases relativas, como a proporção de citações, em vez de números absolutos. Foi decidido contar as citações por documento para a entrega de segunda-feira, considerando apenas 1 ato de evocar uma decisão estrangeira por documento.

### Detalhes

* **Compartilhamento de Local e Status do Projeto**: Gustavo Rodriguez e Lucas Biasetton discutiram o ambiente de Lucas Biasetton e a possibilidade de ruído de fundo, com Lucas Biasetton desligando a câmera devido à bateria ([00:00:00](#00:00:00)). Lucas Biasetton confirmou que não houve interrupção de um evento social, pois eles já haviam planejado a conversa ([00:01:15](#00:01:15)).

* **Metodologia e Documentação do Projeto**: Gustavo Rodriguez informou que estava transcrevendo a conversa e finalizando um relatório, mencionando que a retomada do projeto gerou \*issues\* e pontos de ação que implicam escolhas de \*design\* ([00:00:00](#00:00:00)). Eles salvaram essas ocorrências para documentação, visando fins de metodologia, reprodutibilidade e inspeção, seguindo uma sugestão anterior de Lucas Biasetton ([00:02:36](#00:02:36)).

* **Andamento e Fases do Processo de Extração**: O status atual do projeto é "pending in progress situation extraction V6", com planos para uma análise do \*output\* e exportação para análise manual após a conclusão desta fase. Eles discutiram as fases de processamento, confirmando que a fase sete já foi concluída e que a fase oito deve ser abrangida pela fase cinco, indicando que o \*test running\* já foi realizado ([00:02:36](#00:02:36)).

* **Revisão de Bugs e Detalhes Técnicos**: Gustavo Rodriguez forneceu uma visão geral de um bug na "phase 2 extraction," que implica a remoção de citações do texto, onde 265 documentos saíram com um \*label\* incorreto ou vazio ([00:03:52](#00:03:52)). A causa provável é uma questão técnica com uma chamada de API no \*prompt\*, mas a parcela de documentos afetados é pequena, e eles estão sinalizados para investigação ([00:05:30](#00:05:30)).

* **Progresso da Extração de Citações e Próximos Passos**: O processo de extração de citações está em 98% de conclusão, com 157 itens faltando ([00:05:30](#00:05:30)). Eles concordaram em finalizar a extração e enviar o resultado para Lucas Biasetton fazer uma revisão manual, com anotações em casa ([00:07:55](#00:07:55)).

* **Plano de Revisão e Formato de Entrega**: O formato ideal de entrega para Lucas Biasetton é uma planilha Excel, similar à versão revisada anteriormente, contendo links de acesso direto aos documentos para revisão manual ([00:07:55](#00:07:55)). A sugestão é que Lucas Biasetton realize a revisão, anotando o processo mentalmente ou no papel, para que seja possível automatizar a revisão futuramente ([00:09:06](#00:09:06)).

* **Estratégia de Revisão e Colaboração Futura**: Lucas Biasetton fará a revisão manual mais tarde, sem pressa de enviar as anotações imediatamente, e eles conversarão no dia seguinte para repassar os problemas identificados e buscar uma maneira de abstrair esse processo para a inteligência artificial ([00:10:02](#00:10:02)). Eles concordaram que seus focos de revisão serão complementares, o que é benéfico ([00:12:37](#00:12:37)).

* **Números Atuais de Decisões e Citações**: Gustavo Rodriguez informou que foram classificadas 5.513 decisões e extraídas 11.600 citações, com 4.600 documentos contendo citações ([00:10:02](#00:10:02)). A classificação inicial foi propositalmente abrangente, utilizando \*labels\* amplos para captar o máximo de dados, com a intenção de filtrar os excessos em etapas posteriores ([00:11:12](#00:11:12)).

* **Direcionamento da Análise com Base nas Perguntas de Pesquisa**: Gustavo Rodriguez planeja rodar \*queries\* na base de dados das citações para conferir "chunks" e realizar uma pré-revisão automatizada, enriquecida pelas notas da revisão manual de Lucas Biasetton ([00:11:12](#00:11:12)). Eles planejam focar o mapa para o Adriano (entrega de segunda-feira) em constatações factuais sobre como jurisdições estão utilizando decisões de litígios climáticos de outros países ([00:12:37](#00:12:37)).

* **Métricas para o Mapa de Resultados e Contagem de Citações**: Eles concordaram em usar bases relativas, como a proporção de citações, em vez de números absolutos, para ser mais cauteloso nas afirmações públicas ([00:13:47](#00:13:47)). A contagem de citações será por documento, considerando o ato de evocar uma decisão estrangeira apenas uma vez por documento, mesmo que haja múltiplas referências textuais, para a entrega de segunda-feira ([00:15:01](#00:15:01)).

* **Plano de Reunião para o Dia Seguinte**: O plano é que Lucas Biasetton e Gustavo Rodriguez realizem suas respectivas análises (Lucas Biasetton no Excel e Gustavo Rodriguez com \*queries\*) e as alinhem na manhã seguinte. Eles devem chegar no local do encontro entre meio-dia e uma, preferencialmente antes, para o compromisso com Adriano ([00:16:59](#00:16:59)).

* **Alinhamento Final do Horário e Comunicação**: Gustavo Rodriguez sugeriu que Lucas Biasetton alinhe o horário de encontro com Nat, já que eles não moram sozinhos, para determinar o momento mais adequado para a chegada de Gustavo Rodriguez. Eles confirmaram o plano e encerraram a conversa, com a comunicação de detalhes finais sendo feita por mensagem ([00:16:59](#00:16:59)).

### Próximas etapas sugeridas

- [ ] Gustavo Rodriguez vai enviar o Excel do output para Lucas Biasetton.  
- [ ] Lucas Biasetton vai olhar o Excel do output das citações quando chegar em casa e fazer uma rotina de revisão, anotando o que está checando e o caminho de um dado para o outro, visando automatizar o processo.  
- [ ] Gustavo Rodriguez vai rodar queries na base de dados com as citações e conferir alguns chunks para fazer uma pré-revisão automatizada.  
- [ ] Lucas Biasetton vai alinhar o horário da reunião de amanhã com a Nat.

*Revise as anotações do Gemini para checar se estão corretas. [Confira dicas e saiba como o Gemini faz anotações](https://support.google.com/meet/answer/14754931)*

*Envie feedback sobre o uso do Gemini para criar notas [breve pesquisa.](https://google.qualtrics.com/jfe/form/SV_9vK3UZEaIQKKE7A?confid=IxgUvGtUYemAME3fMa4uDxIOOAIIigIgABgFCA&detailid=standard)*

# 📖 Transcrição

7 de mar. de 2026

## touchpoint \- Global Trends \- Transcrição

### 00:00:00 {#00:00:00}

   
**Gustavo Rodriguez:** Muito bem. Que que é isso? Uma um roof topzinho. Que alto é um Morumbi? Brooklyn. Ah, olha só. Um compromissos da vida de casado. Ah, legal. Tá legal. Tá bem.  
**Lucas Biasetton:** Ah,  
**Gustavo Rodriguez:** Tá gostoso.  
**Lucas Biasetton:** tá de boa. Tá de boa. Tranquilo.  
**Gustavo Rodriguez:** Ah, vista pelo menos é ótima. Muito  
**Lucas Biasetton:** É, não é bonito.  
**Gustavo Rodriguez:** bem.  
**Lucas Biasetton:** Bonito. Eu só vou desligar a câmera que eu não tô com tanta bateria.  
**Gustavo Rodriguez:** Deixa eu abrir o terminal,  
**Lucas Biasetton:** Tipo, eu tô com bateria suficiente, mas  
**Gustavo Rodriguez:** tá? Eu desligo a minha também para não para não sugar tanto.  
**Lucas Biasetton:** sim.  
**Gustavo Rodriguez:** Tô transcrevendo aqui.  
**Lucas Biasetton:** Tá bom.  
**Gustavo Rodriguez:** E ele tá terminando de fazer esse relatório para falar em cima.  
**Lucas Biasetton:** Tá, esse  
**Gustavo Rodriguez:** Mas é esse último,  
**Lucas Biasetton:** último  
**Gustavo Rodriguez:** deixa eu abrir outro para checar o terminal da AVM para ver se acabou aí.  
**Lucas Biasetton:** ô, se tiver muito barulho de vento,  
**Gustavo Rodriguez:** Ousa,  
**Lucas Biasetton:** você me ajuda,  
   
 

### 00:01:15 {#00:01:15}

   
**Gustavo Rodriguez:** não tá suave.  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** Mas eu me ocorreu um pensamento.  
**Lucas Biasetton:** Hum.  
**Gustavo Rodriguez:** Se eu tô te tirando de um evento social,  
**Lucas Biasetton:** Não,  
**Gustavo Rodriguez:** eh,  
**Lucas Biasetton:** não, não. Tá suave,  
**Gustavo Rodriguez:** não,  
**Lucas Biasetton:** tá suave,  
**Gustavo Rodriguez:** tá suave mesmo.  
**Lucas Biasetton:** tá suave, tá suave, tá suave.  
**Gustavo Rodriguez:** Tá bom,  
**Lucas Biasetton:** Sim, sim, sim, sim.  
**Gustavo Rodriguez:** tá bom.  
**Lucas Biasetton:** Eu já tinha combinado com a Nat que algum momento eu ia sentar para falar com  
**Gustavo Rodriguez:** Ah, ótimo.  
**Lucas Biasetton:** você.  
**Gustavo Rodriguez:** Ah, legal, legal. Vou fazer ela me odiar, hein?  
**Lucas Biasetton:** Não, não,  
**Gustavo Rodriguez:** Que eu gosto dela.  
**Lucas Biasetton:** ela te ama.  
**Gustavo Rodriguez:** Ahã. Tá. Check aqui no status já. Ah, pronto. Vou compartilhar a tela. Eh,  
**Lucas Biasetton:** Так.  
**Gustavo Rodriguez:** cadê 200?  
**Lucas Biasetton:** Beleza.  
**Gustavo Rodriguez:** Ó,  
**Lucas Biasetton:** Tô vendo.  
**Gustavo Rodriguez:** tá vendo?  
**Lucas Biasetton:** Tô  
**Gustavo Rodriguez:** Tá. Isso. Essas tes são coisas issues e pontos de ação que  
**Lucas Biasetton:** vendo,  
**Gustavo Rodriguez:** implicam muitas vezes escolhas e designs que surgiram desde que a gente retomou o projeto.  
   
 

### 00:02:36 {#00:02:36}

   
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** Aí a gente enquanto elas iam surgindo, a gente ia progredindo, eu fui salvando essas ocorrências para documentar tudo para fins de  
**Lucas Biasetton:** Угуm.  
**Gustavo Rodriguez:** metodologia e reprodutibilidade e inspeção do que a gente fez. É legal ter isso. Você me contou isso bem cedo e dei um step up num jeito de fazer isso. Eh, a gente tá aqui, ó,  
**Lucas Biasetton:** Boа.  
**Gustavo Rodriguez:** pending in progress situation extraction V6. Eh,  
**Lucas Biasetton:** Expion.  
**Gustavo Rodriguez:** fora isso, tem mapeado também para quando acabar essa coisa, a gente fazer uma análise do output e exportar para você fazer análise manual também.  
**Lucas Biasetton:** Uhum. Uhum.  
**Gustavo Rodriguez:** E ah, não, a gente tá fazendo a fase oito, ó. Ele tem que juntar,  
**Lucas Biasetton:** Ah, já já foi as às 5 ou  
**Gustavo Rodriguez:** não é? Não é a C em progress abrange a fase,  
**Lucas Biasetton:** seis.  
**Gustavo Rodriguez:** a sete já foi e a oito tem que ser abrangida pela cinco. Ele ele ele tem que atualizar o convention de naming dessa p\*\*\*\*.  
**Lucas Biasetton:** Ah, então,  
**Gustavo Rodriguez:** Mas ah,  
**Lucas Biasetton:** mas então a gente já rodou em alguns documentos.  
   
 

### 00:03:52 {#00:03:52}

   
**Gustavo Rodriguez:** já fez test runing.  
**Lucas Biasetton:** Tá beleza. Maravilha.  
**Gustavo Rodriguez:** Um depois daquele que você viu que se apontou gruta da Nigéria,  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** porque mexemos no pipe depois daquilo. Mas aí o que eu o que me fez mexer no pipe foi arrumado.  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** era uma coisa puramente técnica de de como fazer o programa, fazer o que você quer.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** E aí eu nem nem levantei a bola assim, nem E aí tem uns bugs, cara, aqui que assim que eu te mencionei antes. Traction tem algumas também, mas deixa eu falar dos bug que é mais relevante. É aqui a gente tem cara, quanto detalhe você quer ver dessas coisas?  
**Lucas Biasetton:** Cara, acho que é um overview de quais bugs são. Pode me  
**Gustavo Rodriguez:** Tá bom. Overview.  
**Lucas Biasetton:** falar.  
**Gustavo Rodriguez:** Hum. Esse phase 2 extraction implica um uma fase cuja função é ã tirar o as as citações do texto como fall do do do pH 1 ou como cadeia posterior e tinha uma  
**Lucas Biasetton:** Uhm.  
**Gustavo Rodriguez:** classificação de parte dos documentos que saíam dessa etapa que tava com um label ou de tipo,  
**Lucas Biasetton:** Hum.  
**Gustavo Rodriguez:** ah, vazio, errado, esse tipo de coisa.  
   
 

### 00:05:30 {#00:05:30}

   
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** E a gente tem que investigar ainda por isso aconteceu com só 265 documentos. E a a a causa provável,  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** o gas dele é um bagulho com API call no prompt, mas é é uma parcela pequena.  
**Lucas Biasetton:** tá. E a gente tem quais são esses documentos para Tá.  
**Gustavo Rodriguez:** Sim, tá flegado. Tá flegado. Eu mandei flegar.  
**Lucas Biasetton:** Tá bom.  
**Gustavo Rodriguez:** Ã, tá. Isso aqui é sobre velocidade. f\*\*\*-se. Esse aqui tem um carzinho.  
**Lucas Biasetton:** É o mesmo 275,  
**Gustavo Rodriguez:** Não é o mesmo.  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** É o mesmo.  
**Lucas Biasetton:** Esse 275 aí.  
**Gustavo Rodriguez:** É o mesmo. É o mesmo.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Isso aqui é uma coisa deve assim, tipo, que ele salvou para eu ver, porque acho que só pelo jeito dele acessar a virtual machine, ele não tava vendo a a base de dados preenchida por um dentro de um parâmetro,  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** mas o script rodando em e tipo tendo seguido em com base em outro registro aí. OK.  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** State 98%.  
   
 

### 00:06:53

   
**Gustavo Rodriguez:** Ai cara, mas eu vou mandar eles eles trocar na base de dados pra gente já ver depois. Mas não agora no celular não precisa. A gente pode revisar amanhã cedo. Ou você vai querer ver isso hoje ainda?  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Eu eu topo a parte de revisão do  
**Lucas Biasetton:** Cara, é, é que eu não sei, tipo, eu não entendi direito exatamente em qual fase que a gente tá.  
**Gustavo Rodriguez:** output. Extraindo as citações. O último script,  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** falta 157 de todas as  
**Lucas Biasetton:** mas aí a gente tá extraindo as citações de tudo,  
**Gustavo Rodriguez:** decisões. Sim,  
**Lucas Biasetton:** tá? Tá. E tá,  
**Gustavo Rodriguez:** porque a gente fez um teste de 100 de com 31 decisões.  
**Lucas Biasetton:** a gente tá e Aham.  
**Gustavo Rodriguez:** Você revisou, a gente viu juntos a sua revisão,  
**Lucas Biasetton:** Aham.  
**Gustavo Rodriguez:** anotou alguns ajustes,  
**Lucas Biasetton:** Aham.  
**Gustavo Rodriguez:** implementou os ajustes. Eu rodei de novo um teste.  
**Lucas Biasetton:** Mas então você acha que esses 98% em relação ao resultado final já?  
**Gustavo Rodriguez:** É,  
**Lucas Biasetton:** c\*\*\*\*\*\*, eu achei que isso não tava tão avançado ainda,  
   
 

### 00:07:55 {#00:07:55}

   
**Gustavo Rodriguez:** não é tudo.  
**Lucas Biasetton:** tá? Não. Então eu acho que eu não sei se tem alguma sugestão de próximo passo, porque senão o que eu ia falar é: "Vamos acabar, aí você me manda o o que saiu e quando eu chegar em casa eu olho com mais cuidado,  
**Gustavo Rodriguez:** Ah,  
**Lucas Biasetton:** eventualmente faço anotações e tal e amanhã cedo,  
**Gustavo Rodriguez:** ótimo.  
**Lucas Biasetton:** não sei, não precisa ser super cedo, mas amanhã se você quiser ir para casa ou a gente se liga e e aí a  
**Gustavo Rodriguez:** Uhum. Não, prefiro colar aí até pra gente junto o padrão é caminho sua casa porque a dele da minha mais ou  
**Lucas Biasetton:** gente tá tá bom.  
**Gustavo Rodriguez:** menos  
**Lucas Biasetton:** Então a gente fica trabalhando junto até a hora de ir pro Adriano para fechar tudo.  
**Gustavo Rodriguez:** fechado.  
**Lucas Biasetton:** Que que você acha? Não sei se pensou em alguma outra coisa.  
**Gustavo Rodriguez:** Perfeito. Eu só tenho uma dúvida para delimitar, delinear isso melhor ou mais detradamente. O formato que você quer receber,  
**Lucas Biasetton:** Hã,  
**Gustavo Rodriguez:** tipo o que você quer receber e como?  
**Lucas Biasetton:** assim, eu acho que o ideal para mim seria um Excel, ã, em que eu te é parecido com o Excel que eu revisei e aí você já ajustou a nova versão para ter os links de acesso direto ao documento pro meu manual review para eu legal, que eu achar estranho.  
   
 

### 00:09:06 {#00:09:06}

   
**Lucas Biasetton:** Então, a princípio,  
**Gustavo Rodriguez:** Sim.  
**Lucas Biasetton:** se se eu receber o Excel com tudo, já é suficiente, porque com esse Excel eu também consigo começar a gerar uns esboços de mapa que eu já pensei em algumas coisas também. Então, para mim seria isso.  
**Gustavo Rodriguez:** tá? Te pedir um favor, então eu te passo esse Excel e você roda  
**Lucas Biasetton:** Diga. Uhum.  
**Gustavo Rodriguez:** umas não zaralha ele, mas tipo, eh, minha sugestão é você rodar ele numa etapa de revisão, anotando mentalmente no papel ou sei lá onde for o o que você tá fazendo  
**Lucas Biasetton:** Uhum. Sim.  
**Gustavo Rodriguez:** exatamente, o que está checando,  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** que dado está checando e o caminho que você faz de um dado pro outro.  
**Lucas Biasetton:** tá, tá. Pra gente conseguir fazer essa revisão também via inteligência artificial.  
**Gustavo Rodriguez:** eh fazer fazer a revisão automatizada  
**Lucas Biasetton:** É isso. Boa, boa ideia.  
**Gustavo Rodriguez:** assim e aí não faz  
**Lucas Biasetton:** Boa ideia. Boa ideia. Não, perfeito. Eu consigo. Eu  
**Gustavo Rodriguez:** isso. A ideia,  
**Lucas Biasetton:** consigo.  
   
 

### 00:10:02 {#00:10:02}

   
**Gustavo Rodriguez:** você faz essa rotina de revisa um tanto e anota a revisão e interrompe, me passa pra gente ver os problemas que já surgirem na sua  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** revisão e pensar num jeito de extrapolar,  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** abstrair o seu processo com as ferramentas que a gente  
**Lucas Biasetton:** tá,  
**Gustavo Rodriguez:** tem.  
**Lucas Biasetton:** tá. Não, tá bom. Mas, ó, o essa revisão eu provavelmente vou fazer mais tarde só. Então, Tipo, nem se preocupa que em eu mandar isso hoje, tá? Me manda o Excel e aí em algum momento vou sentar e vou olhar.  
**Gustavo Rodriguez:** Tá bom. Suave.  
**Lucas Biasetton:** E aí amanhã e aí ou eu começo algum alguma eu brinco com Claudinho em algum formato de revisão ou eu deixo minhas anotações prontas e amanhã a gente conversa para, enfim, para repassar e tal,  
**Gustavo Rodriguez:** Combinado.  
**Lucas Biasetton:** para ver o que que fala.  
**Gustavo Rodriguez:** Combinadíssimo.  
**Lucas Biasetton:** E aí,  
**Gustavo Rodriguez:** Eh,  
**Lucas Biasetton:** você sabe quantas decisões deram agora?  
**Gustavo Rodriguez:** sim.  
**Lucas Biasetton:** Quantos documentos foram classificados como decisões?  
**Gustavo Rodriguez:** 4.000.  
**Lucas Biasetton:** Ah, top,  
**Gustavo Rodriguez:** Não, 5.513.  
   
 

### 00:11:12 {#00:11:12}

   
**Gustavo Rodriguez:** Só que assim,  
**Lucas Biasetton:** c\*\*\*\*\*\*.  
**Gustavo Rodriguez:** a gente fez um, até agora tem 11.000 citações extraídas,  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** 11.600 e 4600 documentos que contém citações. Só que lembra que o jeito de classificar é uma decisão foi  
**Lucas Biasetton:** Tá  
**Gustavo Rodriguez:** abrangente com labels pra gente pegar  
**Lucas Biasetton:** sim.  
**Gustavo Rodriguez:** mais e errar pelo excesso de captar dados.  
**Lucas Biasetton:** Do que menos.  
**Gustavo Rodriguez:** É.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** E depois na na hora de refinar a gente filtra para tirar  
**Lucas Biasetton:** E a gente pode tirando os excessos.  
**Gustavo Rodriguez:** isso. Isso e desconsidera do do set final de informa de de  
**Lucas Biasetton:** Aham.  
**Gustavo Rodriguez:** informações. Eh, uma última coisa do meu lado, pensei aqui agora porque eh eu preciso olhar o output  
**Lucas Biasetton:** Так.  
**Gustavo Rodriguez:** também e revisar o que eu puder agregar de revisão assim. E aí eu pensei em, já que você vai fazer essa já essa parte manual, eu pensei em rodar uns queries para base de dados com as citações  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** e começar a ver alguns chunks, conferir alguns chunks assim de coisas de tipo um pré revisão automatizada que dá para enriquecer partindo das suas notas da revisão manual.  
   
 

### 00:12:37 {#00:12:37}

   
**Lucas Biasetton:** Não, perfeito.  
**Gustavo Rodriguez:** Eu posso já achar coisas antes também.  
**Lucas Biasetton:** É, e eu acho que que a gente tá não, beleza. Eu acho que a gente vai, acho que o nosso foco da revisão talvez seja em coisas diferentes, então isso é bom também.  
**Gustavo Rodriguez:** Ah, sim, verdade.  
**Lucas Biasetton:** Tipo,  
**Gustavo Rodriguez:** A gente olha para Sim,  
**Lucas Biasetton:** o meu foco vai ser um e o seu provavelmente vai ser outro. Então,  
**Gustavo Rodriguez:** é sim,  
**Lucas Biasetton:** eu acho que se complementam  
**Gustavo Rodriguez:** sim. Eh,  
**Lucas Biasetton:** bem.  
**Gustavo Rodriguez:** e para isso eu queria também eh aplicar ou ter de referência as perguntas de pesquisa, lembra disso?  
**Lucas Biasetton:** Lembro, lembro, lembro,  
**Gustavo Rodriguez:** Então, onde onde tá isso fácil assim?  
**Lucas Biasetton:** lembro. Deixa eu ver aqui que,  
**Gustavo Rodriguez:** Tipo,  
**Lucas Biasetton:** cara, agora as perguntas de pesquisa nem eu sei mais como fal.  
**Gustavo Rodriguez:** tipo,  
**Lucas Biasetton:** Porque as que são do meu doutorado não são necessariamente as que a gente  
**Gustavo Rodriguez:** que a gente vai hã pro  
**Lucas Biasetton:** vai eh que a gente vai usar aqui.  
**Gustavo Rodriguez:** mapa mapa de segunda. É.  
**Lucas Biasetton:** É, mas assim, pensando alto aqui na minha cabeça, o que a gente quer identificar assim, existe um, eu eu não vou entrar agora no argumento da minha tese, porque o que a gente vai eh montar pra segunda é uma constatação fática.  
   
 

### 00:13:47 {#00:13:47}

   
**Lucas Biasetton:** Não tem, não vai ter argumentação ã da minha tese em si, né? vai ser só uma constatação fática do que que a gente viu que tá acontecendo. E aí a gente vai ver como eh jurisdições estão se aproveitando  
**Gustavo Rodriguez:** Certo.  
**Lucas Biasetton:** de decisões de litígios climáticos em outros países para utilizar nos seus próprios.  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** E a gente vai ver o impacto dos casos paradigmáticos no mundo inteiro. Então, a gente basicamente quer ver essas duas coisas, quer ver quais são os países que mais tão suscetíveis a usar decisões estrangeiras em suas em seus suas decisões e quais são os casos mais paradigmáticos e até onde eles chegaram.  
**Gustavo Rodriguez:** Entendi. Então, em termos no de número assim, a gente vai tá, a gente vai contar citações por países e elencar os top cinco, top 10, destacar quem são o número de citações ou eu pensei nisso,  
**Lucas Biasetton:** Isso.  
**Gustavo Rodriguez:** a proporção de citações do total de estações identificadas na base de dados. Eu acho que isso é um,  
**Lucas Biasetton:** É, aí eu acho que a gente vai ter que ver.  
**Gustavo Rodriguez:** eu tive a sugestão assim para ventilar porque você levantou aquela preocupação muito,  
**Lucas Biasetton:** É,  
   
 

### 00:15:01 {#00:15:01}

   
**Gustavo Rodriguez:** muito válida e e p\*\*\*\* séria de tipo, mano, pôr o c\* na reta num bagulho público, num grade acadêmico e ser comedido em certas afirmações  
**Lucas Biasetton:** sim.  
**Gustavo Rodriguez:** assim.  
**Lucas Biasetton:** É,  
**Gustavo Rodriguez:** Aí eu imaginei usar usar bases relativas e não números  
**Lucas Biasetton:** não é, eu acho, eu acho, é, pode ser.  
**Gustavo Rodriguez:** absolutos.  
**Lucas Biasetton:** É uma boa. É, pode ser, pode ser. Eu acho uma boa, tipo, dos que do que encontramos X%,  
**Gustavo Rodriguez:** Isso.  
**Lucas Biasetton:** né? É, eu acho que funciona. E eu acho que um cuidado que a gente tem que tomar na hora da gente fazer os os números é que se eu tenho um acórdão do STF que citou urgenda oito vezes, eu vou contar isso como uma vez só e não como oito citações. A gente a gente falou sobre isso uma vez, lembra? Não sei se você lembra.  
**Gustavo Rodriguez:** Lembra M.  
**Lucas Biasetton:** Tipo, então são citações por documento. Então, se um documento cita uma adesão estrangeira 15 vezes, eu não vou contar como 15, eu vou contar como uma só.  
**Gustavo Rodriguez:** é tipo o ato de evocar a decisão estrangeira, ainda que textualmente se refita isso eh por decisão,  
   
 

### 00:16:04

   
**Lucas Biasetton:** Isso. Por por documento.  
**Gustavo Rodriguez:** ainda que eventualmente o da decisão contenha várias referências textuais,  
**Lucas Biasetton:** Exato.  
**Gustavo Rodriguez:** mas assim, você revocou uma vez,  
**Lucas Biasetton:** Exato. Exato. Porque aí, tipo,  
**Gustavo Rodriguez:** tá?  
**Lucas Biasetton:** e a gente consegue usar esse números, esse que eu não quero usar agora, a gente consegue usar de outras em outros momentos, mas agora eu acho que a gente não não eu não entraria nesse grau de detalhamento. Tipo,  
**Gustavo Rodriguez:** focado ali,  
**Lucas Biasetton:** agora eu iria para É,  
**Gustavo Rodriguez:** buo que a gente tem que entregar a segunda. Perfeito. Muito bem.  
**Lucas Biasetton:** exato,  
**Gustavo Rodriguez:** Muito  
**Lucas Biasetton:** exato, porque é porque esse segundo eu já até tem umas ideias para ele,  
**Gustavo Rodriguez:** bem.  
**Lucas Biasetton:** tipo de eh atribuir uns core de relevância, mas aí f\*\*\*-se, aí é loucura pro pro doutorado e não para pra segunda-feira.  
**Gustavo Rodriguez:** Dependendo de como e quando a gente acabar o o core deliverable de segunda, dá para dar uma viajada.  
**Lucas Biasetton:** É, é, mas é, mas eu acho que é isso. Então,  
**Gustavo Rodriguez:** Temos um plano Excel,  
   
 

### 00:16:59 {#00:16:59}

   
**Lucas Biasetton:** temos um plano.  
**Gustavo Rodriguez:** análise sua, análise minha, a gente bate as análises amanhã.  
**Lucas Biasetton:** Isso. E aí, amanhã a gente se junta que horas que é,  
**Gustavo Rodriguez:** Isso,  
**Lucas Biasetton:** no Adriano?  
**Gustavo Rodriguez:** cara, o esperado é chegar entre meio-dia e uma. Antes do meio-dia vai ser inconveniente,  
**Lucas Biasetton:** c\*\*\*\*\*\*,  
**Gustavo Rodriguez:** meio-dia em ponto é OK,  
**Lucas Biasetton:** cedo.  
**Gustavo Rodriguez:** depois da uma ele já consideram um atraso assim fica, o Adano fica sentido.  
**Lucas Biasetton:** Tá, não tá. É cedo,  
**Gustavo Rodriguez:** É cedo,  
**Lucas Biasetton:** é cedo.  
**Gustavo Rodriguez:** é porque é para mostar gostoso.  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** E o Adriano gosta de rolê que terminam cedo.  
**Lucas Biasetton:** sim. Não,  
**Gustavo Rodriguez:** Ele é um senhorzinho.  
**Lucas Biasetton:** tá sim. Um velhinho. Eh, não.  
**Gustavo Rodriguez:** É domingo.  
**Lucas Biasetton:** Mas beleza. Ah, bom. Mais tarde a gente alinha o horário. Eu acordo cedo,  
**Gustavo Rodriguez:** Eu também.  
**Lucas Biasetton:** então. Mas não sei que hora você tinha pensado,  
**Gustavo Rodriguez:** Vê aí com a Nat. Alinha Conat.  
**Lucas Biasetton:** mais ou menos.  
**Gustavo Rodriguez:** Você não mora sozinho alinha com a que horas ela vai ela vai tá ela vai tá  
**Lucas Biasetton:** É uma boa, uma boa ideia. Uma boa ideia.  
**Gustavo Rodriguez:** com luz para ser forçada a socializar na casa dela ou conviver  
**Lucas Biasetton:** Não,  
**Gustavo Rodriguez:** com Não.  
**Lucas Biasetton:** aí ela fica, ela fica no quarto.  
**Gustavo Rodriguez:** Sim, mas alinha ali com ela,  
**Lucas Biasetton:** Fica no quarto.  
**Gustavo Rodriguez:** ver que horas é adequado.  
**Lucas Biasetton:** Sim. Não, mas é uma boa. É, eu vou conversar com ela.  
**Gustavo Rodriguez:** E aí o mais cedo a partir disso eu colo.  
**Lucas Biasetton:** Mas beleza. Tá bom, tá bom.  
**Gustavo Rodriguez:** Muito bem.  
**Lucas Biasetton:** Maravilha.  
**Gustavo Rodriguez:** Maravilha.  
**Lucas Biasetton:** Fechado. Tá acho muito obrigado, viu, mano? Você tá mais uma vez brilhando. É muito bom. Muito bom. Beleza. Tá bom. Nós falamos então por mensagem ainda. Sim, eu também.  
   
 

### A transcrição foi encerrada após 00:18:56

*Esta transcrição editável foi gerada por computador e pode conter erros. As pessoas também podem alterar o texto depois que ele for criado.*