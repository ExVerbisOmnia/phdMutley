# Projeto de Análise de Citações em Litigância Climática

## 📋 Visão Geral

Projeto de pesquisa de doutorado para análise quantitativa de citações entre decisões judiciais em casos de litigância climática, com foco especial nos fluxos de citação entre cortes do Norte Global e Sul Global.

**Base de Dados**: Climate Case Chart (Columbia University & LSE)  
**Período do Projeto**: Outubro - Novembro 2025  
**Versão Python**: 3.13.9  
**Localização**: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

## 🎯 Objetivos

### Objetivo Principal
Fornecer insights e dados qualificados sobre as relações de citação direta em decisões de cortes superiores em casos de litigância climática.

### Objetivo Específico
Identificar padrões de citação entre:
- Cortes do Norte Global citando outras do Norte
- Cortes do Sul Global citando cortes do Norte
- Cortes do Norte Global citando cortes do Sul

## 📁 Estrutura do Projeto

```
phdMutley/
├── data/
│   ├── raw/              # CSV original do Climate Case Chart
│   ├── processed/        # Dados processados e limpos
│   ├── cleaned/          # Versão final filtrada
│   └── samples/          # Amostras para validação
├── pdfs/
│   ├── downloaded/       # PDFs das decisões baixados
│   └── failed/           # Log de downloads falhados
├── scripts/
│   ├── phase0/           # Fundação e preparação
│   ├── phase1/           # Extração e preprocessing
│   ├── phase2/           # Identificação de citações
│   ├── phase3/           # Análise quantitativa
│   ├── phase4/           # Visualização
│   └── utils/            # Funções auxiliares
├── notebooks/            # Jupyter notebooks para análises
├── outputs/
│   ├── reports/          # Relatórios e documentos
│   ├── visualizations/   # Gráficos e visualizações
│   ├── databases/        # Bancos de dados
│   └── exports/          # Dados para exportação
├── docs/
│   ├── methodology/      # Documentação metodológica
│   └── technical/        # Documentação técnica
├── logs/                 # Arquivos de log
├── config/               # Arquivos de configuração
└── venv/                 # Ambiente virtual Python
```

## 🚀 Começando

### 1. Ativar Ambiente Virtual

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
```

Ou use o script de ativação rápida:

```bash
./activate.sh
```

### 2. Configurar Variáveis de Ambiente

```bash
cp .env.template .env
# Edite .env com suas chaves de API
nano .env  # ou vim, gedit, code, etc.
```

### 3. Verificar Instalação

```bash
python --version  # Deve mostrar Python 3.13.9
pip list          # Ver todas as bibliotecas instaladas
```

### 4. Copiar Dados

```bash
# Copiar o CSV do Climate Case Chart
cp /caminho/para/Document_Data_Download20250929.xlsx data/raw/
```

### 5. Iniciar Jupyter Lab

```bash
jupyter lab
```

## 📚 Bibliotecas Instaladas

### Core Data Science
- pandas, numpy, openpyxl

### Processamento de PDF
- PyPDF2, pdfplumber, pymupdf

### NLP e Linguística
- spacy (com modelos en_core_web_sm e en_core_web_lg)
- langdetect, textblob

### Análise de Redes
- networkx, python-louvain

### Estatística e Machine Learning
- scipy, statsmodels, scikit-learn

### Visualização
- matplotlib, seaborn, plotly, pyvis

### Desenvolvimento
- jupyterlab, notebook
- requests, beautifulsoup4
- tqdm, rich

### Banco de Dados
- sqlalchemy, psycopg2-binary

## 🗓️ Roadmap

### Fase 0: Fundação e Preparação (3-4 dias)
- ✅ Configuração de ambiente
- Análise exploratória do CSV
- Definição de taxonomia Norte/Sul Global

### Fase 1: Extração e Preprocessing (7-10 dias)
- Download de PDFs
- Extração de texto
- Estruturação em banco de dados

### Fase 2: Identificação de Citações (10-12 dias)
- Regex e padrões
- NER (Named Entity Recognition)
- LLM-powered extraction

### Fase 3: Análise Quantitativa (5-7 dias)
- Métricas descritivas
- Análise de rede
- Testes estatísticos

### Fase 4: Visualização e Insights (3-4 dias)
- Grafos de rede
- Dashboards interativos
- Relatórios finais

## 👥 Equipe

- **Gus** (Lucas Biasetton): Desenvolvimento técnico, processamento de dados, análise computacional
- **Mutley**: Pesquisa jurídica, validação metodológica, análise acadêmica

## 📄 Licença

Este é um projeto acadêmico de pesquisa de doutorado.

---

**Última atualização**: Outubro 2025  
**Versão**: 1.0
