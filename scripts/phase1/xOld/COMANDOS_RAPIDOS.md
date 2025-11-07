# Quick Reference - Comandos Essenciais

## 🚀 Comandos para Começar

### 1. Verificar Banco de Dados
```bash
# Ver schema da tabela extracted_texts
sudo -u postgres psql -d climate_litigation -c "\d+ extracted_texts"

# Verificar quantos textos já foram extraídos
sudo -u postgres psql -d climate_litigation -c "SELECT COUNT(*) FROM extracted_texts;"

# Ver distribuição de qualidade
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    extraction_quality, 
    COUNT(*) as total,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage
FROM extracted_texts
GROUP BY extraction_quality
ORDER BY total DESC;
"
```

### 2. Preparar Teste
```bash
# Navegar para diretório do projeto
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Criar diretório para PDFs de teste
mkdir -p pdfs/test_sample

# Ativar ambiente virtual
source venv/bin/activate

# Verificar bibliotecas instaladas
python -c "import pdfplumber; print(f'pdfplumber: {pdfplumber.__version__}')"
python -c "import fitz; print(f'PyMuPDF: {fitz.VersionBind}')"
python -c "import PyPDF2; print(f'PyPDF2: {PyPDF2.__version__}')"
```

### 3. Executar Extração de Teste
```bash
# Teste com 15 PDFs
python scripts/phase1/extract_pdf_text.py \
    --test \
    --pdf-dir pdfs/test_sample \
    --limit 15
```

### 4. Verificar Resultados
```bash
# Ver último log
ls -lt logs/test_extraction_*.log | head -1
tail -100 $(ls -t logs/test_extraction_*.log | head -1)

# Ver backups JSON criados
ls -lh data/extraction_backups/

# Consultar textos extraídos no banco
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    document_id,
    extraction_method,
    extraction_quality,
    is_scanned,
    character_count,
    word_count,
    page_count
FROM extracted_texts
ORDER BY created_at DESC
LIMIT 10;
"
```

### 5. Estatísticas Detalhadas
```bash
# Ver métricas de qualidade
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    extraction_quality,
    AVG(character_count) as avg_chars,
    AVG(word_count) as avg_words,
    AVG(page_count) as avg_pages,
    AVG(extraction_duration_seconds) as avg_time_sec,
    COUNT(*) as total
FROM extracted_texts
GROUP BY extraction_quality;
"

# Ver PDFs escaneados
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    COUNT(*) as total_scanned,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM extracted_texts), 1) as percentage
FROM extracted_texts
WHERE is_scanned = true;
"

# Ver métodos de extração usados
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    extraction_method,
    COUNT(*) as total,
    ROUND(AVG(extraction_duration_seconds), 2) as avg_time_sec
FROM extracted_texts
GROUP BY extraction_method
ORDER BY total DESC;
"
```

---

## 🔧 Comandos de Manutenção

### Limpar Testes Anteriores
```bash
# Deletar registros de teste do banco (CUIDADO!)
sudo -u postgres psql -d climate_litigation -c "DELETE FROM extracted_texts;"

# Deletar backups JSON de teste
rm -rf data/extraction_backups/*

# Deletar logs antigos
rm logs/test_extraction_*.log
```

### Backup do Banco de Dados
```bash
# Fazer backup antes de processar tudo
sudo -u postgres pg_dump -d climate_litigation > backup_pre_extraction_$(date +%Y%m%d).sql

# Restaurar backup se necessário
sudo -u postgres psql -d climate_litigation < backup_pre_extraction_YYYYMMDD.sql
```

### Verificar Espaço em Disco
```bash
# Espaço disponível
df -h /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Tamanho do diretório de backups
du -sh data/extraction_backups/

# Tamanho do banco de dados
sudo -u postgres psql -d climate_litigation -c "
SELECT pg_size_pretty(pg_database_size('climate_litigation'));
"
```

---

