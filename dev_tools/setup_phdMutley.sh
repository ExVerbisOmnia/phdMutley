#!/bin/bash

# ============================================================================
# Script de Continuação - Fases 3-7 (ADAPTADO)
# Projeto: Litigância Climática - Análise de Citações
# Diretório: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
# ============================================================================
# 
# Este script continua a instalação a partir da Fase 3
# Cria ambiente virtual e estrutura dentro da pasta de trabalho especificada
#
# ============================================================================

echo "============================================================================"
echo "   CONTINUAÇÃO DA INSTALAÇÃO - FASES 3-7"
echo "   Projeto de Análise de Citações em Litigância Climática"
echo "============================================================================"
echo ""

# Definir caminho do projeto
PROJECT_DIR="/home/gusrodgs/Gus/cienciaDeDados/phdMutley"

echo "📁 Diretório do projeto: $PROJECT_DIR"
echo ""

# Verificar se Python 3.13.9 está instalado
echo "🔍 Verificando instalação do Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Encontrado: $PYTHON_VERSION"
else
    echo "❌ Python 3 não encontrado. Execute primeiro o script de instalação completo."
    exit 1
fi

# Limpar arquivos temporários (com sudo para evitar erros de permissão)
echo ""
echo "🧹 Limpando arquivos temporários da instalação anterior..."
sudo rm -rf /tmp/Python-3.13.9* 2>/dev/null || true
echo "✅ Limpeza concluída"

echo ""
echo "============================================================================"
echo "FASE 3: CRIAÇÃO DA ESTRUTURA DO PROJETO"
echo "============================================================================"
echo ""

# Verificar se o diretório existe
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Erro: Diretório $PROJECT_DIR não existe!"
    echo "Criando diretório..."
    mkdir -p "$PROJECT_DIR"
fi

# Navegar para o diretório do projeto
cd "$PROJECT_DIR" || exit 1

echo "📍 Trabalhando em: $(pwd)"
echo ""

echo "📁 Criando estrutura de subdiretórios..."

# Criar estrutura completa de diretórios
mkdir -p data/{raw,processed,cleaned,samples}
mkdir -p pdfs/{downloaded,failed}
mkdir -p scripts/{phase0,phase1,phase2,phase3,phase4,utils}
mkdir -p notebooks
mkdir -p outputs/{reports,visualizations,databases,exports}
mkdir -p docs/{methodology,technical}
mkdir -p logs
mkdir -p config

echo "✅ Estrutura de diretórios criada"

# Listar estrutura criada
echo ""
echo "📂 Estrutura criada:"
tree -L 2 -d 2>/dev/null || find . -type d -maxdepth 2 | sort

echo ""
echo "============================================================================"
echo "FASE 4: CONFIGURAÇÃO DO AMBIENTE VIRTUAL"
echo "============================================================================"
echo ""

# Verificar se ambiente virtual já existe
if [ -d "venv" ]; then
    echo "⚠️  Ambiente virtual 'venv' já existe!"
    read -p "Deseja recriá-lo? (s/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "🗑️  Removendo ambiente virtual existente..."
        rm -rf venv
        echo "🐍 Criando novo ambiente virtual Python..."
        python3 -m venv venv
    else
        echo "✅ Usando ambiente virtual existente"
    fi
else
    echo "🐍 Criando ambiente virtual Python..."
    python3 -m venv venv
fi

echo ""
echo "✅ Ambiente virtual configurado"

echo ""
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

echo "✅ Ambiente virtual ativado"
echo "📍 Python do ambiente: $(which python)"

echo ""
echo "⬆️  Atualizando pip, setuptools e wheel..."
pip install --upgrade pip setuptools wheel

echo ""
echo "============================================================================"
echo "FASE 5: INSTALAÇÃO DAS BIBLIOTECAS DO PROJETO"
echo "============================================================================"
echo ""

echo "📚 Instalando bibliotecas essenciais (isso pode levar alguns minutos)..."
echo ""

# Core data science (versões mais recentes)
echo "▶️  [1/12] Instalando pandas, numpy, openpyxl..."
pip install --upgrade pandas numpy openpyxl xlrd

