#!/usr/bin/env python3
"""
PDF Downloader - Version 1
Simple script to download a single PDF from a URL
"""

import requests
from pathlib import Path


def download_single_pdf(url: str, output_path: str, timeout: int = 30) -> tuple[bool, str]:
    """
    Baixa um PDF de uma URL.
    
    Args:
        url: URL do PDF
        output_path: Caminho onde salvar (incluindo nome do arquivo)
        timeout: Timeout em segundos (default: 30)
    
    Returns:
        Tupla (sucesso: bool, mensagem: str)
    
    Conceitos importantes:
    - requests.get(): Faz requisição HTTP GET
    - response.raise_for_status(): Levanta exceção se status HTTP não for 2xx
    - response.content: Conteúdo binário da resposta (bytes do PDF)
    - Path().parent.mkdir(): Cria diretórios pais se não existirem
    """
    try:
        # Fazer requisição HTTP
        response = requests.get(url, timeout=timeout)
        
        # Verificar se deu certo (status 200-299)
        response.raise_for_status()
        
        # Criar diretórios se não existirem
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Salvar PDF
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        return True, f"Success: {output_file}"
        
    except requests.exceptions.Timeout:
        return False, f"Timeout after {timeout}s"
        
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP Error: {e.response.status_code}"
        
    except requests.exceptions.RequestException as e:
        return False, f"Request Error: {str(e)}"
        
    except Exception as e:
        return False, f"Unexpected Error: {str(e)}"


def main():
    """Função principal para testar o download"""
    
    # TESTE: Substitua por uma URL real da sua base
    test_url = "https://example.com/sample.pdf"
    test_output = "../data/pdfs_test/test_download.pdf"
    
    print(f"Downloading: {test_url}")
    print(f"Output: {test_output}")
    print("-" * 60)
    
    success, message = download_single_pdf(test_url, test_output)
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")


if __name__ == '__main__':
    main()