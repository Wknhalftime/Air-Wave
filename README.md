# Airwave - Broadcast Log Management System

**Airwave** is an intelligent broadcast log management system that automatically matches raw artist/title pairs from radio station logs to your music library, making it easy to verify, correct, and export accurate broadcast data.

---

## 🎯 What Does Airwave Do?

Airwave solves a common problem for radio stations: **matching messy broadcast logs to your actual music library**.

### The Problem

Radio automation systems often log songs with inconsistent formatting:
- `"BEATLES"` vs `"The Beatles"` vs `"Beatles, The"`
- `"HEY JUDE"` vs `"Hey Jude"` vs `"Hey Jude (Remastered)"`
- Typos, truncation, extra text, case variations

### The Solution

Airwave uses intelligent matching algorithms to:
1. **Import** broadcast logs from your radio station
2. **Match** raw artist/title pairs to your music library automatically
3. **Verify** uncertain matches through an intuitive UI
4. **Export** clean, accurate data for reporting or music scheduling software

---

## ✨ Key Features

### 🤖 Intelligent Matching

- **Multiple matching strategies**: Exact match, fuzzy matching, semantic vector search
- **Configurable thresholds**: Fine-tune matching behavior with the Match Tuner
- **Three-range filtering**: Auto-accept high confidence, review uncertain, reject low confidence
- **Pre-verified mappings**: Identity Bridge remembers verified matches for instant future matching

### 🎨 User-Friendly Verification Hub

- **Artist Linking**: Create artist aliases to normalize artist names across your entire dataset
- **Song Linking**: Review and verify uncertain song matches with full context
- **Batch Operations**: Link, reject, or promote multiple items at once
- **Smart Filtering**: Filter by match status, date range, or search terms

### 🎛️ Match Tuner (Advanced)

- **Visual threshold calibration**: See real-time examples of what each threshold setting means
- **Impact analysis**: Know exactly how many matches will be affected before changing thresholds
- **Edge case detection**: Identify matches near threshold boundaries
- **2D visualization**: Advanced scatter plot view of the decision space
- **Quality warnings**: Automatic detection of truncation, length mismatches, and other issues

### 📊 Library Navigation

- **Hierarchical browsing**: Navigate by Artist → Work → Recording → Library Files
- **Multi-artist support**: Proper handling of collaborations and featured artists
- **Version management**: Track multiple versions (Original, Radio Edit, Live, etc.)
- **File management**: See which physical files are linked to each recording

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **PostgreSQL** (for production) or SQLite (for development)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Wknhalftime/Air-Wave.git
   cd Air-Wave
   ```

2. **Set up the backend**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up the frontend**
   ```bash
   cd frontend
   npm install
   ```

4. **Configure environment**
   ```bash
   # Create .env file in backend/
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Initialize the database**
   ```bash
   cd backend
   alembic upgrade head
   ```

### Running the Application

1. **Start the backend** (from `backend/` directory)
   ```bash
   uvicorn airwave.main:app --reload
   ```
   Backend will run on `http://localhost:8000`

2. **Start the frontend** (from `frontend/` directory)
   ```bash
   npm run dev
   ```
   Frontend will run on `http://localhost:5173` (or next available port)

3. **Open your browser**
   Navigate to `http://localhost:5173`

---

## 📖 How to Use Airwave

### 1. Import Your Music Library

First, import your music library so Airwave knows what songs you have:

1. Go to **Library** in the navigation
2. Click **Import Library**
3. Select your music directory or import from your music scheduling software
4. Wait for the import to complete

Your library will be organized hierarchically:
- **Artists** (e.g., "The Beatles")
- **Works** (e.g., "Hey Jude" - the song itself)
- **Recordings** (e.g., "Hey Jude (Original)", "Hey Jude (Radio Edit)")
- **Library Files** (e.g., `/music/beatles/hey_jude.flac`)

### 2. Import Broadcast Logs

Import logs from your radio automation system:

1. Go to **Import** in the navigation
2. Upload your broadcast log file (CSV, TXT, or other supported formats)
3. Map the columns (Date/Time, Artist, Title)
4. Click **Import**

Airwave will automatically attempt to match each log entry to your library.

### 3. Review Matches in Verification Hub

After import, Airwave categorizes matches into three groups:

#### **Auto-Linked** ✅
High confidence matches that were automatically linked. No action needed!

#### **Review** ⚠️
Uncertain matches that need your verification. This is where you'll spend most of your time.

**To review matches:**
1. Go to **Verification Hub** → **Song Linking** tab
2. Review each suggested match:
   - See the raw artist/title from the log
   - See the suggested library match
   - See similarity scores and match reason
3. Take action:
   - **Link** - Accept the suggestion
   - **Reject** - Mark as incorrect
   - **Promote to Identity Bridge** - Accept and remember for future imports

#### **Unmatched** ❌
Items that couldn't be matched. These might be:
- Songs not in your library
- Commercials, station IDs, or non-music content
- Severely misspelled or truncated entries

### 4. Create Artist Aliases (Optional but Recommended)

Normalize artist names across your entire dataset:

1. Go to **Verification Hub** → **Artist Linking** tab
2. You'll see raw artist names from your logs (e.g., "BEATLES", "Beatles, The")
3. For each raw name:
   - Search for the correct library artist (e.g., "The Beatles")
   - Click **Link** to create an alias
