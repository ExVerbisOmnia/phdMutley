# Script de Extração v2.0 - Guia de Atualização
## Extração Flexível com Identificação por Nome de Arquivo

**Data**: 06 de Novembro de 2025  
**Versão**: 2.0 - Flexible ID Extraction  

---

## 🎯 O Que Mudou na Versão 2.0

### ✅ Novas Funcionalidades

1. **Variável Global `PDFS_FOLDER_PATH`** (Linha 100)
   - Caminho para a pasta de PDFs configurável no topo do script
   - Valor padrão: `"tests/extraction_test"` (relativo ao projeto)
   - **VOCÊ PODE EDITAR** essa variável diretamente no script

2. **Extração Flexível de Identificadores**
   - Aceita **dois padrões** de nomeação de arquivos:
     - `ID_XXXX_filename.pdf` (teste manual, ex: `ID_0001_test.pdf`)
     - `decision-CaseID.pdf` (produção, ex: `decision-BR-2020-1234.pdf`)

3. **UUID Determinístico**
   - Gera **sempre o mesmo UUID** para o mesmo identificador
   - Usa UUID v5 (SHA-1) com namespace fixo do projeto
   - Permite verificar se já foi processado

4. **Verificação Automática de Duplicatas**
   - Antes de processar, verifica se UUID já existe no banco
   - **Pula automaticamente** PDFs já processados
   - Evita reprocessamento desnecessário

5. **Atualização da Tabela `documents`**
   - Cria/atualiza registro na tabela `documents`
   - Popula campos: `document_id`, `case_id`, `page_count`, `file_size_bytes`, `metadata`
   - Mantém integridade referencial com `extracted_texts`

---

## 📁 Estrutura de Identificação

### Como Funciona

```
Arquivo PDF → Extrai Identificador → Gera UUID Determinístico → Verifica no Banco
```

### Exemplo 1: Teste Manual (ID_XXXX_filename.pdf)
```bash
# Arquivo: ID_0001_silva_vs_brazil.pdf
Identificador extraído: "0001"
UUID gerado: e.g., "12345678-1234-5678-1234-567812345678"
# Sempre o mesmo UUID para "0001"
```

### Exemplo 2: Produção (decision-CaseID.pdf)
```bash
# Arquivo: decision-BR-2020-1234.pdf
Identificador extraído: "BR-2020-1234"
UUID gerado: e.g., "87654321-4321-8765-4321-876543218765"
# Sempre o mesmo UUID para "BR-2020-1234"
```

### ⚠️ Importante: Namespace UUID
```python
# Linha 104 do script
PROJECT_UUID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d')

# Este UUID é FIXO para o projeto
# Garante que o mesmo identificador sempre gera o mesmo UUID
# NÃO modifique a menos que queira reiniciar tudo do zero
```

---

## 🚀 Como Usar

### Preparação Inicial

1. **Criar Diretório de Teste**
```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
mkdir -p tests/extraction_test
```

2. **Renomear PDFs de Teste**
```bash
# Copiar PDFs para a pasta de teste
cp path/to/pdf1.pdf tests/extraction_test/ID_0001_test1.pdf
cp path/to/pdf2.pdf tests/extraction_test/ID_0002_test2.pdf
# ... até ID_0015

# OU usar um loop:
cd tests/extraction_test
counter=1
for file in *.pdf; do
    mv "$file" "ID_$(printf '%04d' $counter)_${file}"
    ((counter++))
done
```

3. **Copiar Script para o Projeto**
```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
cp /caminho/do/script/extract_pdf_text_v2.py scripts/phase1/
```

### Execução - Modo Teste

```bash
# Navegar para o projeto
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Ativar ambiente virtual
source venv/bin/activate

# Executar (usa PDFS_FOLDER_PATH do script = tests/extraction_test)
python scripts/phase1/extract_pdf_text_v2.py --test --limit 15
```

### Execução - Modo Produção

**Depois de validar o teste**, edite o script:

```python
# Linha 100 - EDITAR AQUI:
# Antes (teste):
PDFS_FOLDER_PATH = "tests/extraction_test"

# Depois (produção):
PDFS_FOLDER_PATH = "phdMutley/pdfs/downloaded"
```

Então execute:
```bash
python scripts/phase1/extract_pdf_text_v2.py
```

### Alternativa: Override na Linha de Comando

```bash
# Sem editar o script, use --pdf-dir:
python scripts/phase1/extract_pdf_text_v2.py \
    --pdf-dir phdMutley/pdfs/downloaded
```

---

## 🔍 Verificação de Resultados

