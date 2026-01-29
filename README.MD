# LLM Multi-Agent Battle Simulator

A multi-agent battle simulation framework where AI-powered agents autonomously make strategic decisions and compete in a dynamic card-based environment. The project explores the reasoning capabilities of Large Language Models (LLMs) within a hierarchical multi-agent system.

---

## Technical Stack

### ⚙️ Core
- **Python**
- **LangChain**

### 🤖 Models
- **OpenAI (GPT)**
- **Google (Gemini)**
- **Anthropic (Claude)**
- **Groq (Llama)**

### 📊 Data Handling
- **Pydantic (Structured Output)**

---

## 🚀 Features

- **Autonomous AI Agents:** Agents capable of advanced strategic decision-making powered by Large Language Models (LLMs).
- **Hierarchical Multi-Agent Architecture:** Structured agent hierarchy enabling coordinated planning, reasoning, and execution.
- **Dynamic Competitive Battle Simulation:** Agents compete in an evolving environment that tests adaptability and long-term strategy.
- **Multi-LLM Provider Support:** Compatible with multiple LLM APIs, allowing flexible experimentation across different models.
- **Configurable Simulation Settings:** Easily adjust models, difficulty levels, and key parameters to customize experiments.
- **Experimental Benchmarking:** Includes tools and results for comparing model performance and analyzing agent behaviors.

---

## ⚙️ Setup & Installation

```bash
# Clone the repository
git clone https://github.com/doganenes/llm-multi-agent-battle.git

# Navigate to the project directory
cd llm-multi-agent-battle

```

## 🧪 Create a Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment (Windows)
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

### 📦 Install Dependencies

```bash
pip install -r requirements.txt
```

## 🔑 Configure API Keys

Set environment variables for the LLM providers you plan to use.

### ✅ Required Keys
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`


## ▶️ Usage

### Run the Simulation

Start the simulation with default settings:

```bash
python main.py
```

### Custom Configuration
Customize models, episode count, and difficulty:

```bash
python main.py --model-a "gpt-4o" --model-b "gpt-4o-mini" --episodes 10 --difficulty 1.5
```

### Arguments

- `--model-a` → Model ID for Team A  
- `--model-b` → Model ID for Team B  
- `--episodes` → Number of simulated games (Default: `5`)  
- `--difficulty` → Stat multiplier for Team B (Default: `1.0`)  
