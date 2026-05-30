import os
from pathlib import Path
from markitdown import MarkItDown

def convert_pdfs_to_md(input_dir: str, output_dir: str):
    """
    Converts all PDF files in input_dir to Markdown format using MarkItDown
    and saves them in output_dir.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"Error: Directory '{input_dir}' not found.")
        return
        
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Inicializa o conversor (se o usuário decidir usar OCR, adicionaremos o llm_client aqui futuramente)
    md_converter = MarkItDown()
    
    pdf_files = list(input_path.glob('*.pdf'))
    
    if not pdf_files:
        print(f"No PDF files found in '{input_dir}'.")
        return
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name} ... ", end='', flush=True)
        try:
            result = md_converter.convert(str(pdf_file))
            
            # Gera o nome do arquivo de saída trocando .pdf para .md
            output_file = output_path / f"{pdf_file.stem}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.text_content)
                
            print(f"Success! Saved to {output_file.name}")
            
        except Exception as e:
            print(f"Failed! Error: {e}")

if __name__ == "__main__":
    # Define as pastas padrão
    BASE_DIR = Path(__file__).parent.parent
    INPUT_DIR = BASE_DIR / "artigos"
    OUTPUT_DIR = BASE_DIR / "artigos_md"
    
    convert_pdfs_to_md(INPUT_DIR, OUTPUT_DIR)
