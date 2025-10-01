# Canvas LMS Automation Tool

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tested with pytest](https://img.shields.io/badge/tested%20with-pytest-blue.svg)](https://github.com/pytest-dev/pytest/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-☕-yellow.svg?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/seanpavlak)

Automate Canvas LMS tasks including AI-powered discussion responses and announcement scheduling using browser automation.

## ✨ Features

- 🤖 **AI-Powered Discussion Responses** - Generate contextual responses using OpenAI, Anthropic, or DeepSeek
- 📢 **Automated Announcement Scheduling** - Schedule announcements for entire course with calculated dates
- 🎯 **Interactive CLI** - Rich terminal interface with arrow key navigation
- ⚙️ **Flexible Configuration** - JSON-based course and announcement configuration
- 🔒 **Environment Validation** - Pydantic-based validation for settings and configurations
- 📊 **Rich Logging** - Beautiful console logging with tracebacks
- 🔄 **Auto Week Detection** - Automatically calculates current week based on course start date

## 📋 Prerequisites

- Python 3.10 or higher
- Canvas LMS account credentials
- At least one LLM API key (OpenAI, Anthropic, or DeepSeek)

## 🚀 Installation

1. **Clone the repository**
   ```bash
   cd /path/to/your/projects
   git clone <your-repo-url> chcp
   cd chcp
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

## ⚙️ Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Canvas LMS Credentials (Required)
CANVAS_USERNAME=your.email@example.com
CANVAS_PASSWORD=your_password

# LLM API Keys (At least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
```

### 2. Course Configuration

Edit `courses.json` to configure your courses:

```json
{
  "courses": {
    "A": {
      "course_id": "12345",
      "course_start_date": "2025-09-02",
      "name": "Physics 100 - Section A",
      "weeks": {
        "1": {
          "topic_id": "67890",
          "discussion_prompt": "Your week 1 discussion prompt...",
          "discussion_data": [
            {
              "post": "Example student post...",
              "response": "Example instructor response..."
            }
          ]
        }
      }
    }
  }
}
```

**Key Fields:**
- `course_id`: Canvas course ID (found in URL)
- `course_start_date`: First day of course (YYYY-MM-DD format)
- `topic_id`: Canvas discussion topic ID
- `discussion_data`: Example posts/responses for AI training

### 3. Announcement Configuration

Edit `announcements.json` to configure announcements:

```json
{
  "announcements": [
    {
      "week": 1,
      "title": "Week 1 - Welcome!",
      "content": "<p>Your HTML content here...</p>"
    }
  ]
}
```

## 🎮 Usage

### Interactive Mode (Recommended)

Simply run without arguments for guided experience:

```bash
python main.py
```

Use arrow keys to:
1. Select action (discussion, announcement, or donate)
2. Choose course
3. Select LLM provider (if applicable)
4. Specify week (if applicable)

The interactive menu includes a **donate** option that opens the support page directly in your browser!

### Command-Line Mode

#### Process Discussions

```bash
# Auto-detect week and provider
python main.py discussion --course A

# Specify week and provider
python main.py discussion --course A --week 3 --provider anthropic

# Use course ID directly
python main.py discussion --course 12345 --week 2
```

#### Schedule Announcements

```bash
# Use course selector
python main.py announcement --course A

# Use course ID
python main.py announcement --course 12345
```

### Direct Script Execution

You can also run individual modules:

```bash
# Run discussion handler directly
python discussions.py --course A --week 3

# Run announcement scheduler directly
python announcements.py --course A
```

## 📁 Project Structure

```
chcp/
├── main.py                    # CLI entry point
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (create from .env.example)
│
├── discussions.py             # Discussion handler
├── announcements.py          # Announcement scheduler
├── response_generator.py     # LLM response generation
├── canvas_service.py         # Browser automation service
│
├── course_utils.py           # Course/date utilities
├── llm_manager.py            # LLM provider management
├── config.py                 # Configuration constants
├── schemas.py                # Pydantic validation schemas
├── env_validator.py          # Environment validation
├── logger.py                 # Logging configuration
│
├── announcements.json        # Announcement data
└── courses.json              # Course configuration
```

## 🔧 Advanced Configuration

### Customizing LLM Behavior

Edit `config.py` to customize LLM parameters:

```python
@dataclass(frozen=True)
class LLMConfig:
    TEMPERATURE: Final[float] = 0.8  # Creativity (0-1)
    MAX_RESPONSE_WORDS: Final[int] = 80  # Max response length
    FEW_SHOT_K: Final[int] = 3  # Number of examples to use
```

### Customizing Wait Times

Adjust browser automation timings in `config.py`:

```python
@dataclass(frozen=True)
class CanvasConfig:
    LOGIN_WAIT_TIME: Final[int] = 3  # Seconds
    NAVIGATION_WAIT_TIME: Final[int] = 2
```

## 🐛 Troubleshooting

### "No LLM API keys found"
- Ensure at least one API key is set in `.env`
- Check that `.env` is in the project root
- Verify no typos in environment variable names

### "Course not found in courses.json"
- Verify course selector matches a key in `courses.json`
- Or use numeric course ID from Canvas URL

### "Missing topic_id for week X"
- Ensure `topic_id` is filled in for the week in `courses.json`
- Topic ID is found in the Canvas discussion URL

### Browser Doesn't Open
```bash
# Reinstall Playwright browsers
playwright install --force chromium
```

### Import Errors
```bash
# Ensure virtual environment is activated
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

## 📝 Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Code Quality

```bash
# Type checking
mypy *.py

# Linting
ruff check .

# Formatting
black .
```

## 🔐 Security Notes

- Never commit `.env` file to version control
- Store API keys securely
- Canvas credentials are never logged
- Use read-only API keys when possible

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note:** Ensure compliance with your institution's Canvas LMS terms of service when using this tool.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📧 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review existing issues on GitHub
3. Open a new issue with detailed description

## ☕ Support the Project

If this tool has saved you time and made your Canvas workflow easier, consider supporting its development:

**[Buy Me a Coffee ☕](https://buymeacoffee.com/seanpavlak)**

Your support helps maintain and improve this tool for educators everywhere. Every contribution is appreciated! 🙏

---

**Made with ❤️ for educators automating Canvas LMS workflows**

