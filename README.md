# GenAI Hybrid Bot

A Telegram bot that can answer questions from a set of documents (RAG) and describe images you send it. Built with a microservice approach — 4 separate services talking to each other over HTTP.

## What it does

- `/ask <question>` — searches through knowledge base docs and gives you an answer
- `/image` — send or reply to a photo, gets a caption and tags back
- `/summarize` — shows your recent chat history
- `/help` — lists available commands
- You can also just send a photo directly without any command, it'll describe it automatically

## Architecture

I split the project into 4 services so each one handles one thing:

```
Telegram User
     |
     v
Bot Gateway (python-telegram-bot)
  - routes /ask to RAG service
  - routes /image to Vision service
  - keeps track of last 3 messages per user
     |                    |
     v                    v
RAG Service (:8002)   Vision Service (:8003)
  - gets chunks from     - runs BLIP model locally
    embedding service    - returns caption + 3 tags
  - sends them to       - no API calls needed
    OpenAI for answer
     |
     v
Embedding Service (:8001)
  - chunks documents
  - embeds with sentence-transformers
  - stores in SQLite
  - cosine similarity search
     |
     v
SQLite (embeddings + query cache)
```

**Why microservices?** Each service does one job. If I need to swap out the embedding model or change the LLM, I only touch one file. Also makes testing easier since I can test each service on its own.

**Why SQLite?** For 5 small documents, a full vector database would be overkill. SQLite is simple, needs zero setup, and works fine at this scale.

**Why Telegram?** Simpler bot API compared to Discord, quick to set up with BotFather.

## Models used

| What | Model | Runs where | Why I picked it |
|------|-------|-----------|-----------------|
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Locally on CPU | Small (~80MB), fast, gives 384-dim vectors. Works well for semantic search on small docs. No API key needed. |
| Image captioning | `Salesforce/blip-image-captioning-base` (HuggingFace) | Locally on CPU | BLIP generates decent captions and I can use conditional prompts to extract tags. ~990MB but runs fine without a GPU. Picked over blip2 (too big) and llava (needs GPU). |
| Answer generation | `gpt-4o-mini` (OpenAI) | API call | I need a good LLM to take the retrieved chunks and write a proper answer. gpt-4o-mini is cheap and follows instructions well. Could swap this for Ollama if needed. |

So embeddings and vision run fully offline. Only the final answer generation step calls OpenAI.

## How `/ask` works (step by step)

1. User sends `/ask What is the leave policy?`
2. Bot gateway picks up the command, sends query to RAG service
3. RAG service asks embedding service to find the top 3 most relevant chunks
4. Embedding service checks if this query was cached — if yes, returns cached results. If not, it embeds the query locally with sentence-transformers, compares against all stored chunks using cosine similarity, returns top matches, and caches the result.
5. RAG service takes those chunks, builds a prompt with the context, and calls OpenAI to generate an answer
6. Bot sends the answer back with source file names so you know where it came from

## How `/image` works

1. User sends a photo (or replies to one with `/image`)
2. Bot downloads the image from Telegram
3. Sends it to the Vision service
4. Vision service runs it through BLIP locally — generates a caption and uses conditional prompts to extract 3 keyword tags
5. Bot sends back the caption and tags. No API calls involved here.

## How documents get indexed

On startup, the embedding service:
1. Loads the sentence-transformers model
2. Reads all `.md` and `.txt` files from `knowledge_base/`
3. Splits each file into chunks (500 chars with 50 char overlap)
4. Skips chunks it has already seen (checks by MD5 hash)
5. Batch-embeds all new chunks and stores them in SQLite

## Knowledge base

Comes with 5 sample docs:

- `company_policies.md` — leave, remote work, work hours
- `tech_faq.md` — dev setup, tech stack, deployments
- `onboarding_guide.md` — first day/week checklist, contacts
- `product_guide.md` — features, pricing, API limits
- `security_guidelines.md` — passwords, data handling, incidents

Drop your own `.md` or `.txt` files in `knowledge_base/` and restart to add more.

## Project structure

```
├── config.py                # all env vars and settings in one place
├── run.py                   # starts all 4 services
├── requirements.txt
├── .env                     # your API keys go here
├── .env.example
│
├── services/
│   ├── embedding/app.py     # sentence-transformers + SQLite
│   ├── rag/app.py           # retrieval + OpenAI generation
│   ├── vision/app.py        # BLIP captioning
│   └── bot_gateway/app.py   # Telegram bot
│
├── knowledge_base/          # your docs go here
│   ├── company_policies.md
│   ├── tech_faq.md
│   ├── onboarding_guide.md
│   ├── product_guide.md
│   └── security_guidelines.md
│
├── tests/
│   ├── test_embedding.py    # 5 tests
│   ├── test_rag.py          # 5 tests
│   └── test_vision.py       # 4 tests
│
└── data/
    └── embeddings.db        # created at runtime
```

## How to run

### What you need

- Python 3.11 or higher
- An OpenAI API key (only used for answer generation)
- A Telegram bot token (get it from @BotFather)
- About 2GB free disk space for model downloads on first run

### Setup

```bash
cd New
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in:
#   OPENAI_API_KEY=sk-proj-...
#   TELEGRAM_BOT_TOKEN=your-token-here

python run.py
```

First time you run it, it'll download the models (~80MB for embeddings, ~990MB for BLIP). After that they're cached locally.

## Running tests

Start the services first, then in another terminal:

```bash
pytest tests/ -v
```

14 tests total — covers health checks, embedding generation, search, caching, RAG Q&A with history, image captioning, and input validation.

## Optional features I added

These were listed as bonus in the assignment:

- **Message history** — bot remembers last 3 interactions per user, so follow-up questions work
- **Query caching** — if you ask the same question twice, it skips re-embedding and returns cached search results
- **Source snippets** — each RAG answer shows which document file the info came from
- **`/summarize` command** — shows a quick recap of recent conversation
- **Hybrid mode** — both RAG and vision work in the same bot, not just one or the other