## 📊 Queries Úteis

### Ver Texto Extraído de um Documento Específico
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    document_id,
    extraction_method,
    extraction_quality,
    LEFT(raw_text, 500) as text_sample
FROM extracted_texts
WHERE document_id = 'SEU_DOCUMENT_ID_AQUI';
"
```

### Identificar Documentos Problemáticos
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    document_id,
    extraction_quality,
    is_scanned,
    quality_issues
FROM extracted_texts
WHERE extraction_quality IN ('low', 'failed')
ORDER BY created_at DESC;
"
```

### Estatísticas por Página
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    page_count,
    COUNT(*) as num_docs,
    AVG(character_count) as avg_chars,
    AVG(extraction_duration_seconds) as avg_time_sec
FROM extracted_texts
GROUP BY page_count
ORDER BY page_count;
"
```

---

## 🐛 Troubleshooting Rápido

### Problema: Banco não conecta
```bash
# Verificar status
sudo systemctl status postgresql

# Reiniciar se necessário
sudo systemctl restart postgresql

# Testar conexão
sudo -u postgres psql -l
```

### Problema: Biblioteca não encontrada
```bash
# Reinstalar todas
pip install --upgrade pdfplumber PyMuPDF PyPDF2 sqlalchemy psycopg2-binary python-dotenv
```

### Problema: Permissão negada
```bash
# Verificar proprietário dos diretórios
ls -la pdfs/
ls -la data/

# Corrigir permissões se necessário
chown -R gusrodgs:gusrodgs pdfs/ data/ logs/
```

---

## 🎯 Comandos para Processamento Completo

### Quando Pronto para Processar Todos os PDFs
```bash
# CERTIFIQUE-SE de ter feito backup antes!
sudo -u postgres pg_dump -d climate_litigation > backup_pre_full_extraction.sql

# Processar todos (~2-3 horas)
python scripts/phase1/extract_pdf_text.py \
    --pdf-dir pdfs/downloaded \
    --backup-dir data/extraction_backups

# Monitorar progresso em outro terminal
watch -n 30 'sudo -u postgres psql -d climate_litigation -c "SELECT COUNT(*) FROM extracted_texts;"'
```

### Gerar Relatório Final
```bash
sudo -u postgres psql -d climate_litigation -c "
-- Relatório Completo
SELECT 
    COUNT(*) as total_documents,
    SUM(CASE WHEN extraction_quality = 'high' THEN 1 ELSE 0 END) as high_quality,
    SUM(CASE WHEN extraction_quality = 'medium' THEN 1 ELSE 0 END) as medium_quality,
    SUM(CASE WHEN extraction_quality = 'low' THEN 1 ELSE 0 END) as low_quality,
    SUM(CASE WHEN extraction_quality = 'failed' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN is_scanned = true THEN 1 ELSE 0 END) as scanned_pdfs,
    AVG(character_count) as avg_characters,
    AVG(word_count) as avg_words,
    AVG(page_count) as avg_pages,
    SUM(extraction_duration_seconds) / 3600.0 as total_hours
FROM extracted_texts;
"
```

---

## 📝 Copiar Arquivos para o Projeto

```bash
# Do Claude para o projeto real
cp /mnt/user-data/outputs/scripts/phase1/extract_pdf_text.py \
   /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1/

cp /mnt/user-data/outputs/scripts/phase1/README_extraction.md \
   /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1/

# Verificar
ls -la /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1/
```

---

## 🔗 Links Úteis

- [Script Principal](computer:///mnt/user-data/outputs/scripts/phase1/extract_pdf_text.py)
- [README Completo](computer:///mnt/user-data/outputs/scripts/phase1/README_extraction.md)
- [Resumo Executivo](computer:///mnt/user-data/outputs/RESUMO_EXECUTIVO_EXTRACAO.md)

---

**Dica**: Salve este arquivo como referência e mantenha aberto durante o processamento!
