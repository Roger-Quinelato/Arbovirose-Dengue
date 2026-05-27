import json
import sys
import io
import traceback
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE_DIR / "legacy" / "analise_preditiva_dengue.ipynb"

# Import matplotlib and set backend to Agg
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def execute_notebook():
    print(f"Lendo notebook {NOTEBOOK_PATH.name}...")
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    # We will build a custom global namespace
    global_ns = {
        '__name__': '__main__',
        '__doc__': None,
        '__package__': None,
        '__loader__': None,
        '__spec__': None,
    }
    
    execution_counter = 1
    
    for idx, cell in enumerate(nb['cells']):
        if cell['cell_type'] != 'code':
            continue
            
        code = "".join(cell['source'])
        print(f"Executando célula {execution_counter}...")
        
        # We will collect custom displays inside this cell
        cell_displays = []
        
        # Define our custom monkeypatched display function
        def custom_display(*args, **kwargs):
            for obj in args:
                if obj is None:
                    continue
                
                # Check if it has html representation (e.g. Pandas DataFrame)
                html = None
                if hasattr(obj, '_repr_html_'):
                    html = obj._repr_html_()
                elif hasattr(obj, 'to_html'):
                    html = obj.to_html()
                
                if html is not None:
                    cell_displays.append({
                        "data": {
                            "text/html": [line + "\n" for line in html.splitlines()],
                            "text/plain": [line + "\n" for line in str(obj).splitlines()]
                        },
                        "metadata": {},
                        "output_type": "display_data"
                    })
                # Check if it is an IPython Image
                elif type(obj).__name__ == 'Image' or hasattr(obj, 'filename'):
                    filename = getattr(obj, 'filename', None)
                    if filename and Path(filename).exists():
                        img_bytes = Path(filename).read_bytes()
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                        cell_displays.append({
                            "data": {
                                "image/png": img_base64,
                                "text/plain": [f"<Image: {filename}>\n"]
                            },
                            "metadata": {},
                            "output_type": "display_data"
                        })
                    else:
                        cell_displays.append({
                            "data": {
                                "text/plain": [str(obj) + "\n"]
                            },
                            "metadata": {},
                            "output_type": "display_data"
                        })
                else:
                    cell_displays.append({
                        "data": {
                            "text/plain": [line + "\n" for line in str(obj).splitlines()]
                        },
                        "metadata": {},
                        "output_type": "display_data"
                    })
        
        # Inject custom_display into the namespace
        global_ns['display'] = custom_display
        
        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        
        cell_error = None
        
        try:
            exec(code, global_ns)
        except Exception as e:
            traceback.print_exc(file=captured_stderr)
            cell_error = e
            sys.__stderr__.write(f"Erro na célula {execution_counter}: {e}\n")
            traceback.print_exc(file=sys.__stderr__)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
        outputs = []
        
        # Add stdout stream output
        stdout_val = captured_stdout.getvalue()
        if stdout_val:
            outputs.append({
                "name": "stdout",
                "output_type": "stream",
                "text": [line + "\n" for line in stdout_val.splitlines()]
            })
            
        # Add stderr stream output
        stderr_val = captured_stderr.getvalue()
        if stderr_val:
            outputs.append({
                "name": "stderr",
                "output_type": "stream",
                "text": [line + "\n" for line in stderr_val.splitlines()]
            })
            
        # Append all captured displays
        outputs.extend(cell_displays)
        
        # Capture figures (if any were drawn in cell)
        if plt.get_fignums():
            for fig_num in plt.get_fignums():
                fig = plt.figure(fig_num)
                buf = io.BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight')
                buf.seek(0)
                img_base64 = base64.b64encode(buf.read()).decode('utf-8')
                outputs.append({
                    "data": {
                        "image/png": img_base64
                    },
                    "metadata": {},
                    "output_type": "display_data"
                })
            plt.close('all')
            
        # Save outputs back to cell
        cell['outputs'] = outputs
        cell['execution_count'] = execution_counter
        
        execution_counter += 1
        
        if cell_error:
            print("Execução interrompida devido a um erro.")
            break
            
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2, ensure_ascii=False)
        
    print(f"Notebook {NOTEBOOK_PATH.name} executado e salvo com sucesso com todos os outputs!")

if __name__ == "__main__":
    execute_notebook()