4. Future imports will automatically use the correct artist name

**Pro Tip:** Do this proactively! You don't have to wait for songs to fail matching.

### 5. Fine-Tune Matching (Advanced)

Adjust matching thresholds to fit your needs:

1. Go to **Admin** → **Match Tuner**
2. Adjust the sliders:
   - **Auto-Accept Thresholds** (Artist/Title): Matches above these are auto-linked
   - **Review Thresholds** (Artist/Title): Matches above these go to Verification Hub
   - Matches below review thresholds are rejected
3. See real-time examples of what each setting means
4. See impact summary (how many matches will be affected)
5. Click **Save Settings** when satisfied

**Default Settings:**
- Auto-Accept: 85% artist, 80% title
- Review: 70% artist, 70% title

### 6. Export Matched Data

Export your verified broadcast logs:

1. Go to **Export**
2. Select date range
3. Choose export format (CSV, Excel, etc.)
4. Click **Export**

Your export will include:
- Original log data (date/time, raw artist/title)
- Matched library data (canonical artist, work, recording)
- Match confidence and verification status

---

## 🎓 Understanding the Matching System

### How Matching Works

Airwave uses a **multi-strategy matching pipeline** (in priority order):

1. **Identity Bridge** (Instant)
   - Pre-verified permanent mappings
   - If you've verified "BEATLES|HEY JUDE" before, it's instantly matched

2. **Exact Match** (Fast)
   - Normalized exact string matching
   - "The Beatles" = "beatles" = "BEATLES"

3. **High Confidence Fuzzy** (Fast)
   - Similarity ≥ auto-accept thresholds
   - Automatically linked, no review needed

4. **Review Confidence Fuzzy** (Fast)
   - Similarity ≥ review thresholds but < auto-accept
   - Added to Verification Hub for review

5. **Vector Semantic Search** (Slower)
   - AI-powered semantic similarity
   - Can catch misspellings and variations
   - Always requires review

### Three-Range Filtering

```
100% ┌──────────────────────────────────────┐
     │                                      │
     │   AUTO-ACCEPT RANGE                  │
     │   (Both artist AND title ≥ auto)    │
     │   → Automatically linked             │
     │                                      │
 85% ├──────────────────────────────────────┤
     │                                      │
     │   REVIEW RANGE                       │
     │   (Both ≥ review, one < auto)       │
     │   → Verification Hub                 │
     │                                      │
 70% ├──────────────────────────────────────┤
     │                                      │
     │   REJECT RANGE                       │
     │   (Either < review)                  │
     │   → Not shown in Verification Hub    │
     │                                      │
  0% └──────────────────────────────────────┘
```

### Work vs Recording (Important!)

Airwave separates **identity** (what song?) from **version** (which recording?):

- **Work** = The song itself (e.g., "Hey Jude")
- **Recording** = A specific version (e.g., "Hey Jude (Original)", "Hey Jude (Radio Edit)")

When you verify a match, you're saying "this log entry is **this song**", not "this specific recording". This gives you flexibility to change preferred versions later without re-verifying.

---

## 🛠️ Troubleshooting

### "Too many matches in Review"

Your auto-accept thresholds might be too high. Try:
1. Go to **Match Tuner**
2. Lower auto-accept thresholds slightly (e.g., 85% → 80%)
3. Check the impact summary
4. Save if the results look better

### "Too many auto-links are wrong"

Your auto-accept thresholds might be too low. Try:
1. Go to **Match Tuner**
2. Raise auto-accept thresholds (e.g., 80% → 85%)
3. Check examples to verify quality
4. Save if the results look better

### "Artist names are inconsistent"

Use Artist Linking to normalize:
1. Go to **Verification Hub** → **Artist Linking**
2. Create aliases for common variations
3. Re-run discovery to apply aliases to existing logs

### "Matching is slow"

This is normal for initial imports. Airwave processes in batches of 500 items. Subsequent imports are faster because:
- Identity Bridge remembers verified matches
- Artist aliases are pre-applied
- High confidence matches are auto-linked

---

## 📚 Documentation

For developers and advanced users:

- **[docs/CURRENT-ARCHITECTURE.md](./docs/CURRENT-ARCHITECTURE.md)** - System architecture overview
- **[docs/CHANGELOG.md](./docs/CHANGELOG.md)** - Recent changes and improvements
- **[docs/README.md](./docs/README.md)** - Documentation navigation guide
- **[docs/match-tuner-all-phases-complete.md](./docs/match-tuner-all-phases-complete.md)** - Match Tuner deep dive

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Before contributing, please read:**
- `.cursorrules` - AI agent guidelines and best practices
- `docs/CURRENT-ARCHITECTURE.md` - System architecture
- `docs/CHANGELOG.md` - Recent changes

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern Python web framework
- **React** - Frontend UI library
- **ChromaDB** - Vector database for semantic search
- **SQLAlchemy** - Python SQL toolkit
- **Recharts** - Charting library for visualizations

---

## 📞 Support

For questions, issues, or feature requests:
- Open an issue on GitHub
- Check the documentation in `docs/`
- Review the troubleshooting section above

---

**Made with ❤️ for radio stations who want clean, accurate broadcast data.**
