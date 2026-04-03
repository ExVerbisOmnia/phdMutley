# 📝 Observações

3 de mar. de 2026

## Global Trends

Convidados [Gustavo Rodriguez](mailto:gustavo.rodriguez@kria.vc) [lucasbiasetton@gmail.com](mailto:lucasbiasetton@gmail.com) [lucas.biasetton@vpbg.com.br](mailto:lucas.biasetton@vpbg.com.br)

Anexos [Global Trends](https://www.google.com/calendar/event?eid=NmExMTFnb2UybGs2MDN1amw0azIxbWExaW8gZ3VzdGF2by5yb2RyaWd1ZXpAa3JpYS52Yw) 

Registros da reunião [Transcrição](?tab=t.ibn4qd656xus) 

### Resumo

Lucas Biasetton e Gustavo Rodriguez enfrentaram desafios técnicos iniciais, como problemas de conexão e fones de ouvido. O tópico principal da reunião focou na revisão da metodologia de captura de informações para o projeto, com Lucas Biasetton propondo ajustes na arquitetura para aumentar a extração de citações e incorporar um passo de *build knowledge* (construção de conhecimento) usando dados da Columbia, uma mudança impulsionada por um projeto anterior onde a metodologia falhou em capturar citações corporativas.

Lucas Biasetton também relatou o pedido de Joana e Kate para preparar um mapa de jurisdições para um relatório, identificando as top cinco jurisdições citantes (Austrália, Nova Zelândia, Reino Unido, Brasil e Canadá), e expressou preocupação com citações muito antigas da Austrália que não se enquadravam no escopo do *Climate Case Chart*. Gustavo Rodriguez e Lucas Biasetton concordaram em usar o Gemini para otimizar o *pipeline*, alterar o formato de armazenamento dos arquivos para *Markdown* e focar na extração e filtragem de citações pelo *Sabing Center*, com o objetivo de entregar o mapa estático e uma breve reflexão a Joana até 9 de março, enquanto ponderavam a submissão de um artigo sobre a metodologia.

### Detalhes

* **Desafios de Conexão e Fones de Ouvido**: Lucas Biasetton e Gustavo Rodriguez enfrentaram problemas de conexão no início da reunião, com Gustavo Rodriguez precisando desconectar e reconectar seus fones para estabelecer a comunicação. Lucas Biasetton também mencionou que seus fones não conectaram automaticamente ([00:00:00](#00:00:00)).

* **Teste de Extensão do Chrome e Pesquisa de Apartamento**: Antes de iniciar o tópico principal, Lucas Biasetton mencionou ter deixado o "Claudinho rodando" para testar uma nova extensão do Chrome ([00:00:00](#00:00:00)). Por curiosidade, eles disseram que usaram a ferramenta para procurar um apartamento em Londres com especificações e preço desejados ([00:05:29](#00:05:29)).

* **Revisão da Metodologia de Captura de Informações**: Lucas Biasetton propôs alterar a estrutura de captura de informações devido a um mini-projeto que revelou que a metodologia existente não capturava todas as citações desejadas. O objetivo é ajustar a arquitetura para aumentar a captura de citações e corrigir classificações incorretas ([00:05:29](#00:05:29)).

* **Preparação de Mapa de Jurisdições**: Lucas Biasetton relatou um pedido de Joana e Kate para preparar um mapa estático, que apresentaria as principais jurisdições, as top cinco citantes e a frequência de suas citações ([00:05:29](#00:05:29)). Para isso, Lucas Biasetton realizou testes e notou que as top cinco jurisdições eram: Austrália, Nova Zelândia, Reino Unido, Brasil e Canadá ([00:06:56](#00:06:56)).

* **Identificação de Problemas com Citações Antigas da Austrália**: Ao analisar os dados, Lucas Biasetton expressou preocupação com a Austrália, que cita decisões antiquíssimas do \*common law\* do Reino Unido, algumas datando de 1330 e 1600\. Esses casos não estavam relacionados ao escopo da pesquisa, sugerindo a necessidade de vincular as citações aos casos do \*Climate Case Chart\* ([00:06:56](#00:06:56)) ([00:09:18](#00:09:18)).

* **Sugestão para Limitar Buscas ao Climate Case Chart**: Para evitar a captura de informações aleatórias, Lucas Biasetton sugeriu limitar as buscas de casos aos listados no \*Climate Case Chart\*. Eles reconheceram que essa limitação precisaria ser explicada, e talvez a equipe queira incluir mais casos além dos listados ([00:09:18](#00:09:18)).

* **Experiência em Projeto com Casos Corporativos**: Lucas Biasetton descreveu um projeto anterior com casos corporativos de clima, onde o objetivo era quantificar quantas vezes casos contra o governo eram citados em casos contra empresas ([00:09:18](#00:09:18)). A aplicação da metodologia existente para este projeto resultou na perda de muitas citações, o que motivou a busca por ajustes ([00:10:41](#00:10:41)).

* **\*\*Introdução do Passo de Construção de Conhecimento (\*Build Knowledge\*)\*\***: Para melhorar a captura de citações, Lucas Biasetton implementou um passo de \*build knowledge\* (construção de conhecimento) usando a base de dados da Columbia para obter informações contextuais sobre os casos governamentais ([00:11:56](#00:11:56)). O uso da base da Columbia para gerar contexto sobre o ano, partes e breve descrição de cada caso governamental mostrou-se muito eficaz ([00:12:58](#00:12:58)).

* **Uso de IDs de Casos para Filtragem e Estruturação de Dados**: Gustavo Rodriguez propôs que uma forma de refinar o processo seria adicionar uma etapa de \*build knowledge\* antes de tudo e usar IDs para os casos, limitando o escopo de conexões apenas aos casos identificados na tabela ([00:15:02](#00:15:02)). Eles concordaram que usar IDs existentes no \*Sabing Center\* (tanto de caso quanto de documento) é preferível a criar novos ([00:35:53](#00:35:53)).

* **Revisão Metodológica para Publicação de Artigo**: Lucas Biasetton mencionou que Joana e Kate insistiram para que eles publicassem um artigo sobre a metodologia ([00:18:21](#00:18:21)). Eles ponderaram a possibilidade de submeter uma ideia de artigo como \*Junior Scholars\* para o prazo de 15 de março, aproveitando o refinamento da metodologia que está em curso ([00:19:14](#00:19:14)).

* **Uso de Gemini para Otimizar o Pipeline**: Gustavo Rodriguez confirmou que o projeto pode ser executado usando o Gemini, pois o modelo 3.1 Pro superou o Cloud 4.6 em vários \*benchmarks\* e é mais econômico. A equipe pode refinar o \*pipeline\* de processamento e polir a metodologia enquanto trabalha no entregável de curto prazo ([00:21:04](#00:21:04)).

* **Ajustes no Formato de Armazenamento de Arquivos**: Gustavo Rodriguez sugeriu que, ao baixar a versão mais atualizada da base da Columbia, o formato de armazenamento dos textos extraídos deve ser alterado para \*Markdown\*. Arquivos \*Markdown\* são otimizados para IA e têm melhor relação com texto estruturado, permitindo um \*re-run\* aprimorado do \*pipeline\* ([00:21:58](#00:21:58)).

* **Pontos de Revisão no Pipeline Existente**: A equipe revisou as fases do \*pipeline\*, notando que as etapas de \*Country Classification\* e \*Decision Classification\* merecem atenção e revisão de seus algoritmos ([00:24:37](#00:24:37)). O passo mais delicado a ser revisado é a extração e classificação das citações estrangeiras ([00:44:31](#00:44:31)).

* **Estratégia de Filtro de Citações por Base do Sabing Center**: Lucas Biasetton sugeriu que, no passo de extração de citações, elas sejam primeiro identificadas e, em seguida, filtradas se estiverem ou não no \*Sabing Center\*. Se a citação estiver na base do \*Sabing Center\*, as informações de origem (país, tipo de jurisdição) seriam extraídas dos metadados da própria tabela ([00:47:34](#00:47:34)).

* **Preocupação com a Confiabilidade dos Metadados da Base de Dados**: Gustavo Rodriguez e Lucas Biasetton discutiram a baixa confiabilidade dos metadados da base, como \*document\* e \*document ear\*, que foram escritos manualmente e apresentaram erros ([00:48:57](#00:48:57)). Eles ponderaram a possibilidade de usar o \*LLM\* para corrigir ou refazer essas classificações manuais, embora Lucas Biasetton expressasse preocupação com o custo e a escala dessa tarefa ([00:50:28](#00:50:28)).

* **Escopo e Prazo para o Entregável de Joana**: O objetivo de curto prazo é produzir o mapa estático e a breve reflexão solicitada por Joana até a segunda-feira, dia 9 de março, para que ela possa incorporar no rascunho do relatório. O entregável foca nos dados das top cinco jurisdições que citam e são citadas, bem como uma análise sobre a posição isolada dos EUA na litigância climática global ([00:54:43](#00:54:43)).

* **Plano de Refinamento do Pipeline**: A equipe concluiu que, para garantir a qualidade da publicação, será necessário refazer o grosso do trabalho, o que implica um \*sprint\* de polimento de uma semana para refinar o \*pipeline\* ([00:57:46](#00:57:46)). O foco principal é obter dados confiáveis para o mapa, pois a escrita do texto é rápida ([00:56:36](#00:56:36)).

* **Discussão sobre Perfeição de Dados e Escopo**: Lucas Biasetton e Gustavo Rodriguez conversaram sobre a natureza imperfeita dos dados, mesmo dentro do escopo definido no Sabin. Gustavo Rodriguez destacou que o escopo já é um recorte e que é crucial incluir um aviso (disclaimer) sobre o processamento paralelo, juntamente com alguma estimativa de margem de erro. Lucas Biasetton expressou mais conforto em usar um "top five" de dados, em vez de uma tabela gigante de valores brutos, como o número de vezes que um país é citado ([00:58:55](#00:58:55)).

* **Refinamento dos Passos do Processo**: Lucas Biasetton revisou os passos iniciais do projeto, incluindo a inicialização do banco de dados (passo zero), a versão atualizada da tabela de downloads (passo um) e a criação de novos \*scripts\* de arquivo Markdown (passo dois). Gustavo Rodriguez sugeriu que o passo três deveria ser o fim do processo de correlação de dados e inclusão no banco de dados final ([01:00:03](#01:00:03)).

* **Identificação do Ponto Crítico no Fluxo de Trabalho**: Lucas Biasetton indicou que o ponto mais crítico (o "bug") estava no passo 5, considerando os demais passos como "peanuts". Eles questionaram a manutenção dos passos 3 e 4, que envolviam a classificação do contador e a classificação da decisão, e discutiram a possibilidade de criar uma base de conhecimento (knowledge base) ([01:02:01](#01:02:01)).

* **Estratégia de Reclassificação e Otimização da LLM**: Lucas Biasetton considerou a decisão de não reclassificar os dados do Sabin, principalmente devido à preocupação com o tempo. Gustavo Rodriguez sugeriu reclassificar apenas o que fosse estritamente necessário para o produto final ([01:05:15](#01:05:15)). Eles discutiram se seria mais eficiente ter um único resultado que abordasse a classificação de países e a classificação de decisões, já que o maior consumo de recursos da LLM está na leitura dos dados ([01:03:23](#01:03:23)).

* **Inclusão de Sumarização e Índice**: Gustavo Rodriguez sugeriu que após a conversão para Markdown, fosse incluído um passo de "sumarização" (sumarization) para criar sumários e índices antes da extração de citações. Eles debateram a extração de \*snippets\* de todas as citações como parte do passo de extração, mas concluíram que isso consumiria muitos recursos ([01:07:26](#01:07:26)).

* **Método para Marcação e Referência de Citações**: Gustavo Rodriguez propôs um método para marcar o início e o fim de cada citação por contagem de caracteres, facilitando a conferência posterior sem que o modelo de linguagem tivesse que processar a leitura e escrita integral das citações ([01:07:26](#01:07:26)). Lucas Biasetton expressou o desejo de ter os \*snippets\* das citações que seriam realmente utilizadas. Gustavo Rodriguez concordou em produzir os \*snippets\* depois de ter um método para acessá-los, de forma a não sobrecarregar a LLM com processamento desnecessário ([01:09:05](#01:09:05)).

* **Metodologia de Busca e Confiança no Modelo de Linguagem**: Lucas Biasetton relatou que no projeto anterior, eles buscavam casos relevantes em vez de todas as citações, e o modelo Gemini havia sugerido que não era necessário fornecer uma lista de referência, pois o modelo era avançado o suficiente para entender citações judiciais ([01:11:44](#01:11:44)). Gustavo Rodriguez questionou a confiança nessa informação, mas Lucas Biasetton afirmou que a abordagem funcionou no trabalho anterior, embora a amostragem fosse menor. Eles concluíram que a base de conhecimento seria muito grande para caber no contexto de uma única troca, sugerindo quebrar o processamento em lotes ([01:12:55](#01:12:55)).

* **Estrutura de Entidades e Fluxo do Algoritmo**: Gustavo Rodriguez descreveu a necessidade de catalogar entidades como casos, decisões e citações com rótulos de país, o que permitiria enriquecer a base de dados com sumários e índices ([01:13:55](#01:13:55)). Após o processamento inicial (download para markdown e identificação de entidades), o algoritmo deveria focar em identificar o número de citações feitas por cada país e a quem essas citações se referem ([01:17:44](#01:17:44)). Eles concordaram que as citações já eram tratadas como entidades com um ID na tabela anterior, o que poderia ser aproveitado ([01:19:28](#01:19:28)).

* **Revisão e Definição das Tarefas do Algoritmo**: Lucas Biasetton e Gustavo Rodriguez revisaram e consolidaram os passos do algoritmo, definindo-os em tarefas (tasks) dentro de uma fase. As tarefas incluiriam extrair citações, avaliar se a citação é um caso Sabin, e produzir os resultados finais, que seriam tabelas para validação ([01:28:02](#01:28:02)) ([01:31:06](#01:31:06)).

* **Divisão de Trabalho e Confiança no Processo**: Lucas Biasetton considerou a possibilidade de dividir as tarefas (especialmente os passos 0, 1 e 2\) para aliviar a carga e o prazo, mas Gustavo Rodriguez preferiu centralizar o trabalho para manter a confiança e evitar retrabalho, já que o processo é altamente iterativo e dependente dos passos anteriores ([01:32:48](#01:32:48)) ([01:35:27](#01:35:27)). Eles concordaram que Lucas Biasetton pode continuar a desenvolver a apresentação dos resultados, como o texto e as cores dos mapas ([01:39:35](#01:39:35)).

* **Definição de Comunicação e Cronograma**: Eles estabeleceram o dia 9 como meta para o projeto e definiram uma rotina de comunicação diária para validação e acompanhamento ([01:36:21](#01:36:21)). A sugestão de usar o Discord para manter um canal de comunicação aberto, evitando a necessidade de agendamentos formais, foi aceita para facilitar o contato imediato para validação de decisões ([01:37:42](#01:37:42)).

### Próximas etapas sugeridas

- [ ] Lucas Biasetton irá limitar a busca de casos aos do Climate Case Chart para a pesquisa e adquirir a versão atualizada do Excel de Colúmbia para obter os casos mais recentes.  
- [ ] Lucas Biasetton e Gustavo Rodriguez irão criar um novo script para extrair os dados em formato Markdown, rodar o rerrun no pipe, e revisar o algoritmo de classificação do país de origem (fase 3\) e de decisão (fase 4).  
- [ ] Gustavo Rodriguez fará todo o processo de refinamento do pipeline para garantir que o trabalho seja feito de forma eficiente e confiável.  
- [ ] Lucas Biasetton e Gustavo Rodriguez terão um 'touch point' de tempo variável todos os dias em horários sortidos para troca de informações, acompanhamento e validação do progresso.  
- [ ] Lucas Biasetton e Gustavo Rodriguez usarão um Discord ou Teams aberto para comunicação imediata, começando na manhã seguinte, onde Lucas Biasetton ficará online quando não estiver em reunião.  
- [ ] Lucas Biasetton continuará desenvolvendo a apresentação das informações (texto e cores dos mapas) no box, para que os dados possam ser inseridos assim que estiverem prontos.  
- [ ] Lucas Biasetton fechará o texto para a apresentação, ciente de que dependerá dos resultados para ter algumas respostas.

*Revise as anotações do Gemini para checar se estão corretas. [Confira dicas e saiba como o Gemini faz anotações](https://support.google.com/meet/answer/14754931)*

*Envie feedback sobre o uso do Gemini para criar notas [breve pesquisa.](https://google.qualtrics.com/jfe/form/SV_9vK3UZEaIQKKE7A?confid=jM2HWEJTbn8J_K2oa38NDxIOOAIIigIgABgFCA&detailid=standard)*

# 📖 Transcrição

3 de mar. de 2026

## Global Trends \- Transcrição

### 00:00:00 {#00:00:00}

   
**Gustavo Rodriguez:** الله E aí, não escuto. K. Quando meu fone buga, ele só conecta de novo. Se eu ponho na caixinha e conecto depois de abrir a caixinha de novo. Hum.  
**Gustavo Rodriguez:** E agora você me vê e tal. Não,  
**Lucas Biasetton:** Alô.  
**Gustavo Rodriguez:** agora sim.  
**Lucas Biasetton:** Ah, caraca, difícil, difícil.  
**Gustavo Rodriguez:** Que bug tudo no beta essas  
**Lucas Biasetton:** Pera aí, eu tô,  
**Gustavo Rodriguez:** p\*\*\*\*.  
**Lucas Biasetton:** deixa eu ligar meu fone para variar. Ele não conectou sozinho. Tudo certo aí?  
**Gustavo Rodriguez:** Tudo bem? Você tá bem também?  
**Lucas Biasetton:** Tô bem, tô bem.  
**Gustavo Rodriguez:** Alô? Ah, maravilha.  
**Lucas Biasetton:** Oi. Eu é tá conectando no fone,  
**Gustavo Rodriguez:** Conectados.  
**Lucas Biasetton:** inclusive eu vou almoçar com a Mari na quinta-feira,  
**Gustavo Rodriguez:** Uh, legal.  
**Lucas Biasetton:** então vamos ver.  
**Gustavo Rodriguez:** Muito bem. Depois de amanhã tá  
**Lucas Biasetton:** Exato. Eh,  
**Gustavo Rodriguez:** perto.  
**Lucas Biasetton:** tá. Eu deixei o Claudinho rodando aqui que eu tava testando um negócio novo, aquela extensão do Chrome eu não tinha usado ainda.  
   
 

### 00:05:29 {#00:05:29}

   
**Gustavo Rodriguez:** Ah, aquele navega sozinho. Não tinha usado ainda. Ele nunca tinha pedido para usar.  
**Lucas Biasetton:** Então, não, eu tô por curiosidade, enquanto a gente não começava aqui, eu mandei ele procurar um apartamento em Londres nas especificações que eu queria, no preço que eu preciso e aí ele tá rodando,  
**Gustavo Rodriguez:** E  
**Lucas Biasetton:** tá rodando, sei lá.  
**Gustavo Rodriguez:** aí?  
**Lucas Biasetton:** Eh, mas vamos lá, vamos falar de Joana e Kate agora, né? É o seguinte,  
**Gustavo Rodriguez:** Aham.  
**Lucas Biasetton:** eu comecei a ter aquelas ideias que eu te falei de como a gente poderia alterar um pouco a nossa estrutura de captura de informações, porque eu fiz aquele mini projeto com elas e eu vi que aplicando a nossa metodologia eu não  
**Gustavo Rodriguez:** Так.  
**Lucas Biasetton:** capturava todas as citações que eu queria. E aí eu comecei a pensar, tipo, em formas de ajustar o nossa a nossa arquitetura. para que a gente conseguisse capturar um número maior de estações e para que a gente conseguisse corrigir as classificações que eu sabia que estavam erradas. Hã,  
**Gustavo Rodriguez:** Certo.  
**Lucas Biasetton:** então a princípio era isso. E aí elas pediram pra gente preparar eh um mapa em que a gente colocaria as principais jurisdições, as top cinco citantes e quantas vezes elas citam, fazer tipo um mapinha igual que a gente fez, só que só colocar as top cinco porque seria um mapa estático, né?  
   
 

### 00:06:56 {#00:06:56}

   
**Lucas Biasetton:** Ã, e aí elas pediram pra gente fazer isso e eu falei: "Beleza,  
**Gustavo Rodriguez:** Ah.  
**Lucas Biasetton:** vamos fazer". Eh, e aí eu tava revisando metodologia e tal, eu falei: "Putz, eu acho que tem um espaço para melhorar que esses dois pontos, né, capturar mais citações e e classificar elas corretamente. E além disso, eu fiz uns testes de uns mapas para testar, tipo, ah, as top cinco jurisdições, mais ou menos para ver o que começava a aparecer. E aí eu vi que as top cinco jurisdições eram tipo Austrália primeiro,  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** Nova Zelândia segundo, Reino Unido terceiro, Brasil quarto e Canadá quinto. Eu falei: "Pô, Brasil, OK, que eu dei uma olhada nos dados do Brasil e faziam um sentido." Aí eu fui entrar nos dados da Austrália e aí que entra aquela preocupação que a gente teve de linkar as citações que a gente  
**Gustavo Rodriguez:** Mm.  
**Lucas Biasetton:** encontra com os casos do Sabing. Sabe por quê? Porque a Austrália cita muitas decisões do Reino Unido,  
**Gustavo Rodriguez:** Mm.  
**Lucas Biasetton:** é o país que mais cita, só que as decisões que ela cita do Reino Unido são decisões de common law antiguíssimas que não tem nada a ver com o que a gente tá pesquisando.  
   
 

### 00:08:12

   
**Lucas Biasetton:** Então, tipo assim, eu coloquei a Austrália,  
**Gustavo Rodriguez:** Ah, olha  
**Lucas Biasetton:** eh, eu coloquei a Austrália e aí eu fui tipo ver o ano.  
**Gustavo Rodriguez:** só,  
**Lucas Biasetton:** Se quiser eu até te mostro aqui, ó. Vou te vou abrir aqui,  
**Gustavo Rodriguez:** 1820\.  
**Lucas Biasetton:** cara. Menos 1600 e cacetada.  
**Gustavo Rodriguez:** Ai, que l  
**Lucas Biasetton:** É tipo assim, desesperador,  
**Gustavo Rodriguez:** c\*\*\*\*\*\*.  
**Lucas Biasetton:** velho. Deixa eu te mostrar aqui. Eh,  
**Gustavo Rodriguez:** Loucura.  
**Lucas Biasetton:** cadê? Opa, pera aí, deixa eu ver. Será se eu deixa eu meter Austrália aqui. Source Australia. E aí, tipo, eu vim, onde é que era? É, será que eu Ah, pera, talvez não fosse, cara, que eu já abri tanto Excel aqui que eu nem sei mais. Deixa eu ver se é esse aqui, ó. Sited ear. Olha isso. 1330, 1466\.  
**Gustavo Rodriguez:** Meu Deus, que  
**Lucas Biasetton:** E aí eu fui olhar e realmente é ano isso aqui.  
   
 

### 00:09:18 {#00:09:18}

   
**Gustavo Rodriguez:** loucura.  
**Lucas Biasetton:** Eh, então assim, esse é o problema da gente não ter uma ligação com casos do climate case, a gente acaba capturando uma série de informações que são aleatórias.  
**Gustavo Rodriguez:** Boa,  
**Lucas Biasetton:** Então,  
**Gustavo Rodriguez:** muito bem  
**Lucas Biasetton:** minha sugestão é a gente limitar a buscas de  
**Gustavo Rodriguez:** contada.  
**Lucas Biasetton:** casos do Climate Case Chart. Eu vou parar de compartilhar que meu computador tá sofrendo aqui com Claudinho em Londres. Eh, mas é a gente limitar por casos do Climate Case Chart.  
**Gustavo Rodriguez:** Ah.  
**Lucas Biasetton:** E aí a gente vai ter que explicar isso para elas. Enfim, talvez elas queiram incluir mais alguns casos além dos que estão no climate case chart, mas eu faria a busca usando esse esse filtro agora, sabe? Porque senão, cara, vai virar bagunça. E aí eu queria contar para você o que que eu fiz na pesquisa que eu fiz com elas, porque talvez funcione aqui. Porque assim, quando eu apliquei a, eu acho que eu te falei, né, o que que era pesquisa com elas, era basicamente tinham casos corporativos,  
**Gustavo Rodriguez:** Ah.  
**Lucas Biasetton:** climático, corporate climate cases e a teoria delas é que esses casos eram muito influenciados pelos government framework cases, os casos contra o governo que vieram antes,  
   
 

### 00:10:41 {#00:10:41}

   
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** que elas queriam ajuda é nos casos contra empresas, quem e quantas vezes são citados casos governamentais. né, casos contra os governos, que elas queriam usar isso para fundamentar a teoria delas de que os casos contra os governos que vieram primeiro estão sendo  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** utilizados como base pros casos contra empresas que vieram depois. E aí eu apliquei a nossa, tipo, eu basicamente peguei a nossa estrutura e apliquei para ver se funcionava e ele tava perdendo muitas citações. E aí o que eu fiz,  
**Gustavo Rodriguez:** Como você aplicou? Fala antes disso.  
**Lucas Biasetton:** cara?  
**Gustavo Rodriguez:** Como foi esse  
**Lucas Biasetton:** Eu basicamente eu basicamente peguei o que a gente tinha no GitHub,  
**Gustavo Rodriguez:** aplique?  
**Lucas Biasetton:** só que aí eu limitei as decisões,  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** na verdade eu limitei a todos os documentos de casos corporativos e toquei os mesmos scripts e etc, entendeu?  
**Gustavo Rodriguez:** Tá. Aí você editou os scripts, tipo, pediu para ir a editar e você deu os scripts, tipo, aplica esses scripts nesse recorte de base de dados com esse  
**Lucas Biasetton:** é com o objetivo de encontrar citações a casos corporativos,  
**Gustavo Rodriguez:** objetivo.  
**Lucas Biasetton:** mas a estrutura basicamente foi bem próxima assim, tipo, eu usei a estrutura que a gente tinha montado para capturar essas citações,  
   
 

### 00:11:56 {#00:11:56}

   
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** só que eram poucos, eram poucos documentos e poucos casos. Eram tipo 20 casos e um número de documentos pequeno, então eu conseguia. Calma, você tá me ouvindo?  
**Gustavo Rodriguez:** Revisão nãoamente também.  
**Lucas Biasetton:** Pera aí. Deixa eu desligar o Claudinho aqui que ele tá louco aqui.  
**Gustavo Rodriguez:** Eu acho que eu travei,  
**Lucas Biasetton:** Eu acho que ele não vai.  
**Gustavo Rodriguez:** eu travei, eu travei, eu travei. minha vez.  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** Agora eu iniciei o cloud no terminal e aí imediatamente,  
**Lucas Biasetton:** tá,  
**Gustavo Rodriguez:** cara, fazer upgrade de notebook,  
**Lucas Biasetton:** tá,  
**Gustavo Rodriguez:** cara, tava irritando.  
**Lucas Biasetton:** tá. Sim. Eh, mas então, e aí um negócio que eu fiz, que eu senti que o o recall, né, o número de capturas ficou muito mais avançado, foi um primeiro passo antes de começar tudo que bas que eu eu posso te mandar o prompt, inclusive é que tá no outro computador, mas era um step antes de começar tudo que eu que ele chamou,  
**Gustavo Rodriguez:** Ja.  
**Lucas Biasetton:** né? Porque ele que sugeriu de build knowledge. Então, que que ele tava me falando?  
   
 

### 00:12:58 {#00:12:58}

   
**Lucas Biasetton:** Capturar os casos governamentais só usando o nome dá uma janela de contexto muito pequena. Como a gente tem a base de Colúmbia com muitas informações, ele usou a base de Colúmbia para construir o knowledge sobre cada um dos casos governamentais. Então, ele tinha tipo o ano, as partes, a breve descrição do caso, tudo que tem na base de Colúmbia.  
**Gustavo Rodriguez:** Tá legal.  
**Lucas Biasetton:** Ele usou isso para É,  
**Gustavo Rodriguez:** Eu fiz isso no es também.  
**Lucas Biasetton:** então achei isso muito bom, tipo para gerar contexto.  
**Gustavo Rodriguez:** É aprendizados do primeiro run que a gente teve.  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** É isso, é importante mesmo.  
**Lucas Biasetton:** E aí, e como a gente já tem a a base de Colúmbia pronta com muito contexto, ã, eu achei que talvez faria sentido a gente fazer algo parecido. Eh, mas assim, end game é parecido com o que a gente já fez,  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** mas é limitar um pouco mais ã para casos climáticos, realmente, que isso a gente nem tinha pensado. Eh, e, ã,  
**Gustavo Rodriguez:** Ah.  
**Lucas Biasetton:** que mais que eu tinha te falado? Ah, ele pegar a transcrição exata, tipo, ele não pegar uma transcrição que ele inventa, sabe?  
   
 

### 00:14:05

   
**Lucas Biasetton:** Tipo, a gente fazer um prompt bem rígido na extração da citação, que ele consiga pegar, tipo, a transcrição exata daquilo que ele tá extraindo. Isso foi um negócio que eu fiz, que ajudou na validação depois também,  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** porque aí se a gente quiser, a gente pode botar um outro agente para ler os só os os trechos pequenos de transcrição para validar. Eu acho que era isso.  
**Gustavo Rodriguez:** Uhum. Boa. Maravilha.  
**Lucas Biasetton:** Você acha que faz sentido?  
**Gustavo Rodriguez:** Para c\*\*\*\*\*\*. E tem um tem jeito de fazer isso, né? O que me ocorreu enquanto c\*\*\*\*\*\*. Tem uma motos sererra. Tá ouvindo?  
**Lucas Biasetton:** Não.  
**Gustavo Rodriguez:** Ah,  
**Lucas Biasetton:** Ah,  
**Gustavo Rodriguez:** ótimo. Então,  
**Lucas Biasetton:** você trocou de fone.  
**Gustavo Rodriguez:** beleza. É, eu tô com fone novo.  
**Lucas Biasetton:** Nice.  
**Gustavo Rodriguez:** É, é um, é incrível. Chama, é um da JBL. É inturicular, mas ele tem uma presilha por atrás da orelha,  
**Lucas Biasetton:** Ah, nossa, não  
**Gustavo Rodriguez:** então eu não vou perder.  
**Lucas Biasetton:** conhecia.  
**Gustavo Rodriguez:** Ele vai dar minha orelha pra caixa sempre.  
   
 

### 00:15:02 {#00:15:02}

   
**Gustavo Rodriguez:** Ele não cai nem f\*\*\*\*\*\*. E é resistente a  
**Lucas Biasetton:** Nossa, bom demais. É, o meu é JBL também,  
**Gustavo Rodriguez:** água.  
**Lucas Biasetton:** mas é um, sabe, um mais É exato.  
**Gustavo Rodriguez:** É o que você comprou em Londres, naquele perdido que você sofreu lá.  
**Lucas Biasetton:** Exato.  
**Gustavo Rodriguez:** Da hora.  
**Lucas Biasetton:** Mas é fácil de perder também isso aqui.  
**Gustavo Rodriguez:** É, então é fácil de perder. Eu eu tinha medo desses fones por causa disso,  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** mas aí veio a presilinha, eu falei: "Hum, a bateria dura bastante, eu gostei bastante." Ó a caixinha.  
**Lucas Biasetton:** Nossa, gigante,  
**Gustavo Rodriguez:** É,  
**Lucas Biasetton:** c\*\*\*\*\*\*.  
**Gustavo Rodriguez:** ela tem uma carga boa de bateria, tá? Mas caba no bolso. Ã, então, ó, caminhos possíveis. primeiro que me correu fazer esse buildup, esse esse step to build knowledge antes e dar ids pros casos e verificar esses IDs para limitar o escopo das conexões a casos identificados na tabela.  
**Lucas Biasetton:** Hum. Hum. inteligente.  
**Gustavo Rodriguez:** Eu acho que isso vai vai ser mais straightforward do que fazer a LELLM rodar o conteúdo dos documentos e avaliar se aquilo é um caso climático de fato,  
   
 

### 00:16:16

   
**Lucas Biasetton:** Não é isso. Isso.  
**Gustavo Rodriguez:** em que  
**Lucas Biasetton:** Eu acho que não adianta isso.  
**Gustavo Rodriguez:** medida.  
**Lucas Biasetton:** Avaliação, caso climático. Eu já desisti dessa ideia. Eu acho que a gente vai ter que ser bem  
**Gustavo Rodriguez:** Eh,  
**Lucas Biasetton:** M.  
**Gustavo Rodriguez:** porque isso só daria hoje em dia com os aprendizados do do nosso primeiro run. e do Aeges, eu só confiaria nesse tipo de autocom usando um modelo caro e um call por documento.  
**Lucas Biasetton:** É, não.  
**Gustavo Rodriguez:** Ia sair  
**Lucas Biasetton:** Sim, não. É, eu não acho que que vale entrar nesse nível de detalhe.  
**Gustavo Rodriguez:** caríssimo.  
**Lucas Biasetton:** Por isso que assim, a gente tem certeza que o que está no saving é um caso climático, então tipo, é a melhor régua que que a gente pode ter, sabe?  
**Gustavo Rodriguez:** É sim. Eu acho que é um caminho mais tranquilo. E outra  
**Lucas Biasetton:** Mas aí então o que você tá falando basicamente é para nessa lista de build knowledge,  
**Gustavo Rodriguez:** coisa,  
**Lucas Biasetton:** a ideia seria a gente  
**Gustavo Rodriguez:** aplicar meta dado nos documentos.  
**Lucas Biasetton:** pegar  
**Gustavo Rodriguez:** E cara, eu faria tanta coisa diferente hoje em dia no que a gente fez.  
   
 

### 00:17:14

   
**Gustavo Rodriguez:** Tem tanto improvement possível para Mas a gente tem um objetivo concreto e curto que  
**Lucas Biasetton:** tá. Nossa, parece que eu tô num hospice,  
**Gustavo Rodriguez:** é Sim ou no céu para você  
**Lucas Biasetton:** velho.  
**Gustavo Rodriguez:** positivo.  
**Lucas Biasetton:** Acho que não é não.  
**Gustavo Rodriguez:** É escritório, né? Mais hospício mesmo.  
**Lucas Biasetton:** Eu peguei uma sala aqui que minha sala tem gente.  
**Gustavo Rodriguez:** Muito bem.  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** É essa vibe.  
**Lucas Biasetton:** M.  
**Gustavo Rodriguez:** Eh, porque assim, já que a gente vai pisar nesses terrenos de novo e rodar script do c\*\*\*\*\*\*, a gente tem um ganho muito grande a partir de pouco trabalho em refinar pelo menos  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** algumas etapas do pipe, especialmente as mais anteriores, e por algumas delas para rodar de novo, para afinar ao que a gente tem,  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** tendo em vista o objetivo de curto prazo de produzir o que a Joana pediu. Claro, isso é prioridade, mas eu diria aqui pra gente no que esse projeto tocar no pipe, na nas bases de dados que a gente tem, a gente vê o que tá lá, como chegou lá e ver se alguma tecnologia ou informação nova que a gente acumulou nesse tempo não permite melhorar essa p\*\*\*\*.  
   
 

### 00:18:21 {#00:18:21}

   
**Lucas Biasetton:** Так.  
**Gustavo Rodriguez:** até para não c\*\*\*\* nada no pipe, mexendo em coisas pontuais do pipe, sem olhar pro resto, porque, tipo, tem rola umas incompatibilidade. Por exemplo, imagina o pipe tem cinco scripts, o três e o quatro dependem da output do dois e a gente vai mexer no dois, só que muda o esquema, né, no número e o tipo de coluna, blá blá blá, e caga a execução do três e do quatro ou mexe no três e do quatro sem ajustar o dois quando forar o piping,  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** entendeu? Eh, e tem isso então,  
**Lucas Biasetton:** Não, eu concordo.  
**Gustavo Rodriguez:** a nível  
**Lucas Biasetton:** Sabe por quê? Porque elas, na última conversa que eu tive com elas,  
**Gustavo Rodriguez:** de  
**Lucas Biasetton:** elas insistiram muito em falar que a gente deveria publicar um artigo de metodologia.  
**Gustavo Rodriguez:** legal.  
**Lucas Biasetton:** Elas falaram,  
**Gustavo Rodriguez:** Eu  
**Lucas Biasetton:** tipo, elas falaram: "Cara, eu acho que vocês t que publicar,  
**Gustavo Rodriguez:** adoraria.  
**Lucas Biasetton:** você Gustavo, precisam, precisam, precisam". Aí eu falei: "Pô, a gente pode pensar, mas vocês não querem botar o nome de vocês também?" Porque,  
   
 

### 00:19:14 {#00:19:14}

   
**Gustavo Rodriguez:** Eh,  
**Lucas Biasetton:** p\*\*\*\*, se se eu e você publicarmos, ninguém vai ler essa m\*\*\*\*. Mas se elas publicarem e aí elas falaram: "Ah, não, mas a gente não fez nada" e tal.  
**Gustavo Rodriguez:** eh.  
**Lucas Biasetton:** Tipo, o mérito é todo de vocês e é o que eu tô pensando em fazer, abrir uma chamada. E eu só tô falando tudo isso porque talvez vale a gente rever metodologia considerando todas essas discussões, mas abri uma chamada eh para Call for paper de Colúmbia até o dia 15 de março para Junior Scholars,  
**Gustavo Rodriguez:** Você  
**Lucas Biasetton:** eh que então em fase de early draft. Então, a gente não precisa de um artigo pronto, mas a gente poderia submeter uma ideia de artigo e aí  
**Gustavo Rodriguez:** não vai acreditar, mas eu eu tava falando de escrever esses dias com a Deia e o Adriano, tem um doutorado também.  
**Lucas Biasetton:** é  
**Gustavo Rodriguez:** É porque eu tive umas ideias de de recorte acadêmico do que eu faço, do que eu tô fazendo hoje em dia. E tem muita coisa e eu preciso me fazer presente online como,  
**Lucas Biasetton:** sim,  
**Gustavo Rodriguez:** sabe,  
**Lucas Biasetton:** sim, sim, sim.  
**Gustavo Rodriguez:** vibes linkinhas tipo de balaquisse que profissionalmente relevante.  
**Lucas Biasetton:** Não é isso?  
   
 

### 00:20:18

   
**Gustavo Rodriguez:** E aí eu tô, cara, tô nessa onda.  
**Lucas Biasetton:** Não.  
**Gustavo Rodriguez:** Vamos aproveitar.  
**Lucas Biasetton:** Tá. Então eu acho que porque eu só tô falando isso porque eu acho que vale a gente, se a gente vai rodar de novo, talvez vale a gente fazer os ajustes, enfim, que vão ser meio corridos, mas porque aí a gente já consegue ter uma base para um artigo que a gente pode publicar em alguma revista muito pica.  
**Gustavo Rodriguez:** daqui algum tempo, depois de mais  
**Lucas Biasetton:** É. E é, mas tipo assim,  
**Gustavo Rodriguez:** refinimento.  
**Lucas Biasetton:** eu acho que já vale a gente publicar, se a gente conseguir essa galera de Colúmbia, a gente já,  
**Gustavo Rodriguez:** Não,  
**Lucas Biasetton:** eu imagino que eles vão é e agora é e e o que elas querem  
**Gustavo Rodriguez:** porque agora é só fase draft, né? Tudo bem, a gente tem só draft  
**Lucas Biasetton:** também,  
**Gustavo Rodriguez:** agora.  
**Lucas Biasetton:** a gente não precisa do artigo de metodologia pronto pro que elas querem, porque elas querem basicamente os mapas com os resultados falando com quatro parágrafos,  
**Gustavo Rodriguez:** Ah, claro. Sim.  
**Lucas Biasetton:** tá ligado? Acho um negócio extremamente  
**Gustavo Rodriguez:** Não, isso ficou claro. Isso ficou claro.  
   
 

### 00:21:04 {#00:21:04}

   
**Lucas Biasetton:** objetivo.  
**Gustavo Rodriguez:** Mas eu queria entender a data para esse deliver para  
**Lucas Biasetton:** Então, eu tinha combinado de conversar com elas na  
**Gustavo Rodriguez:** elas.  
**Lucas Biasetton:** segunda.  
**Gustavo Rodriguez:** Dá suave, tranquilíssimo.  
**Lucas Biasetton:** É,  
**Gustavo Rodriguez:** Ah, que você tá f\*\*\*\*\* de coisa,  
**Lucas Biasetton:** não,  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** não, mas isso é meu foco.  
**Gustavo Rodriguez:** Não é tão tranquilíssimo assim.  
**Lucas Biasetton:** Isso é meu foco.  
**Gustavo Rodriguez:** Ah,  
**Lucas Biasetton:** Isso aí.  
**Gustavo Rodriguez:** ótimo. Então, tá. Não. Beleza. Então, tranquilíssimo. A gente tendo budget, tendo esse tempo, dá super, a gente vai refinando e dá para fazer todo o trabalho de revisão do pipe,  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** polir o pipe ã no caminho assim.  
**Lucas Biasetton:** E você acha que dá para fazer usando o Gemen já que a gente tem que eu tenho crédito  
**Gustavo Rodriguez:** Tranquilo. Dá,  
**Lucas Biasetton:** ainda?  
**Gustavo Rodriguez:** dá. O 3.1 Pro passou o Cloud 4.6 em vários benchmarks.  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** Eles são pau a pau, mas tipo tão bom quanto e mais barato. Então,  
**Lucas Biasetton:** tá.  
**Gustavo Rodriguez:** bora.  
**Lucas Biasetton:** Não, tá bom.  
   
 

### 00:21:58 {#00:21:58}

   
**Lucas Biasetton:** Eh, então, pensando aqui em próximos passos, eu acho que a gente, eu vou começar, eu sei que tá transcrevendo, mas eu vou anotar aqui só para me organizar, porque eu acho que a gente vai ter que,  
**Gustavo Rodriguez:** Да.  
**Lucas Biasetton:** assim, começando step one, né, a gente pode pegar a versão mais atualizada do Excel de Colúmbia para pra gente ter os casos mais recentes.  
**Gustavo Rodriguez:** Tá.  
**Lucas Biasetton:** Eh, e aí, eh, você não vai precisar mudar nada naqueles steps de extração e etc, né?  
**Gustavo Rodriguez:** É, é algo é outra coisa que eu  
**Lucas Biasetton:** Download.  
**Gustavo Rodriguez:** refaria, porque a gente guardou na época os arquivos num formato de texto dentro da base de dados X.  
**Lucas Biasetton:** Mhm.  
**Gustavo Rodriguez:** E Markdown File é otimizado para AI, tipo AI tem uma relação melhor com texto estruturado em Mark.  
**Lucas Biasetton:** Так,  
**Gustavo Rodriguez:** Eu salvaria, eu mudaria o formato do dos arquivos. Eu não sei se precisa baixar de novo,  
**Lucas Biasetton:** так.  
**Gustavo Rodriguez:** mas isso é o de menos. Baixou super rápido. Esse script é rápido. Eh,  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** mas aí baixar para já salvar em Mark e rodar o rerrun no pipe depois de polir o pipe já nessa base aprimorada.  
   
 

### 00:23:23

   
**Lucas Biasetton:** Очim.  
**Gustavo Rodriguez:** Isso é rápido.  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** Isso é de menos.  
**Lucas Biasetton:** tá. Então, ã, beleza. Esse, esse é tranquilo, step one. Então, eu vou baixar a versão atualizada do Excel e aí a gente faz um novo script com para extrair com Markdown. Eh, aí o step dois, deixa eu até lembrar aqui quais que eram os nossos steps que eu já nem lembro mais. Pera aí. Ah, aí, então a a nossa fase zero era iniciar database inicialization. Então, isso eu acho que não sei se vai mudar alguma coisa, né?  
**Gustavo Rodriguez:** Não,  
**Lucas Biasetton:** Ã,  
**Gustavo Rodriguez:** não. Talvez com ID dos documentos. É uma coluna nova,  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** talvez.  
**Lucas Biasetton:** Aí a fase um era download dos PDFs, não vai mudar, né? E a fase dois era extração dos  
**Gustavo Rodriguez:** Eh,  
**Lucas Biasetton:** textos.  
**Gustavo Rodriguez:** download não muda. Estação dos textos. O jeito de salvar os textos extraídos vai para  
**Lucas Biasetton:** Beleza? Tá. Eh, calma  
**Gustavo Rodriguez:** Mark.  
**Lucas Biasetton:** aí.  
   
 

### 00:24:37 {#00:24:37}

   
**Lucas Biasetton:** Beleza. Aí o step 3 era country classification. que eu acho que era  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** bem,  
**Gustavo Rodriguez:** Vamos a nota para revisar o algoritmo desse classificação de país,  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** pra gente revisar o método que ele classifica, usa classificar, o processo que ele percorre para classificar, para chegar na classificação. Acho que é digno de de uma atençãozinha e a gente vê se fazer alguma coisa com  
**Lucas Biasetton:** Tá. Tá aí o step four,  
**Gustavo Rodriguez:** isso.  
**Lucas Biasetton:** ã, step four, o step four era, cadê? Decision classification. Eh,  
**Gustavo Rodriguez:** Mais sobre  
**Lucas Biasetton:** então aí isso aqui era aquela,  
**Gustavo Rodriguez:** isso.  
**Lucas Biasetton:** a gente tinha um, a gente tinha um, um método duplo de classificar decisões, lembra que a gente ia primeiro pelo nome e aí se o nome tivesse decision e etc,  
**Gustavo Rodriguez:** Certo?  
**Lucas Biasetton:** a gente já considerava que era uma decisão judicial. Senão é aí aí a a  
**Gustavo Rodriguez:** E aí a gente pegou do do site em vez do bagulho depois, né? Tava uma bosta.  
**Lucas Biasetton:** descrição do nome do arquivo na tabela na parte final tinha tipo decision, judgment e etc.  
   
 

### 00:25:48

   
**Gustavo Rodriguez:** Угу.  
**Lucas Biasetton:** E aí se não tivesse, a gente passava uma uma um modelo para para ver se realmente era uma decisão ou não.  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** Será que esse a gente  
**Gustavo Rodriguez:** Ã, mesma nota do último com talvez dois asteriscos, se não um só. A gente pode ver isso hoje. Inclusive, eu tô só tentando eh marcar, passar pelo pipe inteiro, ver ponto de atenção e aí a gente mergulha  
**Lucas Biasetton:** sim não? Tá. Então eu vou pro próximo.  
**Gustavo Rodriguez:** mais.  
**Lucas Biasetton:** O cinco era dividido em vários, tá? O primeiro,  
**Gustavo Rodriguez:** Eu  
**Lucas Biasetton:** você lembra que o quinto era Hum, pera,  
**Gustavo Rodriguez:** tô com metodólar de aberto aqui. Que documento você tá  
**Lucas Biasetton:** cara. Eu eu gerei um novo a partir do GitHub.  
**Gustavo Rodriguez:** vendo?  
**Lucas Biasetton:** Eu mandei ele ler o GitHub e me falar fase por fase.  
**Gustavo Rodriguez:** No GitHub tem no repositório tem uma pasta dentro de pegado de mutle e documentation ali. Tem um HTML Metodology.  
**Lucas Biasetton:** Ah,  
**Gustavo Rodriguez:** É de a última edição dele,  
**Lucas Biasetton:** pera aí.  
**Gustavo Rodriguez:** sei lá, de quando é que tá no GitHub marcado.  
**Lucas Biasetton:** Quer compartilhar  
   
 

### 00:27:09

   
**Gustavo Rodriguez:** Nome do PC não fica,  
**Lucas Biasetton:** aí?  
**Gustavo Rodriguez:** tá? Ai, pera aí. Ai,  
**Lucas Biasetton:** Saud.  
**Gustavo Rodriguez:** obrigado. Vamos lá. Tá, tá, tá. Passamos por isso.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Só ID. Ah, tem uma aí da ID. Ah, mas é o countri para fim de pegar a citação só,  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** Extrai da própria  
**Gustavo Rodriguez:** Já um comentário aqui.  
**Lucas Biasetton:** base.  
**Gustavo Rodriguez:** A gente falou de colocar o ID nessa nessa fase, né?  
**Lucas Biasetton:** O ID quer dizer o  
**Gustavo Rodriguez:** Eh,  
**Lucas Biasetton:** quê?  
**Gustavo Rodriguez:** o ID, então, o ID do quê? Exatamente? do proceeding, do documento, da decision, tipo da decisão,  
**Lucas Biasetton:** Cara, eu eu sinceramente tô achando esse eu não sei se esse esse arquivo de metodologia é o mais  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** atualizado.  
**Gustavo Rodriguez:** Será? p\*\*\* que data tá isso aqui? Version 5.3.  
**Lucas Biasetton:** Não, talvez seja,  
**Gustavo Rodriguez:** Não,  
**Lucas Biasetton:** mas que é estranho ele colocar como fez o ano.  
**Gustavo Rodriguez:** mas a gente pode checar.  
**Lucas Biasetton:** Vai em scripts para ver como os scripts estão tão numerados.  
   
 

### 00:28:45

   
**Gustavo Rodriguez:** Ah, não. Ele pegou dos scripts. O seu. É que esses essas fases aqui tem mais de um, tipo, ã, quer ver? Aqui tem 0 a 8 9 aqui tem quatro. Só que face to deve ter mais de um script. Ou isso aqui de fato é antigo. Vamos confirmar o bagulho que você escreveu. Não é tudo atualizado. Se for do esquema de ter data nessa p\*\*\*\*. Fica nota. Pera aí. Eu tô com Clud. Manda o que você tava vendo para mim.  
**Lucas Biasetton:** Tá,  
**Gustavo Rodriguez:** A análise que você fez do Gub.  
**Lucas Biasetton:** tá. Pera aí. É porque eu tava pedindo para ele o se eu fosse mudar de modelo, o que que ele achava que tinha que tinha que mudar fase a fase.  
**Gustavo Rodriguez:** modelo de Lalem.  
**Lucas Biasetton:** É só que aí ele foi escrevendo, entendeu? Pera aí.  
**Gustavo Rodriguez:** Ah, tá.  
**Lucas Biasetton:** Cadê o chat? Eu quer que eu mande pro Vou mandar pro WhatsApp que é mais fácil. Pronto, mandei.  
**Gustavo Rodriguez:** Tá peg Ja.  
**Lucas Biasetton:** Então, mas basicamente, ó, a gente a gente baixava tudo e extraí o texto, classificava o país de origem da decisão,  
   
 

### 00:31:00

   
**Gustavo Rodriguez:** Isso.  
**Lucas Biasetton:** depois classificava se era uma decisão ou não,  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** que é o face for. Depois source jurisdiction identification. Eu não sei qual que é a diferença do 3 pro 5.1, mas beleza. Aí 5.2, extrair as citações aqui, tá? A gente extraía todas as citações. Aí o 5.2.5 C seria aquele aquele extra que eu te falei de extrair um crunch exato 5.3 identificação da origem.  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** É, cara, o f\*\*\* é que eu acho que esse grosso aqui a gente vai ter que refazer tudo, velho. É. E aí o 5.5 seria o agente.  
**Gustavo Rodriguez:** cinco.  
**Lucas Biasetton:** Isso é novo também. A gente não tinha antes. Seis, nem sei o que que é. Sete aí a classificação dos resultados e o oito é  
**Gustavo Rodriguez:** Mm. Cara, dá para tem muita coisa para ajustar dado que a gente sabe fazer hoje em dia.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Eh, um jeito de fazer isso rápido, tipo de dar um Kickstart nisso rápido, na verdade. Eh, porque assim, eu te falei do do Aeges, né?  
   
 

### 00:32:51

   
**Gustavo Rodriguez:** Mais ou menos como eu montei o bagulho.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Legal, deixa te mostrar. Tem aqui o próprio Cloud já tem subagentes salvos,  
**Lucas Biasetton:** Uh.  
**Gustavo Rodriguez:** cada um com uma um escopo e um conjunto próprio de contextos para aperfeiçoar o a capacidade do agente nesse escopo. Tipo, sei lá, ã, aqui esse security agent, ele tem um monte de documentação plugada,  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** referenciada nele sobre segurança. O backend tem documentação de do dos das linguagens e frameworks que esse projeto usa no backend. Eh, tem o próprio Cloud, eu criei uns plugins, eu criei skills e o projeto aqui em Docs  
**Lucas Biasetton:** Угуm.  
**Gustavo Rodriguez:** Reference tem a documentação crua de todo tudo que o projeto usa, não só a especificação dos das funcionalidades, mas a documentação da fonte, tipo, sei lá, o projeto é hosted pelo Google Cloud Platformer,  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** que tem a documentação pertinente do GCP. E ah, uma coisa que eu não tinha não fazia tão bem na na no primeiro run que a gente teve do seu projeto, mas que tá melhor agora é encadear as coisas em estruturas.  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** Então, por exemplo, essa pasta aqui tem um index.  
   
 

### 00:34:23

   
**Gustavo Rodriguez:** Esse índex, ele lista onde tá, que documentação dentro da pasta que ele participa e dá um resumo do que tem lá dentro. Então, tipo, é tipo um primeiro primeira ponto de navegação do dos robôs aí dentro do repositório para saber onde pegar contexto e o que fazer com ele. Que mais aqui é relevante?  
**Lucas Biasetton:** Так.  
**Gustavo Rodriguez:** E eu passei a documentar progresso, tesques e tal projeto com uma base de dados para isso, simplesinha assim. Começou documente,  
**Lucas Biasetton:** Угу.  
**Gustavo Rodriguez:** comecei documentando com Markdow e passei a isso. Como se aplica no nosso no no projeto de PhD? Ah, cadê me aí? Vamos lá. Script por script. Aqui por enquanto só rodar o bagulho para ter índice, índice não, ID nos documentos relevantes pra gente se manter dentro da Sabin, ou seja, só do que tem ID no download.  
**Lucas Biasetton:** Pera aí, pera aí, pera aí, calma aí um segundo que eu tirei o fone e você sumiu.  
**Gustavo Rodriguez:** Ah,  
**Lucas Biasetton:** Pera aí. Calma. Parei, eu parei em ID,  
**Gustavo Rodriguez:** não falei de três  
**Lucas Biasetton:** na verdade eu acho que foi no primeiro.  
**Gustavo Rodriguez:** vezes.  
   
 

### 00:35:53 {#00:35:53}

   
**Gustavo Rodriguez:** Qual ed você parou? Tá. Em nesse script aqui, o zero intilizabase, só tem um uma coisa, talvez por enquanto, que é ã adicionar a coluna de ID onde ela for relevante no no na base de dados toda, nas tabelas da base de dados e adaptar os clips de baixo nesse ponto a manterem o ID, tá ligado?  
**Lucas Biasetton:** Tá com ID.  
**Gustavo Rodriguez:** tipo processarem o ID também o  
**Lucas Biasetton:** Você quer dizer o ID  
**Gustavo Rodriguez:** número único que identifica o caso.  
**Lucas Biasetton:** tá no saving center.  
**Gustavo Rodriguez:** Isso no dentro do semin center, cada entrada vai ter um ID.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Que tipo de entrada, p\*\*\*\*?  
**Lucas Biasetton:** Não entendi.  
**Gustavo Rodriguez:** Ah,  
**Lucas Biasetton:** Entendi.  
**Gustavo Rodriguez:** é que lá tem vários documentos pro mesmo caso, né? a gente fez um filtro de decisões, eu diria pegar as decisões filtradas como decisões,  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** os documentos filtrados como decisões, o maior conjunto disso que a gente tiver e dar uma ID para cada.  
**Lucas Biasetton:** Não é,  
**Gustavo Rodriguez:** É só  
**Lucas Biasetton:** é que eu não daria um ID nosso.  
**Gustavo Rodriguez:** isso.  
**Lucas Biasetton:** Eu usaria o ID que os caras já têm. Eles já tem o ID.  
**Gustavo Rodriguez:** Ah, eles têm,  
   
 

### 00:37:11

   
**Lucas Biasetton:** Tem.  
**Gustavo Rodriguez:** mas esse ID é documento,  
**Lucas Biasetton:** Não, não,  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** não tem, tem de casa também.  
**Gustavo Rodriguez:** A gente passou por esse problema.  
**Lucas Biasetton:** Tem tem o case ID e tem o document ID.  
**Gustavo Rodriguez:** Tem de casa.  
**Lucas Biasetton:** Tem tem as duas  
**Gustavo Rodriguez:** Ah, então ótimo. Já fizeram pra gente.  
**Lucas Biasetton:** coisas.  
**Gustavo Rodriguez:** Pulamenta dada é meio procedimental. Estiros muda para MD. Classify.  
**Lucas Biasetton:** Eu acho que era a classificação do do país, mas se quiser abrir aí que a gente olha. é que para mim faria mais sentido esse passo ser a classificação do documento, né? Esse o documento é uma decisão ou não?  
**Gustavo Rodriguez:** que passo, desculpa.  
**Lucas Biasetton:** Esse  
**Gustavo Rodriguez:** Ah, o esse esse script pera aí, tá abrindo.  
**Lucas Biasetton:** Yeah. M.  
**Gustavo Rodriguez:** Tá, entendi. É isso mesmo. Eh, deixa eu já abrir aqui, já que a gente vai ficar vendo essas coisas. Nossa,  
**Lucas Biasetton:** Você  
**Gustavo Rodriguez:** que lindeza, cara. Meu Deus. Desesperador.  
**Lucas Biasetton:** tá olhando o quê agora?  
**Gustavo Rodriguez:** Não, ele tá carregando. Queria só dentro do bagulho.  
   
 

### 00:39:05

   
**Gustavo Rodriguez:** Tá. que é para decisão ou não decisão extrair as citações. Lembro e tem uns métodos faseado aqui dentro tem um sitation pipeline.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Deixa eu ver. Hum, bagunçado isso aqui.  
**Lucas Biasetton:** tá se criticando. É  
**Gustavo Rodriguez:** Sim.  
**Lucas Biasetton:** isso.  
**Gustavo Rodriguez:** Adjustments. Que adjustments? Hum. A gente abre para ver. Quero star.  
**Lucas Biasetton:** É isso. Era pro site depois, eu acho, né?  
**Gustavo Rodriguez:** Exato.  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** Boa. Boa. Carregou. File open folder.  
**Lucas Biasetton:** M.  
**Gustavo Rodriguez:** M. Tá beleza? Aí, ah, vou deixar rodando aqui que a gente segue mais  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** só  
**Lucas Biasetton:** Isso aí é o quê?  
**Gustavo Rodriguez:** isso aqui é o cloud code no terminal. Tô pedindo para ele pegar os benchmarks de processing dois.  
**Lucas Biasetton:** Tá. Tá? Então ele vai comparar os dois para ver onde que a gente pode melhorar. É isso.  
**Gustavo Rodriguez:** Isso é uma primeira, uma primeira análise assim mais superficial por enquanto de novas métodos que vem do Aedes,  
   
 

### 00:43:10

   
**Lucas Biasetton:** Угуm.  
**Gustavo Rodriguez:** que é porque no Aedes como primeiro cheiro. E a gente pode tá carregando ainda isso aqui. Acho que eu preciso escolher. Car escolher deixar o terminal aberto fechar você.  
**Lucas Biasetton:** Deu uma travada, mas acho que  
**Gustavo Rodriguez:** Que tristeza mas eu vou fazer upgade de R essa semana eu vou eu vou comprar uma RAM nova instalar esse  
**Lucas Biasetton:** voltou.  
**Gustavo Rodriguez:** notebook. Se tudo der certo, ele vai de 8 GB para 20 ou 16\.  
**Lucas Biasetton:** c\*\*\*\*\*\*,  
**Gustavo Rodriguez:** É.  
**Lucas Biasetton:** boa, hein?  
**Gustavo Rodriguez:** E eu vou pegar um HD externo de 1 ta SSD para instalar software. Eu tô apertado, cara.  
**Lucas Biasetton:** Muita coisa,  
**Gustavo Rodriguez:** Tá difícil.  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** Muita coisa. E aqui tem 250 GB só. Tá. Vou enquanto o Cloud trabalha. Ã, que que você anotou aí? Vamos  
**Lucas Biasetton:** Cara, eu tava anotando os passos passo a passo,  
**Gustavo Rodriguez:** retomar  
**Lucas Biasetton:** tipo, eh, a gente tava no passo cinco,  
**Gustavo Rodriguez:** onde a gente parou. Qual o  
**Lucas Biasetton:** que é o mais importante,  
**Gustavo Rodriguez:** passo?  
**Lucas Biasetton:** que o passo cinco era justamente achar todas as citações e E aí, ã, classificá-las se elas fossem  
   
 

### 00:44:31 {#00:44:31}

   
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** estrangeiras.  
**Gustavo Rodriguez:** Tá. Eu lembro quando a gente fez isso mais ou menos,  
**Lucas Biasetton:** É,  
**Gustavo Rodriguez:** ó,  
**Lucas Biasetton:** esse eu acho que vai ser o mais,  
**Gustavo Rodriguez:** o mais delicado de revisar,  
**Lucas Biasetton:** é, esse é o mais importante.  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** Eh, se a gente for usar aquela lógica de build knowledge que eu falei, talvez a gente tenha que alterar um pouco como que a gente vai fazer isso, né? Porque a gente não vai estar mais procurando citação,  
**Gustavo Rodriguez:** Man  
**Lucas Biasetton:** eh, tipo, amplamente, a gente vai estar procurando citações aos casos que existem no saving. Muda o approach um pouco.  
**Gustavo Rodriguez:** Eu imagino, ah, só uma uma barreira, tipo, vamos refinar o algoritmo de, tá? Isso aqui é uma citação desses scripts, mas basta um, é um um aporte possível, basta um filtro depois dele identificar as citações, um step de filtro, pá. Se isso aqui tiver no na base do Sabim, eu guardo. Senão, lixo.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Ou coloco um label de citação ofsing.  
**Lucas Biasetton:** Sim, sim, sim, sim, sim. É, não, pera,  
   
 

### 00:46:00

   
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** deixa eu pensar. Então, você tá  
**Gustavo Rodriguez:** É porque sabe por quê?  
**Lucas Biasetton:** Hum.  
**Gustavo Rodriguez:** O o robô, seja qual for o tipo dele, o que o bagulho que tiver rodando isso, ele vai precisar, imagino eu, entender, tá? Primeiro, isso é uma citação. Primeiro passo do na na receita de bolo desse algoritmo, isso é uma citação. É uma citação para tal país ou de tal corte. Tal país ou tal corte não é a corte ou país de onde essa decisão foi exarada. E tal decisão citada não corresponde a nenhuma decisão da base de dados.  
**Lucas Biasetton:** Calma aí, calma.  
**Gustavo Rodriguez:** Essa o último passo que é o filtro que eu  
**Lucas Biasetton:** Então,  
**Gustavo Rodriguez:** falei.  
**Lucas Biasetton:** primeiro passo, achar citações de jurisprudência.  
**Gustavo Rodriguez:** Isso, isso. Identificar identificar  
**Lucas Biasetton:** Segundo  
**Gustavo Rodriguez:** citações. identificar que as citações são ah relevantes,  
**Lucas Biasetton:** passo,  
**Gustavo Rodriguez:** igual a critérios para relevância, né? Tipo, a gente quer guardar isso. Eh, a estrangeira é uma decisão.  
**Lucas Biasetton:** ó. E se a gente fizer assim?  
**Gustavo Rodriguez:** Ah, isso tem  
**Lucas Biasetton:** Se a gente fizer assim, identificar citações,  
   
 

### 00:47:34 {#00:47:34}

   
**Gustavo Rodriguez:** geral.  
**Lucas Biasetton:** achar citações, primeiro, todas. Segundo,  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** identificar se essa citação está no saving ou não.  
**Gustavo Rodriguez:** Que é  
**Lucas Biasetton:** Se não estiver, out,  
**Gustavo Rodriguez:** isso?  
**Lucas Biasetton:** se estiver, vê no próprio, na própria tabela qual é a origem. daquela daquela jures e comparar com a origem que tá produzindo aquele documento. Então, pela pela pelos próprios dados da tabela, não tem como a gente fazer isso.  
**Gustavo Rodriguez:** Kom  
**Lucas Biasetton:** Por exemplo, eu fui para eu estou analisando uma decisão do STF, encontrei a citação urgenda. Beleza, marquei. Aí essa citação está no CEM. Sim. Beleza. Próximo passo. Qual é o país de origem? Holanda. Próximo.  
**Gustavo Rodriguez:** E aí, a partir do está no saben, eu vou identificar o resto pelos metadados do Sabing.  
**Lucas Biasetton:** Isso. Exato.  
**Gustavo Rodriguez:** Tá. Você lembra quais eram os metadados que estavam cagados? Tinha alguns Isso.  
**Lucas Biasetton:** Hum.  
**Gustavo Rodriguez:** Что?  
**Lucas Biasetton:** Cara, era document que a gente viu que tava tava errado.  
   
 

### 00:48:57 {#00:48:57}

   
**Lucas Biasetton:** Eh, mas acho que eu acho que document era o pior de todos. document ear também tava tudo errado. Tudo errado não, mas tinha erros. Ã, summary tinha erros.  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** Então,  
**Lucas Biasetton:** eh.  
**Gustavo Rodriguez:** tudo que a gente viu de perto tinha algum erro. E a única coisa mais reliable era, tá, isso é um, isso é um bagulho que tem a ver com litigância climática e o o nome do documento identifica que tipo de documento tá melhor do que o datado.  
**Lucas Biasetton:** Eh, Eh  
**Gustavo Rodriguez:** Porque assim, se a gente já for rodar o, eu tô de calça, jeans, tá quente, eu vou tirar. Se a gente for rodar o gastar token processando o documento todo em algum momento, já daria para extrair, automatizar um processo que foi manual no passado e hoje tá expresso nos metadados da base de dados, que é pouco reliable.  
**Lucas Biasetton:** Não sei se eu entendi.  
**Gustavo Rodriguez:** Não sei,  
**Lucas Biasetton:** Sì.  
**Gustavo Rodriguez:** tipo, você tá falando, ah, classifica com base dos metadados. Os metadados foram escritidos manualmente. Quase todos os metadados, provavelmente não todos que a gente olhou de perto, tinham problemas de de classificação, tá?  
   
 

### 00:50:28 {#00:50:28}

   
**Gustavo Rodriguez:** Se a gente em algum momento for fazer o robô a lem na verdade mais especificamente ela lembra processar todo o conteúdo do documento. Por algum motivo, não chequei a na minha cabeça se isso ocorre agora, eu acho que vale a pena fazer ela corrigir essas classificações manuais  
**Lucas Biasetton:** Então, mas você concorda que você concorda que essa informação não vai tá no documento que  
**Gustavo Rodriguez:** ou refazer essas classições manuais.  
**Lucas Biasetton:** a gente tá analisando?  
**Gustavo Rodriguez:** informação, por exemplo, que são vários  
**Lucas Biasetton:** STF citou urgenda.  
**Gustavo Rodriguez:** metadados.  
**Lucas Biasetton:** A gente não consegue saber com base no documento do STF que Urgenda é uma decisão holandesa. Então não adianta nada, gente.  
**Gustavo Rodriguez:** Sim, mas isso tá tá referenciado por uma rede de conexões dos desses blocos de informação, tipo, que tão registradas nos metadados da nossa base de dados, que é mais enriquecida do que os os dados da base de dados do Sabin.  
**Lucas Biasetton:** É que tipo, você tá propondo basicamente a gente corrigir a base dos caros.  
**Gustavo Rodriguez:** Só porque nos interessa. Primeiro esse trabalho pontual de gerar o mapa para pra Joana, mapa estático. Segundo, o reprocessamento rerrun aqui nesse nessa versão 2.0.  
**Lucas Biasetton:** Então, mas eu tô tentando pensar que, cara, eu eu eu consigo pensar alguns problemas que a gente teria fazendo isso, porque não necessariamente a gente pode a gente pode ter um caso que não tem uma decisão.  
   
 

### 00:52:20

   
**Lucas Biasetton:** por não ter uma decisão, a gente não vai analisar e aí a gente não vai ter informação. Tipo, eu concordo que a gente tem que desconfiar da base, mas eu acho que seria uma uma tarefa ercúlia a gente corrigir a base com as informações que a gente precisa. Ou você acha que não? Ou você acha que é razoável?  
**Gustavo Rodriguez:** Não, quem vai ser o Hércules vai ser o robô.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Falei no começo, tendo budget que dá para  
**Lucas Biasetton:** Então, mas quanto, né?  
**Gustavo Rodriguez:** estimar e a gente decide porque os tokens são previsíveis e o preço por token é  
**Lucas Biasetton:** Não é? Eu acho uma excelente ideia.  
**Gustavo Rodriguez:** sabido.  
**Lucas Biasetton:** Eu tenho só medo da gente se perder nisso,  
**Gustavo Rodriguez:** Se perder,  
**Lucas Biasetton:** tipo,  
**Gustavo Rodriguez:** como assim?  
**Lucas Biasetton:** a gente gastar mais energia do que precisa para corrigir a base inteira dos caras.  
**Gustavo Rodriguez:** Então, minha ideia é fazer isso em duas fases, só o que nos interessa para produzir o entregável paraa Joana até  
**Lucas Biasetton:** Eu eu  
**Gustavo Rodriguez:** segunda. Só que ah,  
**Lucas Biasetton:** acho que não ia falar que eu acho que ela acharia do c\*\*\*\*\*\*  
**Gustavo Rodriguez:** tipo, depende.  
   
 

### 00:53:35

   
**Gustavo Rodriguez:** Fala,  
**Lucas Biasetton:** se a gente corrigisse a  
**Gustavo Rodriguez:** cara.  
**Lucas Biasetton:** base.  
**Gustavo Rodriguez:** A questão é budget. Se se det, se se tiver budget para fazer isso rodar, tem tempo até segunda para fazer isso acontecer, porque é refinal que a gente já tem,  
**Lucas Biasetton:** Então, mas e  
**Gustavo Rodriguez:** não é?  
**Lucas Biasetton:** e  
**Gustavo Rodriguez:** Gout do zero, num branch assim, a gente não perderia nada que já foi feito.  
**Lucas Biasetton:** então,  
**Gustavo Rodriguez:** Eu faria um branch para ver  
**Lucas Biasetton:** mas a gente quer escolher, por exemplo, a gente quer escolher informações que são relevantes para  
**Gustavo Rodriguez:** 2.0.  
**Lucas Biasetton:** nós. E aí, quando a gente for corrigir a base inteira de novo, a gente vai precisar rodar tudo de novo. Oh.  
**Gustavo Rodriguez:** Não, não, não. Acho que não. Deixa eu pensar. Eh, eu consigo responder isso melhor. Vamos ver quais seriam essas informações que a gente precisa sólidas para produzir o interag.  
**Lucas Biasetton:** Vamos. Vou abrir a tabela aqui.  
**Gustavo Rodriguez:** Tipo dependências assim.  
**Lucas Biasetton:** Deixa eu abrir aqui. Eu vou  
**Gustavo Rodriguez:** Descreve de novo o que é o que é o entregável da Joana, por favor.  
   
 

### 00:54:43 {#00:54:43}

   
**Lucas Biasetton:** vou eu vou te  
**Gustavo Rodriguez:** E a gente vai tomando nota do que ele depende,  
**Lucas Biasetton:** mostrar uma entregável da Joana primeiro.  
**Gustavo Rodriguez:** tipo de trás para  
**Lucas Biasetton:** Deixa eu abrir meu e-mail.  
**Gustavo Rodriguez:** frente.  
**Lucas Biasetton:** Nossa, meu computador parece que tá p\*\*\* que pariu, velho. Calma,  
**Gustavo Rodriguez:** Tô mandando Bitcoin para você acontecer você nem vê.  
**Lucas Biasetton:** calma aí. Tá, vamos lá. Você tá vendo minha tela? Hi Lucas love.  
**Gustavo Rodriguez:** Yes.  
**Lucas Biasetton:** Thanks again what we need. p\*\*\*\*. High resolution static versions of the map for the top five jurisdictions that side foreign case law showing both where they and where they are sided. Anesthetic version of the map the US is regularly sedes. Você tá me ouvindo? Por que que estava na outra?  
**Gustavo Rodriguez:** Sim.  
**Lucas Biasetton:** but almost never anyone else paragraphs including a very short text descriptions of the maps starting with the country with the highest number of foreign citations b short reflection on the fact that although the us is the country with the highest number of cases in some ways it does stand apart from the global phenomenon of climate litigations perhaps we can find a citation on the fact this with the us legal tradition treatment of international law and a short explanation that the figures were generating using LLM trained on saving center data and linked to the dashboard where people can look at other jurisdictions as well.  
   
 

### 00:56:36 {#00:56:36}

   
**Lucas Biasetton:** Ideally we have this by the of March so I can provide any edits and then incorporate in the draft report.  
**Gustavo Rodriguez:** Hum. p\*\*\*\*, ela vai lincar o bagulho no report.  
**Lucas Biasetton:** É, e assim,  
**Gustavo Rodriguez:** Que legal.  
**Lucas Biasetton:** isso eu já assumi a gente não vai entregar dia 9 o link to the dashboard, tá? Isso aí eu já assumi na minha cabeça que não é um entregável de agora porque não  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** dá.  
**Gustavo Rodriguez:** Vamos focar em A e  
**Lucas Biasetton:** É, vamos resolver. Na real,  
**Gustavo Rodriguez:** B.  
**Lucas Biasetton:** a gente só tem que focar aqui, porque isso aqui eu já escrevi,  
**Gustavo Rodriguez:** Ah, sim. Mas oh,  
**Lucas Biasetton:** tipo,  
**Gustavo Rodriguez:** tá claro.  
**Lucas Biasetton:** exato.  
**Gustavo Rodriguez:** Não, entendi. É  
**Lucas Biasetton:** A gente só precisa dos dados porque o texto é 5 minutos.  
**Gustavo Rodriguez:** isso.  
**Lucas Biasetton:** A questão são os dados e aí é basicamente isso que elas querem.  
**Gustavo Rodriguez:** Deixa eu  
**Lucas Biasetton:** Opa.  
**Gustavo Rodriguez:** ol.  
**Lucas Biasetton:** É porque que que eu pensei? Se eu se eu fosse preguiçoso, eu só usaria o que a gente já tem e f\*\*\*-se.  
   
 

### 00:57:46 {#00:57:46}

   
**Lucas Biasetton:** Mas como é um uma publicação muito importante, eu tenho medo de pegar mal pra gente depois, entendeu? Se a gente tiver tanta inconsistência. Por isso que eu queria,  
**Gustavo Rodriguez:** Claro,  
**Lucas Biasetton:** por isso que eu falei,  
**Gustavo Rodriguez:** concordo.  
**Lucas Biasetton:** cara, eu não sei se a gente tá pegando todas as citações,  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** eu não sei se e tem umas que estão classificadas errada, talvez seja melhor a gente refazer a metodologia. Por isso que eu pensei, entendeu?  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** Deixa eu voltar para você  
**Gustavo Rodriguez:** Cara,  
**Lucas Biasetton:** aqui.  
**Gustavo Rodriguez:** tô tentando pensar agora que que dá para excluir de consideração para chegar nisso, porque para chegar num número reliable de top cinco, a gente tem que confissando os números em geral.  
**Lucas Biasetton:** É, não, a gente vai ter que fazer tudo. M.  
**Gustavo Rodriguez:** É, então agora o que isso significa fazer tudo, tendo em vista o objetivo de refinar tudo que a gente já fez na medida do possível,  
**Lucas Biasetton:** Cara, para mim,  
**Gustavo Rodriguez:** é um é um é um sprint assim de polimento de uma semana e aí focar,  
**Lucas Biasetton:** sim.  
**Gustavo Rodriguez:** imagino aí focar nos últimos dias em definir a extensão da qualidade dessa análise, ou seja, margem de erro, por exemplo,  
   
 

### 00:58:55 {#00:58:55}

   
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** para porque ainda vai ter chance de não ser perfeito e ainda que seja vai est  
**Lucas Biasetton:** Sim. Não é perfeito. Não acho que vai ser  
**Gustavo Rodriguez:** limit dentro do escopo do do que tá no Sabin.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Isso só isso já é um recorte.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Eh, esse disclaimer, por exemplo, de processamento paralelo é muito importante. Eu acho que ele tem que vir condicionado de alguma estimativa de imagem de erro, sabe?  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** alguma gordura pr não parecer que a gente tá steer num bagulho absurdo e  
**Lucas Biasetton:** Sim,  
**Gustavo Rodriguez:** não tem dado para suportar isso não.  
**Lucas Biasetton:** sim, sim, sim. É, eu eu fico eu eu ia falar que eu fico um pouco mais confortável porque,  
**Gustavo Rodriguez:** terem um bagulho. Fala  
**Lucas Biasetton:** por exemplo, o que eu ajudei elas a montar no artigo delas, a gente não usou os dados, eu eu ficaria incomodado se a gente usasse os dados como valor, tipo, Brasil cita 353 vezes e tipo fazer uma uma tabela gigante, porque aí eu acho que é é cagada. Agora um top five, eu acho que sabe, eu não tenho tanto receio em colocar e tipo, a gente tem essas capturadas, se a gente perdeu alguma coisa, a gente pode tentar entender o porquê.  
   
 

### 01:00:03 {#01:00:03}

   
**Lucas Biasetton:** Às vezes não tava no saving ou às vezes foi algum erro de leitura, mas f\*\*\*-se também isso eu tô mais tranquilo. Eu só queria refinar o que a gente fez. Eh,  
**Gustavo Rodriguez:** É,  
**Lucas Biasetton:** a questão é how deep, né? A gente vai fazer isso.  
**Gustavo Rodriguez:** é. Ah, que você notou de tescas, então volta lá para eu ver agora.  
**Lucas Biasetton:** Ó, aqui step zero, database inicialization, adicionar col de case idar scripts posteriores a manterem o ID. Step one, versão atualizada da tabela, downloads dos PDFs, Step two, novos scripts de markdown file. E aí eu fui seguindo os steps que a gente tinha usado antes, mas nem sei se eles fazem sentido ainda.  
**Gustavo Rodriguez:** Ага.  
**Lucas Biasetton:** A gente parou aqui. M.  
**Gustavo Rodriguez:** E aí acho que o terceiro é é o fim do processo do P de correlacionar os dados.  
**Lucas Biasetton:** O  
**Gustavo Rodriguez:** É tipo estando vírgula, permitiu o correlacionamento de dados e a inclusão na database final.  
**Lucas Biasetton:** é se for estrangeiro, né?  
**Gustavo Rodriguez:** É.  
**Lucas Biasetton:** E o step se é basicamente exporto,  
**Gustavo Rodriguez:** Ai, é preparar mapa de  
**Lucas Biasetton:** cara.  
   
 

### 01:02:01 {#01:02:01}

   
**Lucas Biasetton:** para mim. V, vê se você concorda comigo,  
**Gustavo Rodriguez:** fato.  
**Lucas Biasetton:** mas eu acho que o book tá aqui no step  
**Gustavo Rodriguez:** Desculpa. O que?  
**Lucas Biasetton:** 5\.  
**Gustavo Rodriguez:** Ah, sim,  
**Lucas Biasetton:** Tipo, o resto, meu peinuts,  
**Gustavo Rodriguez:** sim,  
**Lucas Biasetton:** eu acho. Ih, você tá me ouvindo?  
**Gustavo Rodriguez:** certo.  
**Lucas Biasetton:** Você travou.  
**Gustavo Rodriguez:** Tô te ouvindo.  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** Eh, a minha única dúvida e se a gente continua com o três e o quatro, que é counter classification e decision classification, e se a gente faz um knowledge base,  
**Gustavo Rodriguez:** Hum.  
**Lucas Biasetton:** igual eu tinha te falado,  
**Gustavo Rodriguez:** Sim. Só que fazer um desse implica rodar tudo de novo,  
**Lucas Biasetton:** Não é, é,  
**Gustavo Rodriguez:** o que tudo bem também.  
**Lucas Biasetton:** eu não tenho problema rodar tudo de novo. A questão é tipo a gente tem um resultado, entendeu?  
**Gustavo Rodriguez:** Se dá tem dá sim com o Pô, a Ed está avançado para c\*\*\*\*\*\*. Dá para focar nisso até ter uma versão reliable.  
**Lucas Biasetton:** Mas aí você acha que a gente mantém os Você Você acha que  
   
 

### 01:03:23 {#01:03:23}

   
**Gustavo Rodriguez:** Eu adiantei o outro bagulho que eu mencionei também, então tô com tempo, dá para fazer.  
**Lucas Biasetton:** a gente mantém o três e quatro?  
**Gustavo Rodriguez:** O três, uma vez que a gente tenha confiança no  
**Lucas Biasetton:** Eu  
**Gustavo Rodriguez:** saben, na classificação do saben, dá para tirar de lá para  
**Lucas Biasetton:** acho que a gente só deixou aqui para ter o, é, para incluir a informação,  
**Gustavo Rodriguez:** anotar o que foi feito.  
**Lucas Biasetton:** eu acho. Talvez. Será? Não foi isso.  
**Gustavo Rodriguez:** É, dá para jogar o três para baixo depois do de filtro do  
**Lucas Biasetton:** Calma. Então, qual seria o próximo aqui?  
**Gustavo Rodriguez:** saving.  
**Lucas Biasetton:** O novo três.  
**Gustavo Rodriguez:** Faz, tira os números de todos pra gente planejar, depois não numera.  
**Lucas Biasetton:** Será que aqui a gente faz para classificar ajustes, tipo realmente ver se isso é uma decisão, realmente ver se isso é da Holanda e extrair citações, a gente mandaria ele analisar o documento duas vezes.  
**Gustavo Rodriguez:** Não dá para ter um output que considera as duas perguntas. O que mais consome é o o quanto a gente manda de dados para ele ler. O que ele vai produzir de análise a partir dessa leitura não varia tanto os tokens que a gente tem para usar, a menos que o tamanho do processamento seja muito grande, mas tipo, ele vai identificar e processar texto normal.  
   
 

### 01:05:15 {#01:05:15}

   
**Lucas Biasetton:** Mhm.  
**Gustavo Rodriguez:** A questão é estruturar a pergunta, inclui ela no pront de forma decente para permite a resposta  
**Lucas Biasetton:** Ahí  
**Gustavo Rodriguez:** vir dentro da janela de contexto daquela troca daquele daquela mensagem tanto para lá para LM quanto da LM para cá.  
**Lucas Biasetton:** Cara, eu tô pensando em tomar a decisão da gente não reclassificar as coisas do SA.  
**Gustavo Rodriguez:** É um cover, né?  
**Lucas Biasetton:** É, mas é mais por medo de de tempo.  
**Gustavo Rodriguez:** também  
**Lucas Biasetton:** Eu não sei. Eu tipo, eu fico com medo de dar  
**Gustavo Rodriguez:** dá para dá para ter isso em mente e só reclassificar o que for exatamente necessário para produzir o bagulho final e a gente vê o que  
**Lucas Biasetton:** muito,  
**Gustavo Rodriguez:** parece como exatamente necessário.  
**Lucas Biasetton:** tá? Aqui seria basicamente docum  
**Gustavo Rodriguez:** Ah, classificação do classificação do tipo,  
**Lucas Biasetton:** Men  
**Gustavo Rodriguez:** identificação dos países, citandos e citados a partir da dedicação da corte do próprio país na citação.  
**Lucas Biasetton:** é is Aí o step  
**Gustavo Rodriguez:** Pior que  
**Lucas Biasetton:** four seria já extrair  
**Gustavo Rodriguez:** é.  
**Lucas Biasetton:** citações, não é isso?  
**Gustavo Rodriguez:** Hum. Hum. Não, não. Antes de É, pera, anota aí também em depois de Markdown o dentro de reclassificar, sabinho ou no step anterior, tipo a coisa do knowledge que você mencionou, tipo sumarization, tá ligado?  
   
 

### 01:07:26 {#01:07:26}

   
**Gustavo Rodriguez:** E aí? marca que tipo isso quer dizer criar sumários e índices.  
**Lucas Biasetton:** Uhum. E aí, step four, extrair citação. Então, sabe o que eu acho que vale a gente fazer no stepfor? p\*\*\*, é que isso ajudaria na validação,  
**Gustavo Rodriguez:** M.  
**Lucas Biasetton:** mas eu não sei se é insano. Ele extraiu os nípets de toda a situação que ele encontrar. Sitação de juros. Será que é muito louco isso? Talvez consuma demais,  
**Gustavo Rodriguez:** Dá para economizar um É,  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** dá para economizar fazendo ele apontar. Não, aí fica arriscado. Ai, cara, acho que tem algum método de, tipo, imagina o computador conta os caracteres até chegar no começo da citação, marca, conta os caracteres até chegar no fim da citação, marca. a gente tem essa referência para facilitar a conferência depois, sem fazer o modelo ler e escrever as citações. Ele vai ter identificar citações já em algum momento ali atrás e extrair a partir disso. Tipo, o que eu quero é isso é um exemplo de método para bookmark o bagulho. E aí a tarefa é achar o método mais eficiente com ai, né?  
   
 

### 01:09:05 {#01:09:05}

   
**Gustavo Rodriguez:** ver o que dá para fazer para ter esse essa âncora aí paraa conferência  
**Lucas Biasetton:** Então,  
**Gustavo Rodriguez:** depois.  
**Lucas Biasetton:** mas eu quero pros que a gente realmente vai usar. Eu gostaria de ter o snipets lá que ele chamou,  
**Gustavo Rodriguez:** Eu produzo para você depois de ter esse esse método para chegar no snipet.  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** É que eu não queria fazer a LLM processar isso como como dependência pros próximos passos ou pros outros passos. Tipo, tem uma base só dos relacionando as citações,  
**Lucas Biasetton:** Sì.  
**Gustavo Rodriguez:** os snipets delas e os documentos onde elas vêm.  
**Lucas Biasetton:** É, então a gente só tem o sniper das citações que a gente decide manter depois, tipo, ele volta e pega,  
**Gustavo Rodriguez:** É tipo isso,  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** é que daí a gente pode dar para uma agente fazer a conferência e aí sim quando precisar ele lê toda  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** a citação e faz a conferência a partir do comando. Ah, ela começa aqui, termina aqui. Ou o outro método de marcar onde tá a citação, mas direcionar o agente revisor para lá.  
**Lucas Biasetton:** para um ponto específico. E aí depois você concorda que o próximo passo seria avaliar se a situação é de um caso do saving, que primeiro extrai estação,  
   
 

### 01:10:27

   
**Gustavo Rodriguez:** Uhum. Uhum.  
**Lucas Biasetton:** depois  
**Gustavo Rodriguez:** É em nível mais tipo num em algum grau de abstração, tá bem descrito. Aí tem que traduzir isso no algoritmo.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Mas aí eu me viro com robô, eu valido com você e  
**Lucas Biasetton:** É, comparando com o knowledge base,  
**Gustavo Rodriguez:** aplico.  
**Lucas Biasetton:** que é base. Quando eu fiz, eu fiz isso.  
**Gustavo Rodriguez:** É, a a a dúvida que na minha cabeça é tipo o caminho, o método para fazer essa avaliação. Tipo, ele tem que saber, tá? Essa estação é de o caso do Sabim. Da onde viu essa estação, tá? Isso tá dado. Ah, viu desse documento, desse dessa decisão.  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** Que decisão é essa? chegou na decisão é essa e ele identificar é essa aqui que eu que eu conheço por este conteúdo. Ele verifica se esse conteúdo está aizado.  
**Lucas Biasetton:** você não acha que assim, qual prejuízo você acha que a gente teria se a gente seguisse a metodologia que eu usei na no projeto que eu fiz com elas, que era buscar os casos que eu queria, não era buscar necessariamente ente se todas as citações do documento. Então, tipo, o que ele fazia é casos relevantes são brções ano, bá.  
   
 

### 01:11:44 {#01:11:44}

   
**Lucas Biasetton:** Desses casos estão aqui. Com isso na cabeça, ele lia e procura e procurava identificar essas citações específicas. Eu fiz isso ao invés de procurar todas as citações do documento, entendeu?  
**Gustavo Rodriguez:** Entendi. Legal. E você pôs um dicionarzinho, um guia de referência para ele saber as diferentes formas em que aquele bagulho poderia aparecer como numa situação.  
**Lucas Biasetton:** Então, eu ia fazer isso,  
**Gustavo Rodriguez:** Vamos.  
**Lucas Biasetton:** mas aí o Gemini falou que isso é um que era um método antiquado de de análise de dados e que o modelo já era capaz de entender isso sozinho, porque, tipo, quando eu comecei a procurar isso, eu comecei, tipo, a entrar um o Cloud começou a falar daquele Você tá me  
**Gustavo Rodriguez:** que eu eu me coisei para o nariz,  
**Lucas Biasetton:** ouvindo?  
**Gustavo Rodriguez:** eu já apareço acho que não jeito compartilhar esse momento visual com você,  
**Lucas Biasetton:** Tá. Não,  
**Gustavo Rodriguez:** essa imagem  
**Lucas Biasetton:** tranquilo. O Cloud começou a falar tipo de usar eh aquele legal bird ou tipo modelos treinados em documentos jurídicos e tal. E aí eu comecei a me aprofundar nessa brisa. E aí o Gemini falou: "Cara, não precisa. Tipo,  
   
 

### 01:12:55 {#01:12:55}

   
**Lucas Biasetton:** o modelo é avançado suficiente para conseguir entender o que é uma situação judicial". E aí eu falei: "p\*\*\*, então nem preciso fazer lista de de referência".  
**Gustavo Rodriguez:** Tá, tá. Você acredita?  
**Lucas Biasetton:** Cara,  
**Gustavo Rodriguez:** Você tá confiante nessa informação?  
**Lucas Biasetton:** não, o trabalho que eu fiz com elas, ele cravou,  
**Gustavo Rodriguez:** Boa.  
**Lucas Biasetton:** mas era uma amostragem bem menor,  
**Gustavo Rodriguez:** Então, beleza.  
**Lucas Biasetton:** né? Não,  
**Gustavo Rodriguez:** E você rodou um por um ou você mandou de uma vez?  
**Lucas Biasetton:** tudo de uma vez  
**Gustavo Rodriguez:** Tá. Então, tudo cobe dentro do contexto de uma troca.  
**Lucas Biasetton:** cobe. Só que o problema é que eram tipo 25 casos de referência aqui. Vão ser tipo uns 2.000,  
**Gustavo Rodriguez:** É,  
**Lucas Biasetton:** eu  
**Gustavo Rodriguez:** não cabe não,  
**Lucas Biasetton:** acho.  
**Gustavo Rodriguez:** mas a gente quebra em em betes assim e só põe dentro de cada bet o que o modelo conseguir suportar. Eu tô fazendo  
**Lucas Biasetton:** Então, mas a a o knowledge base seria gigante,  
**Gustavo Rodriguez:** sques,  
**Lucas Biasetton:** né? Eu fiz  
**Gustavo Rodriguez:** mas tá indexado,  
**Lucas Biasetton:** aqui,  
   
 

### 01:13:55 {#01:13:55}

   
**Gustavo Rodriguez:** então ele só vai buscar o que interessa,  
**Lucas Biasetton:** mas depende de como for a citação,  
**Gustavo Rodriguez:** entende? Tipo,  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** eu preciso judar o pedaço.  
**Lucas Biasetton:** Tipo,  
**Gustavo Rodriguez:** Como  
**Lucas Biasetton:** ele não vai citar exatamente o nome que a gente quer que ele  
**Gustavo Rodriguez:** assim?  
**Lucas Biasetton:** cite. Tipo,  
**Gustavo Rodriguez:** Como assim?  
**Lucas Biasetton:** me me explica o que você falou para eu ver se  
**Gustavo Rodriguez:** É, então, eh, não sei também o como ficou.  
**Lucas Biasetton:** се  
**Gustavo Rodriguez:** Deixa eu voltar voltar mais, ó. se ligar, tem algumas entidades ou ou ou categorias de coisas, que a decisão,  
**Lucas Biasetton:** Угуm.  
**Gustavo Rodriguez:** o caso e a citação são os nossos pontos focais, além de talvez país, país associado, beleza? Tem uma estrutura que conecta essas entidades, tipo um caso tem algumas decisões, cada decisão tem algumas estações, tudo isso tem um rótulo de país colado nele. A partir disso, a gente consegue desenhar como vai vão ser os sumários e os índices para eh o algoritmo achar o que ele precisa eficientemente e mandar tudo que a Len precisa para responder o que a gente precisa que ela precisa, que ela precisa para responder essas porras tudo. em cada fase em que ela vai responder alguma coisa.  
   
 

### 01:15:36

   
**Lucas Biasetton:** M.  
**Gustavo Rodriguez:** Então, tipo, dando um exemplo concreto desse desse jeito de fazer, eu tenho os documentos base, o raw material do do sain, são documentos. O nosso recorte são decisões. Se eu catalogar trechos dessas desses dessas decisões, além das próprias decisões,  
**Lucas Biasetton:** Ja.  
**Gustavo Rodriguez:** eu enriqueço o knowledge do da base de dados com o que tá ali dentro. Beleza? Próxima coisa é, eu documento esses labels todos e registro todos eles na base de dados em cada documento, no começo dele com metadado ali, um ID pelo menos a base de dados o resto dos metadados. E na hora de responder as perguntas que a gente tá interessado, a gente pode pegar um shortcut, por exemplo, de vai download, vira markd, cria o sumário já com foco nessas entidades e labels que a gente precisa. Cria o índice dos sumários. deixa salvo. É uma missão place. E aí a gente conta as entidades citações dentro de cada decisão. Com isso, identifica o stoping countries. Anota isso. Depois aplica o caminho que a gente aplicou na no primeiro run. para identificar quantas vezes o país citado depois de anotar o primeiro. E a gente faz as pontos e cria o mapa rodar a base inteira,  
   
 

### 01:17:44 {#01:17:44}

   
**Lucas Biasetton:** Meu Deus, entendi nada,  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** velho.  
**Gustavo Rodriguez:** Não, que loucura.  
**Lucas Biasetton:** Objetivamente.  
**Gustavo Rodriguez:** Ó, deixa eu,  
**Lucas Biasetton:** Objetivamente.  
**Gustavo Rodriguez:** deixa eu download.  
**Lucas Biasetton:** Aham. Aham.  
**Gustavo Rodriguez:** Vira markd l markd.  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** Ela me identifica país. Citações, conta citações.  
**Lucas Biasetton:** o número de citações.  
**Gustavo Rodriguez:** É, foi relevante. Acho que talvez seja, mas não, mas principalmente associa citações ao país que foi citado e guarda essas informações todas até aqui.  
**Lucas Biasetton:** Hum. E aí?  
**Gustavo Rodriguez:** Pera aí. Beleza, as perguntas são top países que  
**Lucas Biasetton:** Não, mas calma.  
**Gustavo Rodriguez:** citam,  
**Lucas Biasetton:** Mas aí,  
**Gustavo Rodriguez:** não é? Foco, o foco do da análise, tipo, eu preciso saber quem são os os top cinco  
**Lucas Biasetton:** mas você quer fazer isso sem a gente ver os  
**Gustavo Rodriguez:** países.  
**Lucas Biasetton:** dados?  
**Gustavo Rodriguez:** Não, eu tô eu tô eu tô eu tô eu tô descrevendo onde eu tô mirando pra gente anotar como eu chego lá.  
**Lucas Biasetton:** Hum hum.  
**Gustavo Rodriguez:** em vista onde estamos mirando. Eu preciso saber o número de citações feitas por cada país.  
   
 

### 01:19:28 {#01:19:28}

   
**Gustavo Rodriguez:** E o número grosso assim e o número de casos de cada país que contém estações estrangeiras. Eu  
**Lucas Biasetton:** M.  
**Gustavo Rodriguez:** preciso saber a quem essas citações se referem, a que países.  
**Lucas Biasetton:** Mano, mas se a gente não tá pulando muito, indo já para essa  
**Gustavo Rodriguez:** Calma. É, é, a gente tá cercando o problema para lados diferentes. No fim vai sair de tudo isso um caminho mais  
**Lucas Biasetton:** tá.  
**Gustavo Rodriguez:** claro. Asitações mapeadas. O próximo nível, próximo tópico aí dentro de resultado final é tipo quantas vezes cada país foi citado. M. E a partir disso  
**Lucas Biasetton:** Угуm.  
**Gustavo Rodriguez:** isso, tá? E aí a partir disso desenhar o mapa que o robô faz em no time. Pera aí. Você acha esquisito cada citação ser uma entidade com ID e  
**Lucas Biasetton:** Não,  
**Gustavo Rodriguez:** tal?  
**Lucas Biasetton:** o nosso já era assim. Tinha um um ID  
**Gustavo Rodriguez:** Já tinha isso na  
**Lucas Biasetton:** gerado.  
**Gustavo Rodriguez:** tabela de  
**Lucas Biasetton:** É tipo aqui, ó.  
**Gustavo Rodriguez:** citações  
**Lucas Biasetton:** Não era isso?  
**Gustavo Rodriguez:** que aí  
**Lucas Biasetton:** Esse extraction a gente que criou,  
**Gustavo Rodriguez:** não  
**Lucas Biasetton:** não é?  
   
 

### 01:21:39

   
**Lucas Biasetton:** do saving.  
**Gustavo Rodriguez:** acho que isso Eh, ah, é, cada linha dessa é umação, né?  
**Lucas Biasetton:** Isso  
**Gustavo Rodriguez:** Ah, então acho que esse ali talvez já sirva.  
**Lucas Biasetton:** você não acha que Bom, vou esperar se acabar. Nossa, raciocínio.  
**Gustavo Rodriguez:** Tá? E aí acho que o próximo passo para desenhar isso é um tópico entre LM L mark down e resultado final. Isso, tá? Chamar de algoritmo. E aí a gente já falou dele no resto dessa página. Pode aumentar a página, a janela, ó. Maximizar isso. Vamos ver.  
**Lucas Biasetton:** Isso aqui.  
**Gustavo Rodriguez:** Não, isso é também, mas não só. Uhum.  
**Lucas Biasetton:** Acabou.  
**Gustavo Rodriguez:** É isso. É o é um é um merge do que a gente fez com que tá descrito de steps no resto do documento. E isso que vai ser o polimento da do pipeline orientado a esse mapa pra Joana.  
**Lucas Biasetton:** Então eu colo isso  
**Gustavo Rodriguez:** lá dentro da ponte,  
**Lucas Biasetton:** aqui  
**Gustavo Rodriguez:** como ponte pode cola esses steps. Sim,  
**Lucas Biasetton:** todos.  
**Gustavo Rodriguez:** os que estão três até o de baixo. Não é os caras sabem que a gente dropou,  
**Lucas Biasetton:** Então é esse  
   
 

### 01:23:42

   
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** aqui.  
**Gustavo Rodriguez:** Isso é o primeiro do do algoritmo e os outros também lá dentro.  
**Lucas Biasetton:** Esse aqui é uma repetição, eu acho.  
**Gustavo Rodriguez:** É, acho que sim, mas coloca como subnível do que a gente acabou de pôr do um do primeiro  
**Lucas Biasetton:** Não.  
**Gustavo Rodriguez:** ateira.  
**Lucas Biasetton:** Assim.  
**Gustavo Rodriguez:** Acho que pode ser os outros stats. Extrai, avalia de potência sabinho ou não tem que tá tá redundante algumas coisas. A gente termina de ti as mudanças depois que mais marcado como step lá  
**Lucas Biasetton:** Eh,  
**Gustavo Rodriguez:** embaixo.  
**Lucas Biasetton:** hã, esporte counter classification, mas que já estaria no outro. Isso aqui já tá tudo isso aqui já tá.  
**Gustavo Rodriguez:** Então apaga. Pode apagar.  
**Lucas Biasetton:** Esse aqui a gente colocou agora. E esse aqui já tá também. Posso tirar?  
**Gustavo Rodriguez:** Sim. Agora pulindo que tá aí. é permitir correlacionamento de dados no terceiro. Isso é, acho que tá mais especificado do que já esteve. Faz sentido do que você tá vendo?  
**Lucas Biasetton:** Cara,  
**Gustavo Rodriguez:** Deu para tipo,  
**Lucas Biasetton:** pera aí, deixa eu ver.  
**Gustavo Rodriguez:** tá, tá. Grosso modo ainda,  
   
 

### 01:26:02

   
**Lucas Biasetton:** Então,  
**Gustavo Rodriguez:** mas é a partir disso que o bagulho  
**Lucas Biasetton:** mas para mim, ué, por que você sumiu?  
**Gustavo Rodriguez:** ã aqui. Tô me vendo.  
**Lucas Biasetton:** Ah, não tô te vendo mais, mas enfim. Eh, não sei se faz sentido, porque é um, tipo, o que que é esse LLM markdown? Lê o markd. Isso.  
**Gustavo Rodriguez:** Lê Mark down  
**Lucas Biasetton:** Que que ele vai fazer aqui?  
**Gustavo Rodriguez:** process.  
**Lucas Biasetton:** Alô.  
**Gustavo Rodriguez:** Tô aqui.  
**Lucas Biasetton:** Ah.  
**Gustavo Rodriguez:** Pera aí. É, não identifica país, estações, contesta estações, estaçõ estado iguais, tá escrito lá embaixo, ficou redundante se ela lembla Mark é uma é uma base para guardar informação quando a gente precisar que a LLM leia o documento, o que tá no subtópico, identificar estações, contar, associar as citações aos países. a gente reproduziu lá embaixo,  
**Lucas Biasetton:** อือ Hum.  
**Gustavo Rodriguez:** né? Então pode apagar.  
**Lucas Biasetton:** Tudo  
**Gustavo Rodriguez:** É, esse TP dois dá para chamar de, como eu chamo isso geralmente, tipo, ah, sei lá, dependência zero, passo zero, passo 0.1, Um que tem um zero ali em cima ou deixa só como step 2 1 2 3 1 0 1 2oritmo virou três e é isso.  
   
 

### 01:28:02 {#01:28:02}

   
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** Confere de  
**Lucas Biasetton:** É assim,  
**Gustavo Rodriguez:** novo.  
**Lucas Biasetton:** não sei, não sei se tá fazendo sentido não,  
**Gustavo Rodriguez:** como você a abraçaria ou descreveria o processo de forma  
**Lucas Biasetton:** porque o medo que eu tô é que o step 3 agora é tipo,  
**Gustavo Rodriguez:** diferente?  
**Lucas Biasetton:** tá ligado?  
**Gustavo Rodriguez:** É sim, mas ele tem substeps. É só que ele é o trabalho de fato, né? Vai estrações, avaliar e produzir o  
**Lucas Biasetton:** Sim,  
**Gustavo Rodriguez:** mapa.  
**Lucas Biasetton:** mas ele e tipo são uma série de passos dentro dele, né? A gente vai mandar ele fazer tudo de uma vez.  
**Gustavo Rodriguez:** Não, não. O que você chamou de step 3, eu diria que é uma fase hoje no seria uma fase. Cada fase tem tesques.  
**Lucas Biasetton:** Hum. Então vamos lá. Me me ajuda a entender aqui. Tesque um.  
**Gustavo Rodriguez:** tá dentro disso aí, tá aí o que tá ali embaixo. Só chamar de tesque, o que tá dentro de o que é um quadrado preto. Tesque um seria tipo depois de ter o que tá já tá lá em cima.  
**Lucas Biasetton:** É extrair estação.  
**Gustavo Rodriguez:** Ah, e esses quadradinhos são são constrições dessa tesque,  
   
 

### 01:29:41

   
**Lucas Biasetton:** Então,  
**Gustavo Rodriguez:** tipo, que ela tem que entregar,  
**Lucas Biasetton:** a primeira coisa que ele vai fazer é identificar todas as citações do  
**Gustavo Rodriguez:** tá ligado?  
**Lucas Biasetton:** documento,  
**Gustavo Rodriguez:** É.  
**Lucas Biasetton:** tá? A segunda coisa que ele vai fazer é isso aqui.  
**Gustavo Rodriguez:** Pode ser. E primeiro joga lá em cima o um.  
**Lucas Biasetton:** Como assim? Joga lá em cima. Ah, tá. É isso aí já tá  
**Gustavo Rodriguez:** O isso é ou só apaga que já tá,  
**Lucas Biasetton:** ali.  
**Gustavo Rodriguez:** já tá lá.  
**Lucas Biasetton:** E o snipet vem para cá,  
**Gustavo Rodriguez:** É isso.  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** É.  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** lá tinha. Calma. E o esse zero é esse primeiro é uma tesque, o segundo e o terceiro são outras tesques. Tipo, ele não vai rodar grandes coisas de uma vez, não dá.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Isso aí tá num nível de abstração também. A gente tá descrevendo grosso modo as coisas na hora de fazer é tipo um monte de linha de prompt  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** para cada coisa e cada coisa é feita de vários promptos mais  
**Lucas Biasetton:** Tá. E aí o  
   
 

### 01:31:06 {#01:31:06}

   
**Gustavo Rodriguez:** todo o contexto que ele já tem.  
**Lucas Biasetton:** tesque  
**Gustavo Rodriguez:** Tesque três. Hã, legal.  
**Lucas Biasetton:** faz sentido que aí ou vai ser uma ah aquelas  
**Gustavo Rodriguez:** Boa. Bem lembrado. Sim, sim.  
**Lucas Biasetton:** porras lá que a gente já tem, porque aí para fazer isso ele vai ter que comparar quem produziu o documento com quem a gente tá  
**Gustavo Rodriguez:** Sim.  
**Lucas Biasetton:** citando.  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** E aí o resultado final primeiro é uma tabela, né?  
**Gustavo Rodriguez:** É, tudo isso aí fica registrado em tabelas no fim das  
**Lucas Biasetton:** tipo gerar um Excel que a gente consiga validar,  
**Gustavo Rodriguez:** contas.  
**Lucas Biasetton:** checar e etc,  
**Gustavo Rodriguez:** Ah, tá. É isso. É  
**Lucas Biasetton:** né?  
**Gustavo Rodriguez:** ntime.  
**Lucas Biasetton:** É isso. Então,  
**Gustavo Rodriguez:** Acho que é consolida só.  
**Lucas Biasetton:** como assim?  
**Gustavo Rodriguez:** É, não, não tá repetitivo mais nada,  
**Lucas Biasetton:** Não,  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** agora acho que não.  
**Gustavo Rodriguez:** Maravilha.  
**Lucas Biasetton:** E aí,  
**Gustavo Rodriguez:** Boa.  
**Lucas Biasetton:** será que eu conseguiria, tipo, será que a gente consegue fazer a quatro mãos isso aqui ou vai ficar muito confuso?  
   
 

### 01:32:48 {#01:32:48}

   
**Gustavo Rodriguez:** Não dá para fazer. A gente marca horários todos os dias e sai junto.  
**Lucas Biasetton:** Não, tipo, eu vou fazendo alguns passos também, entendeu? Tipo, a gente se divide ou será que fica muito confuso?  
**Gustavo Rodriguez:** Hum. Não sei. Só se a gente só se a gente ver agora a natureza de cada um e ver se dá para Cara, eu não saberia dividir isso em quatro mos não. Eu acho não. Acho que em tese dá sim, mas eu não sei se eu sei que é um trabalho interativo, né? Ele ele vai tipo during on the last one  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** assim.  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** Cada coisa que você faz não fica boa de primeira, não fica pronta de primeira, tem erros, tem bugs e aí tem que ir  
**Lucas Biasetton:** Sim. É. Não, então por isso que eu tava tentando pensar se a gente conseguiria dividir,  
**Gustavo Rodriguez:** depurando.  
**Lucas Biasetton:** mas o problema é que se for dependente do passo anterior já fodeu, né?  
**Gustavo Rodriguez:** É, geralmente é esses pipelines do jeito que eu sei fazer. Claro, tem ter alguém que faria o equipes fazem coisas em equipe,  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** mas tá por enquanto fora do do que eu consigo ver por enquanto, tipo até agora.  
   
 

### 01:34:03

   
**Lucas Biasetton:** Não,  
**Gustavo Rodriguez:** Hum. Mas se você quiser ter mais controle sobre tudo  
**Lucas Biasetton:** meu preocupação não é nem controle,  
**Gustavo Rodriguez:** isso,  
**Lucas Biasetton:** é mais tipo a gente é e e dividir a carga também,  
**Gustavo Rodriguez:** acompanhar, ver o que tá acontecendo com s feito.  
**Lucas Biasetton:** tipo, por exemplo, do o 01 e 2, eu me sinto bem confortável para fazer  
**Gustavo Rodriguez:** lá. O inclusive o Ah, então manda ver.  
**Lucas Biasetton:** Só o da base que eu não fiz no último, mas eu posso olhar e e aí eu adapto. Enfim, eu posso fazer com conhecimento do Aeges também e tal. E aí eu deixo você focado no mais complexo.  
**Gustavo Rodriguez:** Boa. Então, faz, eu dou uma olhada. Se eu precisar de alguma de algum polimento, eu eu te aviso, valido com você e aplico ou não. E quando tiver essas coisas, eu começo.  
**Lucas Biasetton:** Tá. Não sei se você acha que faz sentido. Eu só tô preocupado com carga e com prazo. Se achar que não faz sentido também, f\*\*\*-se. Tipo, não é um problema para mim. É  
**Gustavo Rodriguez:** Não, porque a carga não vai,  
**Lucas Biasetton:** só  
   
 

### 01:35:27 {#01:35:27}

   
**Gustavo Rodriguez:** não é uma grande coisa assim, eu acho. Porque assim, eu vou ter, eu vou ter que revisar o que você fizer ou pelo menos entender como e o que você fez prosseguir e vai dar  
**Lucas Biasetton:** sim,  
**Gustavo Rodriguez:** um trabalho próximo de eu também fazer.  
**Lucas Biasetton:** cara. assim por mim. Então, se se você quiser fazer tudo direto,  
**Gustavo Rodriguez:** Eu prefiro para ficar mais  
**Lucas Biasetton:** funciona também. Eh,  
**Gustavo Rodriguez:** confiante de Não,  
**Lucas Biasetton:** tá.  
**Gustavo Rodriguez:** não que eu não confie,  
**Lucas Biasetton:** Não, sim,  
**Gustavo Rodriguez:** eu achei que você não vai fazer,  
**Lucas Biasetton:** sim, eu entendi.  
**Gustavo Rodriguez:** mas é  
**Lucas Biasetton:** Eu entendi. Eh, não, tá bom. E aí, é, eu vou fechar o texto. É que o problema é que uma parte do texto eu vou depender dos resultados para ter a resposta. Eh,  
**Gustavo Rodriguez:** Uhum.  
**Lucas Biasetton:** mas, né? Não sei se eu consigo fazer.  
**Gustavo Rodriguez:** Não, e vai ter vários touch points,  
**Lucas Biasetton:** Sim, sim, sim,  
**Gustavo Rodriguez:** assim,  
**Lucas Biasetton:** sim. Isso  
**Gustavo Rodriguez:** você vai ficar bem próximo,  
**Lucas Biasetton:** sim.  
   
 

### 01:36:21 {#01:36:21}

   
**Gustavo Rodriguez:** eh, para eu te fazer acompanhar, entender e validar as coisas e vou pedir de ajuda em vários momentos, para várias decisões.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** A carga você vai ter, fica  
**Lucas Biasetton:** Tá.  
**Gustavo Rodriguez:** tranquilo.  
**Lucas Biasetton:** Hoje é terça.  
**Gustavo Rodriguez:** né?  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** É o  
**Lucas Biasetton:** Nove é o alvo.  
**Gustavo Rodriguez:** alvo.  
**Lucas Biasetton:** Como é que está de agenda em geral aí? Mais ou menos assim,  
**Gustavo Rodriguez:** A gente pode ter um touch point de x horas, x tempo todo dia em horários sortidos.  
**Lucas Biasetton:** tá?  
**Gustavo Rodriguez:** Ã, hoje eu vou visitar um amigo agora de noite,  
**Lucas Biasetton:** Uhum.  
**Gustavo Rodriguez:** daqui a pouco daí vou ficar muito chapado, voltar para casa e desbaiar na minha cama. Mas a partir de amanhã cedo, eu tô on acho que uma boa rotina pode ser. Eh, a gente de manhã fala, não por causa não necessariamente, só troca algum, troca informação, você fala para validar como tá o que vem. Aí, fim do dia, a gente dá uma olhada no que avançou, como e eu vou te prando se eu precisar de alguma coisa no  
**Lucas Biasetton:** É o que a gente pode fazer.  
**Gustavo Rodriguez:** meio do  
**Lucas Biasetton:** É, e talvez isso é meio coisa de Eita,  
   
 

### 01:37:42 {#01:37:42}

   
**Gustavo Rodriguez:** caminho.  
**Lucas Biasetton:** eu sumi. Sumi. Ah,  
**Gustavo Rodriguez:** Não tô te ouvindo.  
**Lucas Biasetton:** eh,  
**Gustavo Rodriguez:** É só de eu  
**Lucas Biasetton:** é, tá, tá apanhando aqui. Acho que eu tô confocando com pouca bateria. Eh,  
**Gustavo Rodriguez:** sofrendo.  
**Lucas Biasetton:** mas o que a gente pode fazer? Fazer que nem tipo aqueles gamers e ficar num Discord aberto, entendeu? Quando eu não tiver em reunião, eu fico no Discord aberto.  
**Gustavo Rodriguez:** Eu faço isso com grupo de amigos da escola porque eles são nerdes.  
**Lucas Biasetton:** É tipo aberto,  
**Gustavo Rodriguez:** Eles são do grupo de pessoas que tm essa cultura.  
**Lucas Biasetton:** é aberto entre eu e você,  
**Gustavo Rodriguez:** É, eu tô ligado. Essa bolha às  
**Lucas Biasetton:** né? Tipo, e aí eu quando eu não tiver em reunião,  
**Gustavo Rodriguez:** vezes  
**Lucas Biasetton:** eu deixo ele aberto e aí se precisar de alguma coisa, você eu tô lá online. Pode ser um MITS também. Mits tem como ficar infinito,  
**Gustavo Rodriguez:** o Discord é mais feito para isso. Mit, acho que ia encher o  
**Lucas Biasetton:** tá? É, então, tipo, aí eu fico on e o que você precisar,  
   
 

### 01:38:34

   
**Gustavo Rodriguez:** saco.  
**Lucas Biasetton:** você me puxa lá,  
**Gustavo Rodriguez:** Combinado. Pode ser. Gostei de  
**Lucas Biasetton:** que aí a hora que você entrar e eu tiver disponível já não precisa marcar,  
**Gustavo Rodriguez:** ficar.  
**Lucas Biasetton:** tipo, ai você pode estar o horário e tal, quando eu tiver lá eu posso e aí eu fico lá enquanto não tiver  
**Gustavo Rodriguez:** Beleza, fechado.  
**Lucas Biasetton:** reunião.  
**Gustavo Rodriguez:** No trabalho, você usa mits,  
**Lucas Biasetton:** uso não,  
**Gustavo Rodriguez:** é, você fica online,  
**Lucas Biasetton:** me ouens.  
**Gustavo Rodriguez:** não te desculpa,  
**Lucas Biasetton:** Isso  
**Gustavo Rodriguez:** eu tenho essa p\*\*\*\*.  
**Lucas Biasetton:** não,  
**Gustavo Rodriguez:** Só te adicionar também.  
**Lucas Biasetton:** mas é bom. Sei lá, para mim tudo faz.  
**Gustavo Rodriguez:** Mas tá, não não dando para usar. O Discord funciona bem, é só porque da já tá lá no  
**Lucas Biasetton:** É, não, pode ser, pode ser o pode ser o Teams também.  
**Gustavo Rodriguez:** mitão.  
**Lucas Biasetton:** Pode ser o Teams.  
**Gustavo Rodriguez:** Me teams,  
**Lucas Biasetton:** Isso sim.  
**Gustavo Rodriguez:** isso não é mit teams é que é tipo o contrário, né? É tipo inverter algumas letras.  
**Lucas Biasetton:** Sim.  
**Gustavo Rodriguez:** Tá bom. f\*\*\*-se. É  
**Lucas Biasetton:** Eh, não.  
   
 

### 01:39:35 {#01:39:35}

   
**Lucas Biasetton:** Tá. E cara, beleza. Eu acho que é isso, então, né?  
**Gustavo Rodriguez:** isso.  
**Lucas Biasetton:** E aí eu vou, eu já tava explorando um pouco como é que a gente vai apresentar as informações no box e aí eu vou continuar desenvolvendo isso para quando a gente tiver os dados só jogar, entendeu? Tipo texto,  
**Gustavo Rodriguez:** Perfeito.  
**Lucas Biasetton:** cores dos mapas.  
**Gustavo Rodriguez:** Boa. Isso é bom.  
**Lucas Biasetton:** as cores dos mapas estavam uma bosta.  
**Gustavo Rodriguez:** Ótimo. Isso é um bom adianto.  
**Lucas Biasetton:** É.  
**Gustavo Rodriguez:** Um bom adianto. Muito bem.  
**Lucas Biasetton:** E aí eu já resolvo isso e aí você vai me me acionando conforme a gente precisar.  
**Gustavo Rodriguez:** Perfeito, fechado.  
**Lucas Biasetton:** Ai meu Deus.  
**Gustavo Rodriguez:** Ó,  
**Lucas Biasetton:** É isso.  
**Gustavo Rodriguez:** just time.  
**Lucas Biasetton:** Boa. Tá bom. Então, nós falamos amanhã de novo.  
**Gustavo Rodriguez:** Ótimo.  
**Lucas Biasetton:** E,  
**Gustavo Rodriguez:** Fechado.  
**Lucas Biasetton:** cara,  
**Gustavo Rodriguez:** Manda mensagem de manhã quando tiver on.  
**Lucas Biasetton:** eu vou tá on cedo, então eu crio a sala e fico lá e aí qualqu coisa você  
**Gustavo Rodriguez:** Beleza,  
**Lucas Biasetton:** entra.  
**Gustavo Rodriguez:** combinado.  
**Lucas Biasetton:** Boa.  
**Gustavo Rodriguez:** É isso.  
**Lucas Biasetton:** É isso.  
**Gustavo Rodriguez:** Boa,  
**Lucas Biasetton:** Vamos,  
**Gustavo Rodriguez:** backit.  
**Lucas Biasetton:** vamos fazer o como é que chama?  
**Gustavo Rodriguez:** Bora.  
**Lucas Biasetton:** Quando a pessoa refaz a cara lá.  
**Gustavo Rodriguez:** Eh, harmonização facial, a harmonização do projeto do filho aqui. Sim, sim.  
   
 

### A transcrição foi encerrada após 01:41:17

*Esta transcrição editável foi gerada por computador e pode conter erros. As pessoas também podem alterar o texto depois que ele for criado.*