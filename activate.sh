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
