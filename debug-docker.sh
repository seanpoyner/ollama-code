#!/bin/bash
echo "=== Debugging ollama-code installation ==="
echo ""
echo "1. Current directory:"
pwd
echo ""
echo "2. ollama-code directory contents:"
ls -la /home/ollama/ollama-code/
echo ""
echo "3. ollama_code module contents:"
ls -la /home/ollama/ollama-code/ollama_code/
echo ""
echo "4. Python path test:"
cd /home/ollama/ollama-code
source venv/bin/activate
python -c "import sys; print('Python paths:'); [print(f'  {p}') for p in sys.path]"
echo ""
echo "5. Direct import test:"
python -c "import ollama_code; print('Success: ollama_code imported')" 2>&1
echo ""
echo "6. CLI module test:"
python -c "import ollama_code.cli; print('Success: ollama_code.cli imported')" 2>&1
echo ""
echo "7. Main function test:"
python -c "from ollama_code.cli import main; print(f'Main function: {main}')" 2>&1
echo ""
echo "8. Direct run test:"
python -m ollama_code.cli --help 2>&1 | head -20
echo ""
echo "9. Check installed packages:"
pip list | grep -E "(ollama|rich|requests|pyyaml)"
echo ""
echo "10. Check if running from correct directory matters:"
cd /
python -m ollama_code.cli --help 2>&1 | head -5
cd /home/ollama/ollama-code
python -m ollama_code.cli --help 2>&1 | head -5