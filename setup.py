"""Setup script for Ollama Code"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ollama-code",
    version="0.1.0",
    author="Sean Poyner and Ollama Code Contributors",
    author_email="sean.poyner2@gmail.com",
    description="A powerful coding assistant powered by Ollama",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ollama-code",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "ollama>=0.1.0",
        "rich>=13.0.0",
        "requests>=2.25.0",
        "pyyaml>=5.4.0",
    ],
    extras_require={
        "docker": ["docker>=5.0.0"],
        "mcp": ["fastmcp>=0.1.0"],
        "chromadb": ["chromadb>=0.4.0"],
        "all": ["docker>=5.0.0", "fastmcp>=0.1.0", "chromadb>=0.4.0"],
    },
    entry_points={
        "console_scripts": [
            "ollama-code=ollama_code.cli:main",
        ],
    },
    package_data={
        "ollama_code": ["../messages.json", "../prompts.yaml"],
    },
)