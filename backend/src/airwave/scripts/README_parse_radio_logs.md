# Radio Log Parser

High-speed, memory-efficient pipeline to parse radio CSV logs into a relational **Artist -> Song -> Playtimes** model.

## Input Format

CSV with columns: `Station`, `Played`, `Artist`, `Title`, `Release Year`, `Grc`.

## Usage

```bash
poetry run python -m airwave.scripts.parse_radio_logs path/to/radio_log.csv -o output_dir
poetry run python -m airwave.scripts.parse_radio_logs radio_log.csv -o out --chunk 10000
```

## Outputs

- `song_catalog.csv`: song_id, artist, title, year
- `airplay_log.csv`: timestamp, song_id
