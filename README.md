# Self-Correcting Terminal Agent 🤖⚡

An autonomous terminal agent that sniffs your environment, plans multi-step tasks, and automatically corrects errors using LLMs (Ollama or Gemini).

## ✨ Features

-   **Environment Aware**: Detects OS, Shell, and installed tools to generate compatible commands.
-   **Self-Healing**: Automatically analyzes error output and suggests fixes to resume progress.
-   **Real-time Streaming**: Captures and streams terminal output line-by-line (or character-by-character).
-   **Robust CWD Tracking**: Correctly follows directory changes even in complex chained commands (e.g., `mkdir test && cd test`).
-   **Auto-Venv Activation**: Automatically detects and uses local virtual environments (`venv`, `.venv`, `env`).
-   **Interactive Prompts**: Detects `(y/n)` prompts and allows for user interaction.
-   **Task Persistence**: Saves and loads command history to improve long-term decision making.
-   **Dual Interface**: Use it via a beautiful CLI (powered by `rich`) or a FastAPI-based streaming server.

## 🏗️ Architecture

The project is modularly designed:
-   **`EnvSniffer`**: Gathers system context.
-   **`CommandExecutor`**: Handles robust execution and state management.
-   **`Planner`**: LLM-driven reasoning for task decomposition and debugging.
-   **`TerminalAgent`**: The orchestrator managing the "Plan -> Run -> Fix" loop.

## 🚀 Getting Started

### Prerequisites

-   Python 3.10+
-   [Ollama](https://ollama.com/) (Default) or a Google Gemini API Key.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone <repo-url>
    cd self-correcting-terminal
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables**:
    Create a `.env` file in the root directory:
    ```env
    LLM_PROVIDER=ollama
    PLANNER_MODEL=qwen2.5-coder:7b
    OLLAMA_HOST=http://127.0.0.1:11434

    # If using Google Gemini:
    # LLM_PROVIDER=google
    # PLANNER_MODEL=gemini-1.5-flash
    # GOOGLE_API_KEY=your_api_key_here
    ```

## 🛠️ Usage

### CLI Mode

Run a task directly from your terminal:

```bash
python main.py "Create a new react app named 'my-app' using vite and install tailwindcss"
```

### Server Mode (for UI/Frontend integration)

Start the FastAPI server:

```bash
python server.py
```

The server runs on `http://0.0.0.0:8002` and provides a streaming endpoint `/run` that sends events via Server-Sent Events (SSE).

## 🧪 Running Tests

```bash
# Set PYTHONPATH to include the current directory
$env:PYTHONPATH="."  # PowerShell
set PYTHONPATH=.     # CMD
export PYTHONPATH=.  # Bash/Zsh

pytest
```

## 📂 Project Structure

- `src/core/`: Core logic (Sniffer, Executor, Planner).
- `src/agent.py`: Main agent orchestrator.
- `main.py`: CLI entry point.
- `server.py`: FastAPI streaming server.
- `tests/`: Automated test suite.

## 📝 License

MIT
