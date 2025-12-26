# Reproducing the Optiqal Paper

This guide explains how to build the paper and reproduce all results.

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- [Bun](https://bun.sh) for running JavaScript tests

## Building the Paper

### 1. Install Dependencies

```bash
cd docs
uv sync
```

This installs:
- `mystmd` - MyST Markdown document builder
- `jupyter` - For executing code blocks in the paper
- `ipykernel` - Python kernel for Jupyter

### 2. Build HTML Version

First build (executes all Python code):
```bash
myst build --execute --html
```

Subsequent builds (uses cached results):
```bash
myst build --html
```

### 3. Build PDF Version

```bash
myst build --execute --pdf
```

### 4. View Output

HTML output is in `docs/_build/site/public/`

PDF output is in `docs/exports/optiqal.pdf`

## Project Structure

```
docs/
├── index.md              # Main paper
├── appendix.md           # Supplementary material
├── references.bib        # Bibliography
├── myst.yml             # MyST configuration
├── pyproject.toml       # Python dependencies
├── validation/          # Validation documentation
│   └── pan-ukb-plan.md  # Pan-UKB validation plan
├── precomputed-baselines.md    # Precomputed baseline documentation
└── precomputed-quick-start.md  # Quick start for precomputed results
```

## Reproducing Calculations

### JavaScript/TypeScript Tests

All core QALY calculations are implemented in TypeScript with comprehensive test coverage.

Run tests:
```bash
cd ..  # Return to project root
bun test
```

Run with UI:
```bash
bun test:ui
```

### Python Validation

Validation analyses are in Jupyter notebooks:

```
notebooks/
└── pan-ukb-validation.ipynb  # Pan-UK Biobank validation
```

To run validation notebooks:
```bash
cd notebooks
jupyter notebook pan-ukb-validation.ipynb
```

## Reproducing Figures

All figures in the paper are generated from executable code blocks. When you run `myst build --execute --html`, MyST automatically:

1. Executes Python code blocks marked with `{code-cell}`
2. Captures matplotlib plots and other outputs
3. Embeds them in the generated HTML/PDF

To regenerate specific figures, modify the code blocks in `index.md` or `appendix.md` and rebuild.

## Development Workflow

1. **Edit content**: Modify `.md` files in the `docs/` directory
2. **Update bibliography**: Add references to `references.bib`
3. **Test calculations**: Run `bun test` from project root
4. **Rebuild**: Run `myst build --execute --html` to see changes
5. **Review**: Open `_build/site/public/index.html` in your browser

## Configuration

The paper is configured in `docs/myst.yml`:

- **Title and metadata**: Project title, authors, keywords
- **Export formats**: HTML, PDF
- **Bibliography**: Reference to `references.bib`
- **Table of contents**: Main paper and appendix

## Dependencies

### Python (docs/pyproject.toml)
- `mystmd>=1.0` - Document building
- `jupyter>=1.0` - Notebook execution
- `ipykernel>=6.0` - Python kernel

### JavaScript (package.json at project root)
- `vitest` - Testing framework
- `@vitest/ui` - Test UI
- Core libraries for QALY calculations

## Troubleshooting

### "Command not found: myst"

Make sure you've activated the virtual environment:
```bash
cd docs
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### Build errors with Python code

If code execution fails:
1. Check that all required packages are installed (`uv sync`)
2. Verify Python version is 3.10+
3. Look for error messages in the build output

### Tests fail

Run tests with verbose output to diagnose:
```bash
bun test --reporter=verbose
```

## Citation

If you use this framework in your research, please cite:

```bibtex
@article{ghenis2024optiqal,
  title={Optiqal: A State-Based Framework for Personalized QALY Estimation},
  author={Ghenis, Max},
  year={2024},
  url={https://github.com/MaxGhenis/optiqal-ai}
}
```

## License

MIT License - see LICENSE file for details.
