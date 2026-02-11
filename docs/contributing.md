# Contributing

Contributions to the OpenMagnetics Virtual Builder are welcome.

## Development Setup

1. **Fork and clone** the repository:

    ```bash
    git clone https://github.com/YOUR_USERNAME/MVB.git
    cd MVB
    ```

2. **Install dependencies**:

    ```bash
    pip install -e .
    pip install cadquery numpy ezdxf
    ```

3. **Clone MAS data** (for tests):

    ```bash
    git clone https://github.com/OpenMagnetics/MAS.git ../MAS
    ```

4. **Run tests** to verify setup:

    ```bash
    python -m unittest tests.test_builder
    ```

## Code Style

- Follow PEP 8 conventions
- Use descriptive variable names
- Add docstrings to public methods (Google style)
- Keep lines under 120 characters

## Adding a New Shape Family

1. Add the family to `ShapeFamily` enum in `utils.py`
2. Create the shape class in both `cadquery_builder.py` and `freecad_builder.py`
3. Inherit from the appropriate base class (`IPiece`, `E`, `P`, `U`, etc.)
4. Implement `get_shape_base()` and `get_negative_winding_window()`
5. Register the shape in the engine's `shapers` dict
6. Add dimension/subtype config to `shape_configs.py` if needed
7. Add tests and update documentation

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Ensure all tests pass
4. Update documentation if needed
5. Open a pull request against `main`
6. Describe your changes and link any related issues

## Reporting Issues

Please report bugs and feature requests on the
[GitHub Issues](https://github.com/OpenMagnetics/MVB/issues) page.

Include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages / tracebacks