### 1. Verificar PDFs Processados
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    document_id,
    extraction_method,
    extraction_quality,
    is_scanned,
    character_count,
    word_count,
    page_count,
    created_at
FROM extracted_texts
ORDER BY created_at DESC
LIMIT 15;
"
```

### 2. Verificar Identificadores e UUIDs
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    d.document_id,
    d.metadata->>'identifier' as identifier,
    d.metadata->>'original_filename' as filename,
    e.extraction_quality
FROM documents d
LEFT JOIN extracted_texts e ON d.document_id = e.document_id
ORDER BY d.created_at DESC
LIMIT 15;
"
```

### 3. Verificar Duplicatas (Deve retornar 0)
```bash
sudo -u postgres psql -d climate_litigation -c "
SELECT document_id, COUNT(*) as count
FROM extracted_texts
GROUP BY document_id
HAVING COUNT(*) > 1;
"
```

### 4. Ver JSON Backups
```bash
ls -lh data/extraction_backups/
cat data/extraction_backups/extraction_0001.json | head -50
```

---

## 📊 Fluxo de Trabalho Completo

### Phase 1A: Teste Inicial ✅ VOCÊ ESTÁ AQUI

```bash
# 1. Preparar 15 PDFs de teste
mkdir -p tests/extraction_test
# [Copiar e renomear PDFs como ID_0001 até ID_0015]

# 2. Executar extração
python scripts/phase1/extract_pdf_text_v2.py --test --limit 15

# 3. Verificar resultados
sudo -u postgres psql -d climate_litigation -c "SELECT COUNT(*) FROM extracted_texts;"

# 4. Validar manualmente 5 casos
# [Comparar PDF original com texto extraído]

# 5. Executar segunda vez (teste de duplicatas)
python scripts/phase1/extract_pdf_text_v2.py --test --limit 15
# Deve mostrar: "Already processed: 15" e "To process: 0"
```

### Phase 1B: Produção (Após Validação)

```bash
# 1. Editar script (linha 100):
PDFS_FOLDER_PATH = "phdMutley/pdfs/downloaded"

# 2. Fazer backup do banco
sudo -u postgres pg_dump -d climate_litigation > backup_pre_full_extraction.sql

# 3. Executar produção
python scripts/phase1/extract_pdf_text_v2.py

# 4. Monitorar progresso (em outro terminal)
watch -n 30 'sudo -u postgres psql -d climate_litigation -c "SELECT COUNT(*) FROM extracted_texts;"'

# 5. Gerar relatório final
sudo -u postgres psql -d climate_litigation -c "
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN extraction_quality = 'high' THEN 1 ELSE 0 END) as high_quality,
    SUM(CASE WHEN extraction_quality = 'medium' THEN 1 ELSE 0 END) as medium_quality,
    SUM(CASE WHEN extraction_quality = 'low' THEN 1 ELSE 0 END) as low_quality,
    SUM(CASE WHEN is_scanned = true THEN 1 ELSE 0 END) as scanned
FROM extracted_texts;
"
```

---

## 🔧 Resolução de Problemas v2.0

### Problema: "Cannot extract identifier from filename"

**Causa**: Nome do arquivo não segue os padrões esperados

**Solução**:
```bash
# Verificar formato dos arquivos
ls tests/extraction_test/*.pdf

# Devem ser:
# ID_0001_nome.pdf ou decision-CaseID.pdf

# Renomear se necessário:
mv arquivo_errado.pdf ID_0001_arquivo_errado.pdf
```

### Problema: "Document already processed" mas você quer reprocessar

**Causa**: UUID já existe no banco

**Solução 1 - Deletar registro específico**:
```bash
# Obter UUID do arquivo
python -c "
import uuid
namespace = uuid.UUID('a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d')
doc_uuid = uuid.uuid5(namespace, '0001')  # Substitua '0001' pelo identificador
print(doc_uuid)
"

# Deletar do banco
sudo -u postgres psql -d climate_litigation -c "
DELETE FROM extracted_texts WHERE document_id = 'UUID_AQUI';
DELETE FROM documents WHERE document_id = 'UUID_AQUI';
"
```

**Solução 2 - Limpar todos os testes**:
```bash
sudo -u postgres psql -d climate_litigation -c "
-- CUIDADO: Isso deleta TUDO
DELETE FROM extracted_texts;
DELETE FROM documents;
"
```

### Problema: UUID mudou entre execuções

**Causa**: Você mudou o `PROJECT_UUID_NAMESPACE`

**Solução**: 
- NÃO mude o namespace a menos que queira começar do zero
- Se precisar mudar, delete todos os registros primeiro

