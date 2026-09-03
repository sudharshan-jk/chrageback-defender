param([string]$task = "help")

switch ($task) {
    "install" { uv sync }
    "eval"    { uv run python -m src.eval.run_eval }
    "demo"    { uv run streamlit run app/main.py }
    "test"    { uv run pytest }
    "clean"   {
        Remove-Item data\chroma -Recurse -ErrorAction SilentlyContinue
        Remove-Item data\embeddings.pkl -ErrorAction SilentlyContinue
        Remove-Item logs\*.json -ErrorAction SilentlyContinue
    }
    default   { Write-Host "Usage: .\tasks.ps1 [install|eval|demo|test|clean]" }
}