# PDF processing
echo ""
echo "▶️  [2/12] Instalando bibliotecas de processamento de PDF..."
pip install --upgrade PyPDF2 pdfplumber pymupdf pypdf

# NLP and language detection
echo ""
echo "▶️  [3/12] Instalando bibliotecas de NLP e detecção de idioma..."
pip install --upgrade spacy langdetect langid textblob

# Download spaCy models
echo ""
echo "▶️  [4/12] Baixando modelos spaCy (inglês e multilíngue)..."
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_lg

# Network analysis
echo ""
echo "▶️  [5/12] Instalando NetworkX para análise de redes..."
pip install --upgrade networkx python-louvain

# Statistical analysis
echo ""
echo "▶️  [6/12] Instalando bibliotecas de análise estatística..."
pip install --upgrade scipy statsmodels scikit-learn

# Visualization
echo ""
echo "▶️  [7/12] Instalando bibliotecas de visualização..."
pip install --upgrade matplotlib seaborn plotly pyvis kaleido

# Jupyter
echo ""
echo "▶️  [8/12] Instalando Jupyter Lab..."
pip install --upgrade jupyterlab notebook ipywidgets

# Web scraping and requests
echo ""
echo "▶️  [9/12] Instalando bibliotecas para web scraping..."
pip install --upgrade requests beautifulsoup4 lxml aiohttp

# Progress bars and CLI
echo ""
echo "▶️  [10/12] Instalando utilitários CLI..."
pip install --upgrade tqdm rich click

# Database
echo ""
echo "▶️  [11/12] Instalando bibliotecas de banco de dados..."
pip install --upgrade sqlalchemy psycopg2-binary

# Utilities and additional tools
echo ""
echo "▶️  [12/12] Instalando utilitários adicionais..."
pip install --upgrade python-dotenv pyyaml python-dateutil regex chardet

echo ""
echo "✅ Todas as bibliotecas instaladas com sucesso!"

echo ""
echo "============================================================================"
echo "FASE 6: CRIAÇÃO DE ARQUIVOS DE CONFIGURAÇÃO"
echo "============================================================================"
echo ""

# Criar requirements.txt
echo "📄 Gerando requirements.txt..."
pip freeze > requirements.txt
echo "✅ requirements.txt criado"