### Problema: Tabela `documents` vazia

**Causa**: Script v1.0 não populava `documents`

**Solução**: Execute v2.0 que popula ambas as tabelas automaticamente

---

## 📋 Checklist de Migração v1.0 → v2.0

- [ ] Script v2.0 copiado para `scripts/phase1/`
- [ ] Diretório de teste criado: `tests/extraction_test/`
- [ ] 15 PDFs renomeados com padrão `ID_XXXX_filename.pdf`
- [ ] Variável `PDFS_FOLDER_PATH` aponta para pasta correta
- [ ] Teste executado: `--test --limit 15`
- [ ] Resultados verificados no PostgreSQL
- [ ] JSON backups criados em `data/extraction_backups/`
- [ ] Teste de duplicatas realizado (segunda execução)
- [ ] Validação manual de 5 casos concluída
- [ ] Aprovação de Mutley obtida
- [ ] Backup do banco criado antes de produção
- [ ] Script atualizado para pasta de produção
- [ ] Extração completa executada

---

## 💡 Dicas Importantes

### 1. Namespace UUID é Sagrado
```python
# NÃO MUDE ISTO:
PROJECT_UUID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d')

# Se mudar, todos os UUIDs mudam e o banco não reconhece mais!
```

### 2. Testar Identificação Antes de Processar
```python
# Script de teste rápido:
import re
from pathlib import Path

pdf_dir = Path("tests/extraction_test")
for pdf in pdf_dir.glob("*.pdf"):
    # Pattern 1: ID_XXXX
    match1 = re.search(r'ID_(\d+)_', pdf.name)
    # Pattern 2: decision-CaseID
    match2 = re.search(r'decision-([^\.]+)\.pdf', pdf.name)
    
    if match1:
        print(f"{pdf.name} → ID: {match1.group(1)}")
    elif match2:
        print(f"{pdf.name} → CaseID: {match2.group(1)}")
    else:
        print(f"{pdf.name} → ✗ SEM MATCH!")
```

### 3. Alternância Teste ↔ Produção

**Opção A**: Editar variável no script
```python
# Para teste:
PDFS_FOLDER_PATH = "tests/extraction_test"

# Para produção:
PDFS_FOLDER_PATH = "phdMutley/pdfs/downloaded"
```

**Opção B**: Usar argumento de linha de comando
```bash
# Teste:
python extract_pdf_text_v2.py --pdf-dir tests/extraction_test --test --limit 15

# Produção:
python extract_pdf_text_v2.py --pdf-dir phdMutley/pdfs/downloaded
```

### 4. Progressão Gradual Recomendada
```bash
# 1. Teste com 5 PDFs
python extract_pdf_text_v2.py --test --limit 5

# 2. Teste com 15 PDFs
python extract_pdf_text_v2.py --test --limit 15

# 3. Teste com 50 PDFs (se disponível)
python extract_pdf_text_v2.py --test --limit 50

# 4. Produção completa
python extract_pdf_text_v2.py
```

---

## 🎓 Considerações Acadêmicas

### Reprodutibilidade
✅ UUID determinístico garante que:
- Mesma execução em diferentes máquinas gera mesmos UUIDs
- Processamento pode ser interrompido e retomado
- Fácil verificar se documento já foi processado

### Transparência
✅ Identificador original preservado em `metadata`:
```json
{
  "identifier": "0001",
  "original_filename": "ID_0001_test.pdf",
  "extraction_date": "2025-11-06T..."
}
```

### Auditoria
✅ Três níveis de rastreamento:
1. **Logs**: Todas as operações registradas
2. **JSON Backups**: Cópia independente dos resultados
3. **PostgreSQL**: Dados estruturados para análise

---

## 📞 Próximos Passos

1. ✅ **Executar teste com 15 PDFs**
2. ⏳ Validar qualidade dos resultados
3. ⏳ Revisar com Mutley
4. ⏳ Executar extração completa (~2.924 documentos)
5. ⏳ Análise exploratória dos textos extraídos
6. ⏳ Preparar Phase 2: Identificação de citações

---

## 🔗 Arquivos Relacionados

- [Script v2.0](computer:///mnt/user-data/outputs/scripts/phase1/extract_pdf_text_v2.py)
- [Resumo Executivo](computer:///mnt/user-data/outputs/RESUMO_EXECUTIVO_EXTRACAO.md)
- [Comandos Rápidos](computer:///mnt/user-data/outputs/COMANDOS_RAPIDOS.md)

---

**Versão**: 2.0  
**Status**: ✅ Pronto para Teste  
**Última Atualização**: 06 de Novembro de 2025
