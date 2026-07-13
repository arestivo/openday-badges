FROM python:3.11-slim

ENV POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    inkscape \
    fontconfig \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Fonts used by the badge SVG templates
RUN mkdir -p /usr/share/fonts/truetype/badges && \
    curl -fsSL -o "/usr/share/fonts/truetype/badges/KeaniaOne-Regular.ttf" \
      "https://raw.githubusercontent.com/google/fonts/main/ofl/keaniaone/KeaniaOne-Regular.ttf" && \
    curl -fsSL -o "/usr/share/fonts/truetype/badges/AlumniSansSC[wght].ttf" \
      "https://raw.githubusercontent.com/google/fonts/main/ofl/alumnisanssc/AlumniSansSC%5Bwght%5D.ttf" && \
    curl -fsSL -o "/usr/share/fonts/truetype/badges/MajorMonoDisplay-Regular.ttf" \
      "https://raw.githubusercontent.com/google/fonts/main/ofl/majormonodisplay/MajorMonoDisplay-Regular.ttf" && \
    fc-cache -f

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml README.md ./
RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 8000

CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "600", "app:app"]