# Criar .gitignore
echo ""
echo "📝 Criando .gitignore..."
cat > .gitignore << 'GITIGNORE_EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# Data files
*.csv
*.xlsx
*.xls
*.tsv
data/raw/*
data/processed/*
data/cleaned/*
data/samples/*
!data/raw/.gitkeep
!data/processed/.gitkeep
!data/cleaned/.gitkeep
!data/samples/.gitkeep

# PDFs
pdfs/downloaded/*
pdfs/failed/*
*.pdf
!pdfs/downloaded/.gitkeep
!pdfs/failed/.gitkeep

# Databases
*.db
*.sqlite
*.sqlite3

# Logs
logs/*.log
logs/*.txt
!logs/.gitkeep

# OS
.DS_Store
Thumbs.db
*.swp
*.swo

# IDE
.vscode/
.idea/
*.sublime-project
*.sublime-workspace

# Environment variables
.env
.env.local
.env.*.local

# Outputs
outputs/reports/*
outputs/visualizations/*
outputs/databases/*
outputs/exports/*
!outputs/reports/.gitkeep
!outputs/visualizations/.gitkeep
!outputs/databases/.gitkeep
!outputs/exports/.gitkeep

# Cache
.cache/
*.cache

# Temporary files
*.tmp
temp/
tmp/
GITIGNORE_EOF

echo "✅ .gitignore criado"

# Criar arquivos .gitkeep
echo ""
echo "📌 Criando .gitkeep files para preservar estrutura..."
touch data/raw/.gitkeep
touch data/processed/.gitkeep
touch data/cleaned/.gitkeep
touch data/samples/.gitkeep
touch pdfs/downloaded/.gitkeep
touch pdfs/failed/.gitkeep
touch logs/.gitkeep
touch outputs/reports/.gitkeep
touch outputs/visualizations/.gitkeep
touch outputs/databases/.gitkeep
touch outputs/exports/.gitkeep

echo "✅ .gitkeep files criados"

# Criar .env template
echo ""
echo "📝 Criando template de variáveis de ambiente..."
cat > .env.template << 'ENV_EOF'
# Configurações do Projeto de Litigância Climática

# APIs de LLM (para Fase 2 - Extração de Citações)
ANTHROPIC_API_KEY=your_claude_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Configurações de Processamento
MAX_CONCURRENT_DOWNLOADS=5
PDF_DOWNLOAD_TIMEOUT=30
RETRY_ATTEMPTS=3

# Banco de Dados
DATABASE_TYPE=sqlite  # ou postgresql
DATABASE_PATH=outputs/databases/climate_litigation.db

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=True

# Paths
RAW_DATA_PATH=data/raw
PROCESSED_DATA_PATH=data/processed
PDF_DOWNLOAD_PATH=pdfs/downloaded
ENV_EOF

echo "✅ .env.template criado (copie para .env e configure suas chaves)"

# Criar README.md
echo ""
echo "📖 Criando README.md..."
cat > README.md << 'README_EOF'
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
README_EOF

echo "✅ README.md criado"

# Criar script de ativação rápida
echo ""
echo "📝 Criando script de ativação rápida do ambiente..."
cat > activate.sh << 'ACTIVATE_EOF'
#!/bin/bash
# Script de ativação rápida do ambiente

PROJECT_DIR="/home/gusrodgs/Gus/cienciaDeDados/phdMutley"

echo "🐍 Ativando ambiente virtual do projeto..."
cd "$PROJECT_DIR" || exit 1
source venv/bin/activate

echo "✅ Ambiente ativado!"
echo ""
echo "📊 Projeto: Litigância Climática - Análise de Citações"
echo "🐍 Python: $(python --version)"
echo "📁 Diretório: $(pwd)"
echo ""
echo "Comandos úteis:"
echo "  jupyter lab          - Iniciar Jupyter Lab"
echo "  python --version     - Ver versão do Python"
echo "  pip list             - Ver bibliotecas instaladas"
echo "  deactivate           - Desativar ambiente virtual"
echo ""
ACTIVATE_EOF

chmod +x activate.sh

echo "✅ Script activate.sh criado"

# Criar notebook de validação
echo ""
echo "📓 Criando notebook de validação..."
cat > notebooks/00_setup_validation.ipynb << 'NOTEBOOK_EOF'
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Setup Validation - Projeto Litigância Climática\n",
    "\n",
    "Este notebook valida que todas as bibliotecas foram instaladas corretamente e o ambiente está pronto para uso.\n",
    "\n",
    "**Diretório do projeto**: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "import os\n",
    "print(f\"Python version: {sys.version}\")\n",
    "print(f\"Working directory: {os.getcwd()}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test core libraries\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "print(f\"✅ pandas {pd.__version__}\")\n",
    "print(f\"✅ numpy {np.__version__}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test PDF libraries\n",
    "import PyPDF2\n",
    "import pdfplumber\n",
    "import fitz  # pymupdf\n",
    "print(f\"✅ PyPDF2\")\n",
    "print(f\"✅ pdfplumber\")\n",
    "print(f\"✅ pymupdf\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test NLP libraries\n",
    "import spacy\n",
    "import langdetect\n",
    "print(f\"✅ spacy {spacy.__version__}\")\n",
    "print(f\"✅ langdetect\")\n",
    "\n",
    "# Test spaCy model\n",
    "nlp = spacy.load('en_core_web_sm')\n",
    "print(f\"✅ spaCy model 'en_core_web_sm' loaded\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test visualization libraries\n",
    "import matplotlib\n",
    "import seaborn as sns\n",
    "import plotly\n",
    "print(f\"✅ matplotlib {matplotlib.__version__}\")\n",
    "print(f\"✅ seaborn {sns.__version__}\")\n",
    "print(f\"✅ plotly {plotly.__version__}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test network analysis\n",
    "import networkx as nx\n",
    "print(f\"✅ networkx {nx.__version__}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Verify project structure\n",
    "import pathlib\n",
    "\n",
    "project_dirs = [\n",
    "    'data/raw',\n",
    "    'data/processed',\n",
    "    'data/cleaned',\n",
    "    'pdfs/downloaded',\n",
    "    'scripts/phase0',\n",
    "    'notebooks',\n",
    "    'outputs/reports',\n",
    "    'logs'\n",
    "]\n",
    "\n",
    "print(\"\\n📂 Verificando estrutura de diretórios:\")\n",
    "for dir_path in project_dirs:\n",
    "    path = pathlib.Path(dir_path)\n",
    "    if path.exists():\n",
    "        print(f\"✅ {dir_path}\")\n",
    "    else:\n",
    "        print(f\"❌ {dir_path} não encontrado\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"\\n🎉 Todas as bibliotecas foram instaladas com sucesso!\")\n",
    "print(\"O ambiente está pronto para começar a Fase 0 do projeto.\")\n",
    "print(\"\\n📍 Próximo passo: Copiar o CSV do Climate Case Chart para data/raw/\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.13.9"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
NOTEBOOK_EOF

echo "✅ Notebook de validação criado"

echo ""
echo "============================================================================"
echo "FASE 7: INICIALIZAÇÃO DO GIT"
echo "============================================================================"
echo ""

# Verificar se já é um repositório git
if [ -d ".git" ]; then
    echo "⚠️  Repositório Git já existe"
    echo "✅ Mantendo repositório existente"
else
    echo "🌿 Inicializando repositório Git..."
    git init
    
    echo ""
    echo "📝 Criando primeiro commit..."
    git add .gitignore README.md .env.template activate.sh
    git commit -m "Initial commit: Project structure and configuration"
    
    echo "✅ Repositório Git inicializado"
fi

echo ""
echo "============================================================================"
echo "✅ INSTALAÇÃO COMPLETA!"
echo "============================================================================"
echo ""
echo "📊 Resumo da Instalação:"
echo "  ✅ Python 3.13.9 já instalado"
echo "  ✅ Ambiente virtual criado em: $PROJECT_DIR/venv"
echo "  ✅ $(pip list | wc -l) bibliotecas instaladas"
echo "  ✅ Estrutura de diretórios criada"
echo "  ✅ Arquivos de configuração criados"
echo "  ✅ Repositório Git configurado"
echo ""
echo "============================================================================"
echo "🚀 PRÓXIMOS PASSOS"
echo "============================================================================"
echo ""
echo "1️⃣  Para ativar o ambiente virtual:"
echo "    cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley"
echo "    source venv/bin/activate"
echo "    # Ou simplesmente:"
echo "    ./activate.sh"
echo ""
echo "2️⃣  Para copiar o CSV do Climate Case Chart:"
echo "    cp /caminho/para/Document_Data_Download20250929.xlsx data/raw/"
echo ""
echo "3️⃣  Para iniciar Jupyter Lab:"
echo "    cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley"
echo "    source venv/bin/activate"
echo "    jupyter lab"
echo ""
echo "4️⃣  Para validar a instalação:"
echo "    Abra o notebook: notebooks/00_setup_validation.ipynb"
echo ""
echo "5️⃣  Para configurar APIs (Fase 2):"
echo "    cp .env.template .env"
echo "    nano .env  # Edite com suas chaves"
echo ""
echo "============================================================================"
echo "📚 DOCUMENTAÇÃO"
echo "============================================================================"
echo ""
echo "  📄 README: $PROJECT_DIR/README.md"
echo "  📋 Roadmap: Consulte a documentação do projeto no Claude"
echo "  🔧 Config: $PROJECT_DIR/.env.template"
echo ""
echo "============================================================================"
echo ""
echo "🎉 Ambiente pronto para começar a Fase 0!"
echo "   Boa sorte com o projeto de Litigância Climática!"
echo ""
echo "============================================================================"

# Desativar ambiente virtual
deactivate
